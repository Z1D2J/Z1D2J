"""Textual TUI 入口实现。

线程模型:
- Input 提交 → 启动 @work(thread=True) 的 worker,在其中同步调用 agent.run_turn
- agent 通过 EventSink 推送事件 → post_message(线程安全)投递回 UI 线程
- App.on_agent_event 在 UI 线程更新 Transcript / LiveView

新增 Web/Desktop 界面时,替换的仅是本文件(事件桥接)与 widgets,core 不动。
"""

from __future__ import annotations

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
    ErrorEvent,
    ReasoningDelta,
    TextDelta,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    TurnStarted,
)

from .widgets.live_view import LiveView
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
        Binding("ctrl+r", "reset", "重置会话", show=True),
        Binding("ctrl+t", "toggle_thinking", "思考面板", show=True),
    ]

    def __init__(self, agent: Agent) -> None:
        super().__init__()
        self.agent = agent
        self.busy = False
        self.thinking_visible = True
        self._pending_args: dict = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Transcript(id="transcript")
                yield Input(
                    placeholder="输入消息,回车发送 (Ctrl+Q 退出)",
                    id="composer",
                )
            yield LiveView(id="live")
        yield Static(self._status_text(), id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#composer", Input).focus()
        self.query_one("#transcript", Transcript).add_system(
            f"sAgent 就绪 | 模型: {self.agent.settings.model} | "
            "Ctrl+R 重置会话, Ctrl+T 折叠思考面板"
        )

    def _status_text(self) -> str:
        state = "思考中..." if self.busy else "等待输入"
        return f" 模型 {self.agent.settings.model} | {state} "

    def _refresh_status(self) -> None:
        self.query_one("#status", Static).update(self._status_text())

    @on(Input.Submitted)
    def handle_submit(self, event: Input.Submitted) -> None:
        if event.input.id != "composer":
            return
        prompt = event.value.strip()
        event.input.value = ""
        if not prompt:
            return
        if self.busy:
            self.query_one("#transcript", Transcript).add_system(
                "上一轮尚未结束,已忽略本次输入。"
            )
            return
        self.busy = True
        self._pending_args.clear()
        event.input.disabled = True
        self._refresh_status()
        self._run_turn(prompt)

    @work(thread=True, group="turn")
    def _run_turn(self, prompt: str) -> None:
        """worker 线程: 仅调用 core,事件经 post_message 回 UI 线程。"""
        self.agent.run_turn(prompt, sink=lambda e: self.post_message(AgentEventMsg(e)))

    def on_agent_event_msg(self, msg: AgentEventMsg) -> None:
        self._dispatch(msg.event)

    def _dispatch(self, event: AgentEvent) -> None:
        transcript = self.query_one("#transcript", Transcript)
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
        elif isinstance(event, TurnFinished):
            self.busy = False
            input_widget = self.query_one("#composer", Input)
            input_widget.disabled = False
            input_widget.focus()
            self._refresh_status()

    def action_clear(self) -> None:
        transcript = self.query_one("#transcript", Transcript)
        transcript.clear()
        transcript.add_system("显示已清空(会话历史仍保留,Ctrl+R 可重置)。")

    def action_reset(self) -> None:
        if self.busy:
            return
        self.agent.reset()
        transcript = self.query_one("#transcript", Transcript)
        transcript.clear()
        transcript.add_system("会话已重置,历史清空。")
        self.query_one("#live", LiveView).reset_view(self.thinking_visible)

    def action_toggle_thinking(self) -> None:
        self.thinking_visible = not self.thinking_visible
        self.query_one("#live", LiveView).toggle_thinking()
