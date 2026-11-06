"""会话选择与配置提示弹窗。"""

from typing import List, Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from rich.text import Text
from textual.widgets import Button, Label, OptionList, Static
from textual.widgets.option_list import Option

from core import SessionInfo


class SessionListScreen(ModalScreen[Optional[str]]):
    """列出已保存会话;选择后返回 session id,ESC 返回 None。"""

    BINDINGS = [Binding("escape", "cancel", "取消")]

    def __init__(self, sessions: List[SessionInfo]) -> None:
        super().__init__()
        self.sessions = sessions

    def compose(self) -> ComposeResult:
        with Vertical(id="session-dialog"):
            yield Label("恢复会话", id="session-title")
            options = [
                Option(
                    Text(
                        f"{info.updated_at or info.created_at}  "
                        f"{info.title}  ({info.message_count} 条)  #{info.id}"
                    ),
                    id=info.id,
                )
                for info in self.sessions
            ]
            if not options:
                options = [Option("(暂无已保存会话)", id="none", disabled=True)]
            yield OptionList(*options, id="session-options")
            yield Static(
                "↑/↓ 选择, Enter 恢复, Esc 取消", id="session-hint"
            )

    def on_mount(self) -> None:
        self.query_one("#session-options", OptionList).focus()

    @on(OptionList.OptionSelected, "#session-options")
    def choose(self, event: OptionList.OptionSelected) -> None:
        if event.option.id == "none":
            return
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfigNoticeScreen(ModalScreen[None]):
    """首次自动生成 config.ini 后的提示。"""

    BINDINGS = [
        Binding("escape", "close", "关闭"),
        Binding("enter", "close", "关闭"),
    ]

    def __init__(self, config_file: str) -> None:
        super().__init__()
        self.config_file = config_file

    def compose(self) -> ComposeResult:
        with Vertical(id="config-dialog"):
            yield Label("已生成配置文件", id="config-title")
            yield Static(
                f"未找到 config.ini,已在以下位置生成一份带 mock 值的配置:\n\n"
                f"{self.config_file}\n\n"
                "请修改 [api] 段的 key / base_url / model,以及 [search] 段的"
                "搜索 Key,然后重新启动 sAgent。\n\n"
                "MCP 服务器请在项目目录的 .mcp.json 中配置。",
                id="config-body",
                markup=False,
            )
            yield Button("知道了", id="config-ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#config-ok", Button).focus()

    @on(Button.Pressed, "#config-ok")
    def close_dialog(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
