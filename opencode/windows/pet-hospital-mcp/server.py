import asyncio
from mcp.server import MCPServer
from tools.pets import register_tools


def create_server() -> MCPServer:
    """创建并配置 MCP Server"""
    mcp = MCPServer(
        name="pet-hospital-mcp",
        version="1.0.0",
    )

    register_tools(mcp)

    return mcp


async def main():
    """启动 STDIO 服务器"""
    mcp = create_server()
    await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
