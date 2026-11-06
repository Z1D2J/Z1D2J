"""Agent 编排层(应用层): 多轮工具往返 + 事件推送,UI 无关。

职责:
- 维护会话历史(含 reasoning_content 回传、标准格式 tool_calls 回传)
- 每轮: 流式请求 → 按事件回调推送 → 分发工具 → 回写 tool 结果 → 继续
- 上下文预算监控、/compact 压缩与原始上下文归档
- 出错统一转为 ErrorEvent 推送(不向上抛业务异常),TUI/Web 无需 try/except

线程模型: Agent 非线程安全,一个 turn 同一时刻只由一个线程驱动;
TUI 在 worker 线程中调用 run_turn/compact,通过 post_message 把事件投回 UI 线程。
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import Settings, load_config
from .context import (
    ContextStore,
    ContextUsage,
    build_archive_note,
    limit_summary,
    render_transcript,
)
from .errors import AgentError
from .events import (
    AgentEvent,
    AssistantMessage,
    CompactionFailed,
    CompactionFinished,
    CompactionStarted,
    ContextStatus,
    ContextWarning,
    ErrorEvent,
    EventSink,
    McpServerInfo,
    McpStatus,
    ReasoningDelta,
    TextDelta,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    TurnStarted,
    null_sink,
)
from .llm.client import (
    LLMClient,
    StreamReasoning,
    StreamText,
    StreamToolCalls,
    StreamUsage,
)
from .mcp import McpManager
from .session import AGENTS_MARKER, SessionInfo, SessionStore
from .skills import SkillCatalog
from .tools import ToolRegistry, build_default_registry
from .tools.recall import register as register_recall_tool
from .tools.skill import register as register_skill_tool

SYSTEM_PROMPT = (
    "你是 sAgent,一个严谨的智能助手。"
    "需要本地文件操作或系统信息时,调用提供的工具完成任务;"
    "需要生成或修改 PPT(.pptx)、Word(.docx)、Excel(.xlsx)时,优先调用 officeCli 工具;"
    "能直接回答时不要调用工具。回复保持简洁。"
)

COMPACT_PROMPT = """你是一名 AI Agent 的上下文管理助手。当前会话即将达到上下文窗口限制，需要将历史对话压缩为一份高质量的工作摘要，以便 Agent 在新的上下文中继续执行任务。

请认真阅读提供的历史上下文，提取对后续工作仍然有价值的信息，并生成一份约 5,000 Tokens 的 Markdown 摘要。

摘要应重点保留以下内容：

1. **用户目标与要求**：用户希望完成什么任务？有哪些必须遵守的约束、偏好和验收条件？
2. **已经完成的工作**：哪些任务已经完成？实现了哪些功能？获得了哪些已经验证的结果？
3. **当前工作状态**：Agent 正在处理什么任务？当前进展到哪一步？是否存在尚未解决的问题？
4. **关键技术信息**：保留重要的文件路径、函数名称、接口定义、配置项、执行命令、错误信息和必要的代码片段。
5. **关键决策与原因**：记录用户和 Agent 已经确定的技术方案，以及重要的设计取舍。
6. **下一步任务**：明确接下来应该执行的操作，以及需要继续验证的事项。

请遵守以下要求：

- 优先保留对后续任务有直接影响的信息，删除寒暄、重复讨论、过时的尝试和无关内容。
- 对已经验证的事实与尚未验证的推测作出明确区分。
- 不要将计划完成的任务描述为已经完成。
- 重要的文件路径、函数名称、配置名称和命令应保留准确原文。
- 对失败的尝试，只保留有助于避免重复错误的信息。
- 如果信息存在冲突，应优先保留用户最新确认的要求，并简要说明仍然存在的冲突。
- 如果某些历史细节无法在摘要中完整保留，可简要说明它们已保存到原始上下文归档中，后续可以通过 `recallContext` 工具重新检索。
- 使用清晰的 Markdown 结构输出摘要，不要附加解释或无关内容。

**最终目标：使一个从未阅读过原始对话的 Agent，仅凭这份摘要，就能够理解当前任务、继承关键决策，并继续开展工作。**"""


class Agent:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        registry: Optional[ToolRegistry] = None,
        system_prompt: str = SYSTEM_PROMPT,
        skills: Optional[SkillCatalog] = None,
    ):
        self.settings = settings or load_config()
        extra_skill_roots = [
            Path(part.strip()).expanduser()
            for part in re.split(r"[,;]", self.settings.skills_extra_dirs)
            if part.strip()
        ]
        self.skills = skills or SkillCatalog(extra_roots=extra_skill_roots)
        self.registry = registry or build_default_registry(self.settings)
        register_skill_tool(self.registry, self.skills)
        self.context = ContextStore(
            model=self.settings.model,
            context_window=self.settings.context_window,
            context_dir=self.settings.context_dir,
            compact_threshold=self.settings.compact_threshold,
            compact_target_tokens=self.settings.compact_target_tokens,
            compact_max_tokens=self.settings.compact_max_tokens,
            recall_max_matches=self.settings.recall_max_matches,
            recall_max_chars=self.settings.recall_max_chars,
            recall_snippet_chars=self.settings.recall_snippet_chars,
        )
        register_recall_tool(self.registry, self.context)
        self.mcp = McpManager(
            config_path=Path(self.settings.mcp_config_file),
            default_connect_timeout=self.settings.mcp_connect_timeout,
            default_call_timeout=self.settings.mcp_call_timeout,
            max_tool_name_length=self.settings.mcp_max_tool_name_length,
            max_result_chars=self.settings.mcp_max_result_chars,
        )
        self.mcp_errors: List[str] = []
        self._mcp_loading = False
        self._mcp_loaded = False
        self.client = LLMClient(self.settings)
        section = self.skills.prompt_section()
        self.system_prompt = f"{system_prompt}\n\n{section}" if section else system_prompt
        self.session_store = SessionStore(directory=self.settings.session_dir)
        self.session_id = self.session_store.new_id()
        self.session_created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._history: List[dict] = [{"role": "system", "content": self.system_prompt}]
        self._inject_agents_md()
        self._compacting = False
        self._blocked = False
        self._warning_sent = False

    @property
    def round_limit(self) -> int:
        return self.settings.max_tool_rounds

    def context_usage(self) -> ContextUsage:
        return self.context.usage(self._history, self.registry.definitions())

    def reset(self) -> None:
        """清空会话历史(回到 system prompt 起点)。"""
        self._history = [{"role": "system", "content": self.system_prompt}]
        self._inject_agents_md()
        self.context.reset_usage()
        self._blocked = False
        self._warning_sent = False

    def history_snapshot(self) -> List[dict]:
        """返回当前历史的浅拷贝,供 UI 在恢复会话后重放。"""
        return list(self._history)

    def has_dialogue(self) -> bool:
        """是否存在用户/助手/工具消息(避免把仅含 system 的空会话写盘)。"""
        return any(
            message.get("role") in ("user", "assistant", "tool")
            for message in self._history
        )

    def _agents_path(self) -> Path:
        path = Path(self.settings.agents_file).expanduser()
        return path if path.is_absolute() else Path.cwd() / path

    def _agents_message(self) -> Optional[dict]:
        path = self._agents_path()
        try:
            if not path.is_file():
                return None
            content = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            print(f"[AGENTS.md] 读取失败: {exc}", file=sys.stderr)
            return None
        content = content.strip()
        if not content:
            return None
        limit = max(1, self.settings.agents_max_chars)
        if len(content) > limit:
            content = content[:limit] + "\n...(AGENTS.md 内容过长,已截断)"
        return {
            "role": "system",
            "content": f"{AGENTS_MARKER}\n\n{content}",
        }

    def _inject_agents_md(self, history: Optional[List[dict]] = None) -> bool:
        """把 AGENTS.md 作为独立的 system 消息插入到会话开头(只注入一次)。"""
        target = history if history is not None else self._history
        if any(
            message.get("role") == "system"
            and AGENTS_MARKER in str(message.get("content") or "")
            for message in target
        ):
            return False
        message = self._agents_message()
        if message is None:
            return False
        index = 0
        while index < len(target) and target[index].get("role") == "system":
            index += 1
        target.insert(index, message)
        return True

    def save_session(self) -> SessionInfo:
        """把当前完整历史写入 .agents/sessions 下的 JSONL 文件。"""
        return self.session_store.save(
            self.session_id, self.session_created_at, self._history
        )

    def _auto_save(self) -> None:
        if not self.settings.auto_save_sessions or not self.has_dialogue():
            return
        try:
            self.save_session()
        except OSError as exc:
            print(f"[session] 自动保存失败: {exc}", file=sys.stderr)

    def new_session(self, save_current: bool = True) -> str:
        """结束当前会话并开启新会话;默认先保存旧会话。"""
        if save_current and self.has_dialogue():
            try:
                self.save_session()
            except OSError as exc:
                print(f"[session] 保存旧会话失败: {exc}", file=sys.stderr)
        self.session_id = self.session_store.new_id()
        self.session_created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.reset()
        return self.session_id

    def resume_session(self, session_id: str) -> SessionInfo:
        """恢复指定会话的消息历史;若旧记录缺少 AGENTS.md,则补注入。"""
        info, messages = self.session_store.load(session_id)
        self.session_id = info.id
        self.session_created_at = info.created_at or datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self._history = messages or [{"role": "system", "content": self.system_prompt}]
        self._inject_agents_md()
        self.context.reset_usage()
        self._blocked = False
        self._warning_sent = False
        self._compacting = False
        return info

    def mcp_status_event(self, loading: Optional[bool] = None) -> McpStatus:
        if loading is None:
            loading = self._mcp_loading
        servers = tuple(
            McpServerInfo(
                name=item.name,
                transport=item.transport,
                connected=item.connected,
                tools=item.tools,
                error=item.error,
            )
            for item in self.mcp.status()
        )
        return McpStatus(
            loading=loading,
            servers=servers,
            errors=tuple(self.mcp_errors),
        )

    def load_mcp(self, sink: EventSink = null_sink) -> McpStatus:
        """在 TUI worker 中异步加载 MCP;返回最终状态并推送 McpStatus 事件。"""
        if self._mcp_loading:
            return self.mcp_status_event(loading=True)
        if self._mcp_loaded:
            status = self.mcp_status_event()
            sink(status)
            return status

        self._mcp_loading = True
        sink(self.mcp_status_event(loading=True))
        try:
            self.mcp_errors = self.mcp.start()
            self.mcp.register_tools(self.registry)
            for message in self.mcp_errors:
                print(f"[MCP] {message}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001  MCP 失败不能拖垮 TUI
            self.mcp_errors.append(f"MCP 加载失败: {exc}")
        finally:
            self._mcp_loading = False
            self._mcp_loaded = True

        status = self.mcp_status_event()
        sink(status)
        return status

    def close(self) -> None:
        """释放 MCP 连接等进程级资源(幂等)。"""
        self.mcp.close()

    def run_turn(self, prompt: str, sink: EventSink = null_sink) -> str:
        """执行一轮完整对话(含工具往返);返回最终回复文本。

        任何运行期错误都会以 ErrorEvent 推送给 sink 并返回空字符串,
        保证 UI 层无需捕获异常。
        """
        if not prompt.strip():
            sink(ErrorEvent("提示词为空,请输入内容。"))
            sink(TurnFinished())
            return ""

        if self._compacting:
            sink(ErrorEvent("正在压缩上下文,请等待压缩完成后再输入。"))
            sink(TurnFinished())
            return ""

        usage = self._emit_context_status(sink)
        if self._blocked:
            sink(
                ErrorEvent(
                    f"上下文已使用 {usage.percent:.1f}%"
                    f"({usage.tokens / 1000:.1f}k / {usage.window / 1000:.0f}k)，"
                    "已暂停接受新的提示词。请先执行 /compact 压缩上下文。"
                )
            )
            sink(TurnFinished())
            return ""

        sink(TurnStarted(prompt))
        turn_start = len(self._history)
        self._history.append({"role": "user", "content": prompt})

        final_text = ""
        for _ in range(self.settings.max_tool_rounds + 1):
            try:
                reply_text, reasoning_text, tool_calls, total_tokens = self._stream_once(
                    sink
                )
            except AgentError as exc:
                sink(ErrorEvent(str(exc)))
                del self._history[turn_start:]  # 回滚整轮,保持历史一致
                sink(TurnFinished())
                return ""
            except KeyboardInterrupt:
                sink(ErrorEvent("已取消。"))
                del self._history[turn_start:]
                sink(TurnFinished())
                return ""

            if not tool_calls:
                self._history.append(self._assistant_message(reply_text, reasoning_text))
                self.context.note_usage(total_tokens, len(self._history))
                final_text = reply_text
                sink(AssistantMessage(reply_text, reasoning_text))
                self._emit_context_status(sink)
                self._auto_save()
                sink(TurnFinished())
                return final_text

            self._history.append(
                self._assistant_message(reply_text, reasoning_text, tool_calls)
            )
            self.context.note_usage(total_tokens, len(self._history))
            for call in tool_calls:
                name = call.get("function", {}).get("name") or ""
                sink(ToolCallStarted(name, call.get("function", {}).get("arguments") or ""))
                result = self.registry.dispatch(call)
                sink(ToolCallFinished(name, result))
                self._history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or "",
                        "content": result,
                    }
                )
            self._emit_context_status(sink)

        sink(ErrorEvent(f"错误: 工具调用轮次过多(>{self.settings.max_tool_rounds}),本轮终止。"))
        self._auto_save()
        sink(TurnFinished())
        return ""

    def compact(self, sink: EventSink = null_sink) -> bool:
        """手动压缩上下文: 先归档原文,再调用 LLM 生成摘要并替换历史。

        压缩失败时保持原有历史不变,返回 False;成功返回 True。
        """
        if self._compacting:
            sink(CompactionFailed("上下文压缩已在进行中,请稍候。"))
            return False
        if len(self._history) <= 1:
            sink(CompactionFailed("当前会话没有可压缩的历史内容。"))
            return False

        self._compacting = True
        sink(CompactionStarted())
        try:
            try:
                archive = self.context.new_archive()
                self.context.write_archive(archive, self._history)
            except OSError as exc:
                sink(CompactionFailed(f"原始上下文归档保存失败,已取消压缩: {exc}"))
                return False

            system_count = 0
            while (
                system_count < len(self._history)
                and self._history[system_count].get("role") == "system"
            ):
                system_count += 1
            history_text = render_transcript(
                self._history[system_count:], include_system=False
            )
            if not history_text.strip():
                sink(CompactionFailed("当前会话没有可压缩的历史内容。"))
                return False

            try:
                summary = self._generate_summary(history_text)
            except AgentError as exc:
                sink(CompactionFailed(str(exc)))
                return False
            except Exception as exc:  # 压缩失败必须保证原上下文不被破坏
                sink(CompactionFailed(f"生成上下文摘要失败: {exc}"))
                return False

            original_text = render_transcript(self._history, include_reasoning=True)
            summary = limit_summary(
                summary, archive.id, self.context.compact_max_tokens
            )
            note = build_archive_note(archive.id, archive.created_at)
            after_content = f"【历史上下文压缩摘要】\n\n{summary}\n\n{note}"

            system_messages = [
                message
                for message in self._history
                if message.get("role") == "system"
            ]
            self._history = [
                *system_messages,
                {"role": "user", "content": after_content},
                {
                    "role": "assistant",
                    "content": "已加载历史上下文压缩摘要，可以继续执行任务。",
                },
            ]
            self.context.reset_usage()
            self._blocked = False
            self._warning_sent = False

            sink(
                CompactionFinished(
                    archive_id=archive.id,
                    created_at=archive.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    original=original_text,
                    summary=after_content,
                )
            )
            self._emit_context_status(sink)
            self._auto_save()
            return True
        finally:
            self._compacting = False

    def _generate_summary(self, history_text: str) -> str:
        """压缩期间只允许调用 LLM 生成摘要,不提供任何工具定义。"""
        target = f"{self.context.compact_target_tokens:,}"
        prompt = COMPACT_PROMPT.replace("约 5,000 Tokens", f"约 {target} Tokens")
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": "以下是需要压缩的历史上下文：\n\n" + history_text,
            },
        ]
        parts: List[str] = []
        for event in self.client.stream(messages, []):
            if isinstance(event, StreamText):
                parts.append(event.text)
        summary = "".join(parts).strip()
        if not summary:
            raise AgentError("模型未返回有效的上下文摘要,请重试 /compact。")
        return summary

    def _emit_context_status(self, sink: EventSink) -> ContextUsage:
        usage = self.context_usage()
        sink(
            ContextStatus(
                tokens=usage.tokens,
                window=usage.window,
                percent=usage.percent,
                default_window=usage.default_window,
            )
        )
        over_threshold = usage.tokens >= self.context.threshold
        self._blocked = over_threshold
        if over_threshold:
            if not self._warning_sent:
                self._warning_sent = True
                sink(
                    ContextWarning(
                        f"上下文已使用 {usage.percent:.1f}%"
                        f"({usage.tokens / 1000:.1f}k / {usage.window / 1000:.0f}k)，"
                        "已接近模型上限。请执行 /compact 压缩上下文；"
                        "压缩完成前将暂停接受新的普通提示词。"
                    )
                )
        else:
            self._warning_sent = False
        return usage

    def _stream_once(self, sink: EventSink):
        """发起一次流式请求,推送增量事件,返回 (文本, 思考, tool_calls, usage)。"""
        reply_parts: List[str] = []
        reasoning_parts: List[str] = []
        tool_calls: List[dict] = []
        total_tokens: Optional[int] = None
        events = 0

        for event in self.client.stream(
            self._history, self.registry.definitions()
        ):
            if isinstance(event, StreamText):
                reply_parts.append(event.text)
                sink(TextDelta(event.text))
                events += 1
            elif isinstance(event, StreamReasoning):
                reasoning_parts.append(event.text)
                sink(ReasoningDelta(event.text))
            elif isinstance(event, StreamToolCalls):
                tool_calls = event.calls
                events += 1
            elif isinstance(event, StreamUsage):
                total_tokens = event.total_tokens or (
                    event.prompt_tokens + event.completion_tokens
                )

        if events == 0:
            raise AgentError("错误: 模型返回了空回复。")
        return "".join(reply_parts), "".join(reasoning_parts), tool_calls, total_tokens

    @staticmethod
    def _assistant_message(
        text: str,
        reasoning: str,
        tool_calls: Optional[List[dict]] = None,
    ) -> dict:
        """构造回传的 assistant 消息(关键: 标准 tool_calls + reasoning_content)。"""
        if tool_calls:
            message = {"role": "assistant", "tool_calls": tool_calls}
            if text:
                message["content"] = text
        else:
            message = {"role": "assistant", "content": text}
        if reasoning:
            message["reasoning_content"] = reasoning
        return message
