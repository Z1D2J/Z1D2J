"""Agent 编排层(应用层): 多轮工具往返 + 事件推送,UI 无关。

职责:
- 维护会话历史(含 reasoning_content 回传、标准格式 tool_calls 回传)
- 每轮: 流式请求 → 按事件回调推送 → 分发工具 → 回写 tool 结果 → 继续
- 出错统一转为 ErrorEvent 推送(不向上抛业务异常),TUI/Web 无需 try/except

线程模型: Agent 非线程安全,一个 turn 同一时刻只由一个线程驱动;
TUI 在 worker 线程中调用 run_turn,通过 post_message 把事件投回 UI 线程。
"""

from typing import List, Optional

from .config import Settings, load_config
from .errors import AgentError
from .events import (
    AgentEvent,
    AssistantMessage,
    ErrorEvent,
    EventSink,
    ReasoningDelta,
    TextDelta,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    TurnStarted,
    null_sink,
)
from .llm.client import LLMClient, StreamReasoning, StreamText, StreamToolCalls
from .tools import ToolRegistry, build_default_registry

SYSTEM_PROMPT = (
    "你是 sAgent,一个严谨的智能助手。"
    "需要本地文件操作或系统信息时,调用提供的工具完成任务;"
    "能直接回答时不要调用工具。回复保持简洁。"
)


class Agent:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        registry: Optional[ToolRegistry] = None,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        self.settings = settings or load_config()
        self.registry = registry or build_default_registry()
        self.client = LLMClient(self.settings)
        self.system_prompt = system_prompt
        self._history: List[dict] = [{"role": "system", "content": system_prompt}]

    @property
    def round_limit(self) -> int:
        return self.settings.max_tool_rounds

    def reset(self) -> None:
        """清空会话历史(回到 system prompt 起点)。"""
        self._history = [{"role": "system", "content": self.system_prompt}]

    def run_turn(self, prompt: str, sink: EventSink = null_sink) -> str:
        """执行一轮完整对话(含工具往返);返回最终回复文本。

        任何运行期错误都会以 ErrorEvent 推送给 sink 并返回空字符串,
        保证 UI 层无需捕获异常。
        """
        if not prompt.strip():
            sink(ErrorEvent("提示词为空,请输入内容。"))
            return ""

        sink(TurnStarted(prompt))
        turn_start = len(self._history)
        self._history.append({"role": "user", "content": prompt})

        final_text = ""
        for _ in range(self.settings.max_tool_rounds + 1):
            try:
                reply_text, reasoning_text, tool_calls = self._stream_once(sink)
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
                final_text = reply_text
                sink(AssistantMessage(reply_text, reasoning_text))
                sink(TurnFinished())
                return final_text

            self._history.append(self._assistant_message(reply_text, reasoning_text, tool_calls))
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

        sink(ErrorEvent(f"错误: 工具调用轮次过多(>{self.settings.max_tool_rounds}),本轮终止。"))
        sink(TurnFinished())
        return ""

    def _stream_once(self, sink: EventSink):
        """发起一次流式请求,推送增量事件,返回 (text, reasoning, tool_calls)。"""
        reply_parts: List[str] = []
        reasoning_parts: List[str] = []
        tool_calls: List[dict] = []
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

        if events == 0:
            raise AgentError("错误: 模型返回了空回复。")
        return "".join(reply_parts), "".join(reasoning_parts), tool_calls

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
