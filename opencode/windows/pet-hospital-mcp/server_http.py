import uvicorn
from mcp.server import MCPServer
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from tools.pets import register_tools

import asyncio
from sse_starlette.sse import EventSourceResponse


def create_server() -> MCPServer:
    mcp = MCPServer(name="pet-hospital-mcp", version="1.0.0")
    register_tools(mcp)
    return mcp


mcp = create_server()


async def handle_sse(request):
    async with mcp.session_manager.run_streamable_http_session(
        scope=request.scope,
        receive=request.receive,
        send=request._send,
    ):
        pass


app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
    ],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
