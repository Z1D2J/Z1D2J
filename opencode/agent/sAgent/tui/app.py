"""Textual TUI 入口实现。

线程模型:
- Input 提交 → 启动 @work(thread=True) 的 worker,在其中同步调用 agent.run_turn
- agent 通过 EventSink 推送事件 → post_message(线程安全)投递回 UI 线程
- App.on_agent_event 在 UI 线程更新 Transcript / LiveView / McpView

新增 Web/Desktop 界面时,替换的仅是本文件(事件桥接)与 widgets,core 不动。
"""

from __future__ import annotations

from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Footer, Header, Input, Static

from core import (
    Agent,
    AgentEvent,
    AssistantMessage,
    CompactionFailed,
    CompactionFinished,
    CompactionStarted,
    ContextStatus,
    ContextWarning,
    ErrorEvent,
    McpStatus,
    ReasoningDelta,
    TextDelta,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    TurnStarted,
)

from .widgets.commands import COMMANDS, CommandPalette, ComposerInput
from .widgets.compaction import CompactionScreen
from .widgets.dialogs import ConfigNoticeScreen, SessionListScreen
from .widgets.live_view import LiveView
from .widgets.mcp_view import McpView
from .widgets.transcript import Transcript


class AgentEventMsg(Message):
    """worker 线程 → UI 线程的事件载体。"""

    def __init__(self, event: AgentEvent) -> None:
        super().__init__()
        self.event = event


class sAgentApp(App[None]):
    TITLE = "sAgent"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("ctrl+q", "quit", "退出"),
        Binding("ctrl+l", "clear", "清屏", show=True),
        Binding("ctrl+r", "new_session", "新会话", show=True),
        Binding("ctrl+t", "toggle_thinking", "思考面板", show=True),
    ]

    def __init__(self, agent: Agent) -> None:
        super().__init__()
        self.agent = agent
        self.busy = False
        self.thinking_visible = self.agent.settings.thinking_visible
        self._pending_args: dict = {}
        self.context_tokens = 0
        self.context_window = 128_000
        self.context_percent = 0.0
        self.context_default_window = True

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Transcript(
                    id="transcript",
                    max_lines=self.agent.settings.transcript_max_lines,
                )
                yield CommandPalette()
                yield ComposerInput(
                    placeholder=(
                        "输入消息,回车发送;输入 / 查看命令 (Ctrl+Q 退出)"
                    ),
                    id="composer",
                )
            with Vertical(id="right"):
                yield LiveView(id="live")
                yield McpView(id="mcp")
        yield Static(self._status_text(), id="status")
        yield Footer()

    def on_mount(self) -> None:
        usage = self.agent.context_usage()
        self.context_tokens = usage.tokens
        self.context_window = usage.window
        self.context_percent = usage.percent
        self.context_default_window = usage.default_window
        if not self.thinking_visible:
            self.query_one("#live", LiveView).toggle_thinking()
        self.query_one("#composer", ComposerInput).focus()
        transcript = self.query_one("#transcript", Transcript)
        transcript.add_system(
            f"sAgent 就绪 | 模型: {self.agent.settings.model} | "
            "输入 / 查看命令, Ctrl+R 新会话, Ctrl+T 折叠思考面板"
        )
        self._update_title()
        self._refresh_status()
        if self.agent.settings.config_created:
            self.push_screen(
                ConfigNoticeScreen(self.agent.settings.config_file)
            )
        self._load_mcp()

    def _update_title(self) -> None:
        self.title = "sAgent"
        self.sub_title = f"会话 {self.agent.session_id}"

    def _status_text(self) -> str:
        state = "思考中..." if self.busy else "等待输入"
        window_text = f"{self.context_window / 1000:.0f}k"
        if self.context_default_window:
            window_text += "(默认)"
        if self.context_percent >= 60:
            style = "bold red"
        elif self.context_percent >= 40:
            style = "bold yellow"
        else:
            style = "bold green"
        usage_text = (
            f"[{style}]上下文 {self.context_tokens / 1000:.1f}k / {window_text} "
            f"({self.context_percent:.1f}%)[/]"
        )
        return (
            f" {usage_text} | 模型 {self.agent.settings.model} | "
            f"会话 {self.agent.session_id} | {state} "
        )

    def _refresh_status(self) -> None:
        self.query_one("#status", Static).update(self._status_text())

    def _sync_context(self) -> None:
        usage = self.agent.context_usage()
        self.context_tokens = usage.tokens
        self.context_window = usage.window
        self.context_percent = usage.percent
        self.context_default_window = usage.default_window
        self._refresh_status()

    def _transcript(self) -> Transcript:
        return self.query_one("#transcript", Transcript)

    def handle_palette_key(self, event) -> bool:
        palette = self.query_one(CommandPalette)
        if not palette.visible:
            return False
        if event.key in ("down", "tab"):
            palette.move(1)
        elif event.key == "up":
            palette.move(-1)
        elif event.key == "escape":
            palette.hide()
        elif event.key == "enter":
            command = palette.selected()
            palette.hide()
            self.query_one("#composer", ComposerInput).value = ""
            if command:
                self._execute_command(command)
        else:
            return False
        return True

    @on(Input.Changed, "#composer")
    def handle_composer_changed(self, event: Input.Changed) -> None:
        self.query_one(CommandPalette).refresh_for(event.value)

    @on(Input.Submitted)
    def handle_submit(self, event: Input.Submitted) -> None:
        if event.input.id != "composer":
            return
        prompt = event.value.strip()
        event.input.value = ""
        self.query_one(CommandPalette).hide()
        if not prompt:
            return
        if prompt.startswith("/"):
            self._execute_command(prompt.split()[0].lower())
            return
        if self.busy:
            self._transcript().add_system("上一轮尚未结束,已忽略本次输入。")
            return
        self.busy = True
        self._pending_args.clear()
        event.input.disabled = True
        self._refresh_status()
        self._run_turn(prompt)

    def _execute_command(self, command: str) -> None:
        if command == "/clear":
            self.action_clear()
            return
        if command == "/quit":
            self.action_quit()
            return
        if command == "/help":
            self._show_help()
            return
        if command == "/compact":
            if self.busy:
                self._transcript().add_system("当前正在处理,请稍后再压缩上下文。")
                return
            self._start_compact(self.query_one("#composer", ComposerInput))
            return
        if self.busy:
            self._transcript().add_system("当前正在处理,请稍后再执行该命令。")
            return

        if command == "/new":
            session_id = self.agent.new_session()
            self._transcript().clear()
            self._transcript().add_system(f"已开启新会话 #{session_id}。")
            self.query_one("#live", LiveView).reset_view(self.thinking_visible)
            self._sync_context()
            self._update_title()
        elif command == "/resume":
            sessions = self.agent.session_store.list_sessions()
            if not sessions:
                self._transcript().add_system("暂无已保存的会话。")
                return
            self.push_screen(SessionListScreen(sessions), self._resume_selected)
        elif command == "/save":
            try:
                info = self.agent.save_session()
            except OSError as exc:
                self._transcript().add_error(f"保存会话失败: {exc}")
                return
            self._transcript().add_system(
                f"已保存会话 #{info.id} -> {info.path}"
            )
        elif command == "/status":
            self._show_status()
        elif command == "/mcp":
            self._show_mcp_status()
        else:
            self._transcript().add_system(
                f"未知命令: {command}。输入 / 查看可用命令。"
            )

    def _resume_selected(self, session_id: Optional[str]) -> None:
        if not session_id or self.busy:
            return
        try:
            info = self.agent.resume_session(session_id)
        except OSError as exc:
            self._transcript().add_error(f"恢复会话失败: {exc}")
            return
        transcript = self._transcript()
        transcript.clear()
        transcript.replay(self.agent.history_snapshot())
        transcript.add_system(
            f"已恢复会话 #{info.id} | {info.title} | {info.message_count} 条消息"
        )
        self.query_one("#live", LiveView).reset_view(self.thinking_visible)
        self._sync_context()
        self._update_title()

    def _show_help(self) -> None:
        lines = ["可用命令:"]
        lines.extend(
            f"  {command.name:<9} {command.description}" for command in COMMANDS
        )
        self._transcript().add_system("\n".join(lines))

    def _show_status(self) -> None:
        status = self.agent.mcp_status_event()
        connected = sum(1 for server in status.servers if server.connected)
        tools = sum(len(server.tools) for server in status.servers)
        mcp_text = (
            "正在加载..."
            if status.loading
            else f"{connected}/{len(status.servers)} 已连接, 共 {tools} 个工具"
        )
        lines = [
            f"会话: #{self.agent.session_id}",
            f"上下文: {self.context_tokens / 1000:.1f}k / "
            f"{self.context_window / 1000:.0f}k ({self.context_percent:.1f}%)",
            f"MCP: {mcp_text}",
            f"自动保存: {'开启' if self.agent.settings.auto_save_sessions else '关闭'}",
        ]
        if status.errors:
            lines.extend(f"  ! {error}" for error in status.errors)
        self._transcript().add_system("\n".join(lines))

    def _show_mcp_status(self) -> None:
        status = self.agent.mcp_status_event()
        if status.loading:
            self._transcript().add_system("MCP 正在加载,请稍后查看。")
            return
        if not status.servers:
            self._transcript().add_system("未配置 MCP 服务器。")
            return
        lines = []
        for server in status.servers:
            mark = "已连接" if server.connected else "未连接"
            lines.append(
                f"{server.name} [{server.transport}] {mark}"
                f" | 工具 {len(server.tools)} 个"
            )
        if status.errors:
            lines.extend(f"! {error}" for error in status.errors)
        self._transcript().add_system("\n".join(lines))

    def _start_compact(self, input_widget: Input) -> None:
        self.busy = True
        self._pending_args.clear()
        input_widget.disabled = True
        self._refresh_status()
        self._run_compact()

    @work(thread=True, group="turn")
    def _run_turn(self, prompt: str) -> None:
        """worker 线程: 仅调用 core,事件经 post_message 回 UI 线程。"""
        self.agent.run_turn(prompt, sink=lambda e: self.post_message(AgentEventMsg(e)))

    @work(thread=True, group="turn")
    def _run_compact(self) -> None:
        self.agent.compact(sink=lambda e: self.post_message(AgentEventMsg(e)))

    @work(thread=True, group="mcp")
    def _load_mcp(self) -> None:
        self.agent.load_mcp(sink=lambda e: self.post_message(AgentEventMsg(e)))

    def on_agent_event_msg(self, msg: AgentEventMsg) -> None:
        self._dispatch(msg.event)

    def _dispatch(self, event: AgentEvent) -> None:
        transcript = self._transcript()
        live = self.query_one("#live", LiveView)

        if isinstance(event, TurnStarted):
            transcript.add_user(event.prompt)
            live.reset_view(self.thinking_visible)
        elif isinstance(event, TextDelta):
            live.append_reply(event.text)
        elif isinstance(event, ReasoningDelta):
            if self.thinking_visible:
                live.append_thinking(event.text)
        elif isinstance(event, ToolCallStarted):
            self._pending_args[event.name] = event.arguments
            live.add_tool(event.name, event.arguments)
        elif isinstance(event, ToolCallFinished):
            args = self._pending_args.pop(event.name, "")
            transcript.add_tool(event.name, args, event.result)
        elif isinstance(event, AssistantMessage):
            transcript.add_assistant(event.text, event.reasoning)
            live.finish_reply(event.text)
        elif isinstance(event, ErrorEvent):
            transcript.add_error(event.message)
        elif isinstance(event, ContextStatus):
            self.context_tokens = event.tokens
            self.context_window = event.window
            self.context_percent = event.percent
            self.context_default_window = event.default_window
            self._refresh_status()
        elif isinstance(event, ContextWarning):
            transcript.add_warning(event.message)
        elif isinstance(event, CompactionStarted):
            transcript.add_system("开始压缩上下文：正在保存原始上下文并生成摘要...")
        elif isinstance(event, CompactionFinished):
            transcript.add_system(
                f"上下文压缩完成，原始上下文已保存为归档 {event.archive_id}。"
            )
            self._finish_busy()
            self.push_screen(
                CompactionScreen(
                    archive_id=event.archive_id,
                    original=event.original,
                    summary=event.summary,
                )
            )
        elif isinstance(event, CompactionFailed):
            transcript.add_error(f"上下文压缩失败: {event.message}")
            self._finish_busy()
        elif isinstance(event, McpStatus):
            self.query_one("#mcp", McpView).update_status(event)
            if not event.loading and event.errors:
                transcript.add_system("MCP: " + " | ".join(event.errors))
        elif isinstance(event, TurnFinished):
            self._finish_busy()

    def _finish_busy(self) -> None:
        self.busy = False
        input_widget = self.query_one("#composer", ComposerInput)
        input_widget.disabled = False
        input_widget.focus()
        self._refresh_status()

    def action_clear(self) -> None:
        transcript = self._transcript()
        transcript.clear()
        transcript.add_system("显示已清空(会话历史仍保留)。")

    def action_new_session(self) -> None:
        if self.busy:
            return
        had_dialogue = self.agent.has_dialogue()
        session_id = self.agent.new_session()
        transcript = self._transcript()
        transcript.clear()
        suffix = "(旧会话已自动保存)" if had_dialogue else ""
        transcript.add_system(f"已开启新会话 #{session_id}{suffix}。")
        self.query_one("#live", LiveView).reset_view(self.thinking_visible)
        self._sync_context()
        self._update_title()

    def action_quit(self) -> None:
        if not self.busy and self.agent.has_dialogue():
            try:
                self.agent.save_session()
            except OSError:
                pass
        self.agent.close()
        self.exit()

    def action_toggle_thinking(self) -> None:
        self.thinking_visible = not self.thinking_visible
        self.query_one("#live", LiveView).toggle_thinking()
