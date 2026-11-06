"""对话历史控件: 以追加式日志展示完整会话(用户/助手/工具/错误)。"""

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual.widgets import RichLog


class Transcript(RichLog):
    """append-only 消息流;写入均在 UI 线程经事件驱动触发。"""

    def __init__(self, max_lines: int = 2000, **kwargs) -> None:
        super().__init__(
            wrap=True,
            highlight=True,
            markup=True,
            auto_scroll=True,
            max_lines=max_lines,
            **kwargs,
        )

    def add_user(self, prompt: str) -> None:
        self.write(Text("你", style="bold cyan"))
        self.write(Text(prompt, style="cyan"))
        self.write("")

    def add_assistant(self, text: str, reasoning: str = "") -> None:
        body = text if text.strip() else "(空回复)"
        self.write(Panel(Markdown(body), title="sAgent", border_style="green"))
        if reasoning.strip():
            self.write(
                Text(f"思考 {len(reasoning)} 字(见右侧思考面板)\n", style="dim")
            )

    def add_tool(self, name: str, arguments: str, result: str) -> None:
        self.write(
            Panel(
                Text(result, overflow="fold"),
                title=f"[tool] {name}",
                border_style="yellow",
            )
        )

    def add_error(self, message: str) -> None:
        self.write(Text(message, style="bold red"))
        self.write("")

    def add_warning(self, message: str) -> None:
        self.write(
            Panel(
                Text(message, style="bold red"),
                title="上下文警告",
                border_style="red",
            )
        )

    def add_system(self, message: str) -> None:
        self.write(Text(message, style="dim"))
        self.write("")

    def replay(self, messages: list[dict]) -> None:
        """恢复会话后重放用户与助手消息(跳过 system/tool 细节)。"""
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            if role == "user":
                self.add_user(content)
            elif role == "assistant":
                reasoning = message.get("reasoning_content") or ""
                self.add_assistant(content, reasoning if isinstance(reasoning, str) else "")
