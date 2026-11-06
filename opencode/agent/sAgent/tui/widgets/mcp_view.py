"""MCP 服务器状态边栏: 展示连接状态、工具与错误。"""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label, Static

from core import McpStatus


class McpView(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Label("MCP 服务器", id="mcp-title", classes="pane-title")
        yield Static("正在加载 MCP 服务器...", id="mcp-body", markup=False)

    def update_status(self, status: McpStatus) -> None:
        if status.loading:
            self.query_one("#mcp-body", Static).update("正在连接 MCP 服务器...")
            return

        if not status.servers:
            lines = ["未配置 MCP 服务器。"]
            if status.errors:
                lines.extend(f"! {error}" for error in status.errors)
            self.query_one("#mcp-body", Static).update("\n".join(lines))
            return

        lines = []
        for server in status.servers:
            mark = "●" if server.connected else "○"
            lines.append(f"{mark} {server.name}  [{server.transport}]")
            if server.connected:
                if server.tools:
                    for tool in server.tools:
                        lines.append(f"    · {tool}")
                else:
                    lines.append("    (无工具)")
            else:
                lines.append(f"    ! {server.error or '未连接'}")
        if status.errors:
            lines.append("")
            lines.extend(f"! {error}" for error in status.errors)
        self.query_one("#mcp-body", Static).update("\n".join(lines))
