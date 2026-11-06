"""上下文压缩前后的对照面板(浮动 Modal)。"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class CompactionScreen(ModalScreen[None]):
    """左右两栏展示压缩前原文与压缩后摘要,支持独立滚动。"""

    BINDINGS = [("escape", "close", "关闭")]

    def __init__(self, archive_id: str, original: str, summary: str) -> None:
        super().__init__()
        self.archive_id = archive_id
        self.original = original or "(无原始内容)"
        self.summary = summary or "(无压缩结果)"

    def compose(self) -> ComposeResult:
        with Vertical(id="compaction-dialog"):
            yield Static(
                f"上下文压缩预览 · 归档 {self.archive_id}",
                id="compaction-title",
            )
            with Horizontal(id="compaction-columns"):
                with Vertical(id="compaction-left", classes="compaction-col"):
                    yield Static("压缩前原文", classes="compaction-heading")
                    with VerticalScroll(classes="compaction-scroll"):
                        yield Static(self.original, classes="compaction-body", markup=False)
                with Vertical(classes="compaction-col"):
                    yield Static("压缩后结果", classes="compaction-heading")
                    with VerticalScroll(classes="compaction-scroll"):
                        yield Static(self.summary, classes="compaction-body", markup=False)
            yield Button("关闭", id="compaction-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "compaction-close":
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()
