"""斜杠命令定义、补全面板与可拦截按键的输入框。"""

from dataclasses import dataclass
from typing import List, Optional, Sequence

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option


@dataclass(frozen=True)
class SlashCommand:
    name: str
    description: str


COMMANDS: Sequence[SlashCommand] = (
    SlashCommand("/new", "新建会话(自动保存当前会话)"),
    SlashCommand("/resume", "打开会话列表并恢复历史会话"),
    SlashCommand("/save", "立即保存当前会话"),
    SlashCommand("/quit", "保存并退出 sAgent"),
    SlashCommand("/compact", "压缩上下文并归档原始记录"),
    SlashCommand("/status", "查看会话、上下文与 MCP 状态"),
    SlashCommand("/mcp", "查看 MCP 服务器与工具"),
    SlashCommand("/help", "显示全部命令"),
    SlashCommand("/clear", "清空屏幕(不删除历史)"),
)


def filter_commands(text: str) -> List[SlashCommand]:
    if not text.startswith("/") or " " in text:
        return []
    token = text[1:].casefold()
    return [command for command in COMMANDS if command.name[1:].startswith(token)]


class CommandPalette(Vertical):
    """输入框上方的命令补全面板,不抢输入框焦点。"""

    def __init__(self, **kwargs) -> None:
        super().__init__(id="command-palette", **kwargs)
        self.display = False
        self._ids: List[str] = []

    def compose(self) -> ComposeResult:
        yield Label(
            "命令 (↑/↓ 或 Tab 选择, Enter 执行, Esc 关闭)",
            id="palette-title",
        )
        yield OptionList(id="command-options")

    def refresh_for(self, text: str) -> None:
        matches = filter_commands(text)
        if not matches:
            self.hide()
            return
        option_list = self.query_one("#command-options", OptionList)
        option_list.clear_options()
        self._ids = [command.name for command in matches]
        option_list.add_options(
            [
                Option(
                    f"{command.name}   {command.description}",
                    id=command.name,
                )
                for command in matches
            ]
        )
        option_list.highlighted = 0
        self.display = True

    def hide(self) -> None:
        self.display = False

    @property
    def visible(self) -> bool:
        return self.display and bool(self._ids)

    def move(self, delta: int) -> None:
        if not self.visible:
            return
        option_list = self.query_one("#command-options", OptionList)
        count = len(self._ids)
        current = option_list.highlighted or 0
        option_list.highlighted = (current + delta) % count

    def selected(self) -> Optional[str]:
        if not self.visible:
            return None
        option_list = self.query_one("#command-options", OptionList)
        index = option_list.highlighted or 0
        if 0 <= index < len(self._ids):
            return self._ids[index]
        return None


class ComposerInput(Input):
    """在 Input 处理 Enter/Esc 之前,让 App 有机会接管命令面板按键。"""

    async def _on_key(self, event: events.Key) -> None:
        handler = getattr(self.app, "handle_palette_key", None)
        if handler is not None and handler(event):
            event.stop()
            event.prevent_default()
            return
        await super()._on_key(event)
