"""右侧实时面板: 流式回复、思考过程、工具活动的即时视图。"""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label, Static

THINKING_PLACEHOLDER = "(暂无思考内容)"
TOOLS_PLACEHOLDER = "(本轮无工具调用)"


class LiveView(VerticalScroll):
    """承载三个区块: 思考 / 回复 / 工具状态。

    文本以内部缓冲累积后整段 update,避免依赖 Static 内部渲染状态。
    """

    _thinking = ""
    _reply = ""
    _tools = ""

    def compose(self) -> ComposeResult:
        yield Label("思考过程", id="thinking-title", classes="pane-title")
        yield Static(THINKING_PLACEHOLDER, id="live-thinking", classes="thinking")
        yield Label("实时回复", id="reply-title", classes="pane-title")
        yield Static("", id="live-reply")
        yield Label("工具活动", id="tools-title", classes="pane-title")
        yield Static(TOOLS_PLACEHOLDER, id="live-tools", classes="tools")

    def reset_view(self, thinking_visible: bool) -> None:
        self._thinking = ""
        self._reply = ""
        self._tools = ""
        self.query_one("#live-thinking", Static).update(
            "(思考中...)" if thinking_visible else "(思考内容已隐藏)"
        )
        self.query_one("#live-reply", Static).update("")
        self.query_one("#live-tools", Static).update(TOOLS_PLACEHOLDER)
        self.scroll_end(animate=False)

    def append_thinking(self, text: str) -> None:
        self._thinking += text
        self.query_one("#live-thinking", Static).update(self._thinking)
        self.scroll_end(animate=False)

    def append_reply(self, text: str) -> None:
        self._reply += text
        self.query_one("#live-reply", Static).update(self._reply)
        self.scroll_end(animate=False)

    def add_tool(self, name: str, arguments: str) -> None:
        self._tools += f"\n▶ {name}({arguments[:120]})"
        self.query_one("#live-tools", Static).update(
            self._tools.lstrip("\n") or TOOLS_PLACEHOLDER
        )
        self.scroll_end(animate=False)

    def finish_reply(self, text: str) -> None:
        self._reply = text if text.strip() else "(空回复)"
        self.query_one("#live-reply", Static).update(self._reply)

    def toggle_thinking(self) -> None:
        self.query_one("#thinking-title", Label).toggle_class("hidden")
        self.query_one("#live-thinking", Static).toggle_class("hidden")
