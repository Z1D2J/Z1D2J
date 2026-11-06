"""MCP Client: 连接外部 MCP Server,发现工具并转发 Function Calling。

实现要点:
- 使用 MCP Python SDK 的标准接口: stdio_client / streamable_http_client + ClientSession
- 所有异步连接与调用都运行在后台事件循环线程中,对上层保持同步 API
- 连接失败只记录错误,不影响本地工具与其他 MCP Server
- LLM 暴露名与 (Server, 原始工具名) 的映射保存在 McpManager 中
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import re
import threading
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .config import (
    DEFAULT_CALL_TIMEOUT,
    DEFAULT_CONNECT_TIMEOUT,
    McpServerConfig,
    default_config_path,
    load_mcp_config,
)
from ..tools.base import ToolRegistry, ToolSpec, parse_arguments

try:  # MCP SDK 可选: 未安装时本地工具仍可正常使用
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    _MCP_IMPORT_ERROR: Optional[str] = None
except Exception as exc:  # pragma: no cover - 取决于运行环境
    ClientSession = None  # type: ignore[assignment]
    StdioServerParameters = None  # type: ignore[assignment]
    stdio_client = None  # type: ignore[assignment]
    _MCP_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

try:
    from mcp.client.streamable_http import streamable_http_client as _streamable_http_client
except ImportError:  # pragma: no cover - 旧版 SDK 走下面的兼容分支
    _streamable_http_client = None

try:
    from mcp.client.streamable_http import streamablehttp_client as _legacy_streamable_http_client
except ImportError:
    _legacy_streamable_http_client = None

MAX_TOOL_NAME_LENGTH = 64
MAX_RESULT_CHARS = 30000
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")


class McpOperationError(RuntimeError):
    """MCP 连接或调用失败,message 为可直接展示的文案。"""


def _exception_text(exc: BaseException) -> str:
    """把异常(含 ExceptionGroup)压成一段可读文案。"""
    if isinstance(exc, BaseExceptionGroup):  # type: ignore[attr-defined]
        parts = []
        for item in exc.exceptions:  # type: ignore[attr-defined]
            text = _exception_text(item)
            if text and text not in parts:
                parts.append(text)
        return " | ".join(parts)
    text = str(exc).strip()
    name = type(exc).__name__
    return f"{name}: {text}" if text else name


@asynccontextmanager
async def _open_stdio(config: McpServerConfig):
    if stdio_client is None or StdioServerParameters is None:
        raise McpOperationError("MCP Python SDK 未安装或不完整,无法使用 stdio 传输。")
    params = StdioServerParameters(
        command=config.command,
        args=list(config.args),
        env=dict(config.env) or None,
        cwd=config.cwd,
    )
    async with stdio_client(params) as streams:
        yield streams


@asynccontextmanager
async def _open_streamable_http(config: McpServerConfig):
    headers = dict(config.headers) or None
    if _streamable_http_client is not None:
        # MCP SDK 2.x: 通过自定义 httpx2.AsyncClient 传入 Authorization 等请求头。
        import httpx2

        timeout = httpx2.Timeout(30.0, read=max(60.0, config.call_timeout))
        async with httpx2.AsyncClient(headers=headers, timeout=timeout) as client:
            async with _streamable_http_client(config.url, http_client=client) as streams:
                yield streams
        return

    if _legacy_streamable_http_client is not None:
        # MCP SDK 1.x: 请求头与超时直接作为参数传入。
        async with _legacy_streamable_http_client(
            config.url,
            headers=headers,
            timeout=30.0,
            sse_read_timeout=max(60.0, config.call_timeout),
        ) as streams:
            yield streams
        return

    raise McpOperationError("当前 MCP Python SDK 未提供 Streamable HTTP 客户端。")


@dataclass
class McpTool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None


@dataclass
class McpToolRef:
    server: str
    tool: str


@dataclass(frozen=True)
class McpServerStatus:
    name: str
    transport: str
    connected: bool
    tools: Tuple[str, ...] = ()
    error: str = ""


class _ServerConnection:
    def __init__(self, config: McpServerConfig):
        self.config = config
        self.tools: List[McpTool] = []
        self._stack: Optional[AsyncExitStack] = None
        self._session: Any = None
        self.connected = False

    async def open(self) -> None:
        stack = AsyncExitStack()
        self._stack = stack
        try:
            transport = (
                _open_stdio(self.config)
                if self.config.transport == "stdio"
                else _open_streamable_http(self.config)
            )
            streams = await stack.enter_async_context(transport)
            read_stream, write_stream = streams[0], streams[1]
            session = ClientSession(read_stream, write_stream)
            self._session = await stack.enter_async_context(session)
            await self._session.initialize()
            self.tools = await self._list_tools()
            self.connected = True
        except BaseException:
            self._session = None
            self._stack = None
            await stack.aclose()
            raise

    async def _list_tools(self) -> List[McpTool]:
        tools: List[McpTool] = []
        cursor: Optional[str] = None
        while True:
            try:
                result = await self._session.list_tools(
                    params=None if cursor is None else _pagination_params(cursor)
                )
            except TypeError:
                # MCP SDK 1.x: list_tools(cursor=None)
                result = await self._session.list_tools(cursor=cursor)
            for tool in getattr(result, "tools", None) or []:
                tools.append(_convert_tool(tool))
            cursor = getattr(result, "next_cursor", None)
            if not cursor:
                break
        return tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]):
        if not self.connected or self._session is None:
            raise McpOperationError(f"MCP Server {self.config.name!r} 尚未连接。")
        return await self._session.call_tool(name, arguments)

    async def close(self) -> None:
        self.connected = False
        self._session = None
        stack, self._stack = self._stack, None
        if stack is not None:
            await stack.aclose()


def _pagination_params(cursor: str):
    try:
        from mcp.types import PaginatedRequestParams

        return PaginatedRequestParams(cursor=cursor)
    except Exception:  # pragma: no cover - 由调用方 TypeError 分支兜底
        return None


def _convert_tool(tool: Any) -> McpTool:
    schema = getattr(tool, "input_schema", None)
    if schema is None:
        schema = getattr(tool, "inputSchema", None)
    if not isinstance(schema, dict) or not schema:
        schema = {"type": "object", "properties": {}}
    elif "type" not in schema:
        schema = {"type": "object", **schema}
    output_schema = getattr(tool, "output_schema", None)
    if output_schema is None:
        output_schema = getattr(tool, "outputSchema", None)
    description = getattr(tool, "description", None) or ""
    return McpTool(
        name=str(getattr(tool, "name", "") or ""),
        description=str(description),
        input_schema=schema,
        output_schema=output_schema if isinstance(output_schema, dict) else None,
    )


def _sanitize_name(value: str, max_length: int = MAX_TOOL_NAME_LENGTH) -> str:
    cleaned = _SAFE_NAME.sub("_", value.strip()).strip("_-")
    if not cleaned:
        cleaned = "tool"
    return cleaned[:max_length]


def _with_suffix(base: str, suffix: str, max_length: int = MAX_TOOL_NAME_LENGTH) -> str:
    room = max_length - len(suffix)
    return (base[:room] if room > 0 else "") + suffix


def _unique_tool_name(
    server: str, tool: str, used: Sequence[str], max_length: int = MAX_TOOL_NAME_LENGTH
) -> str:
    """优先使用原始工具名;冲突时加上 Server 名称前缀,再冲突则追加序号。"""
    base = _sanitize_name(tool, max_length)
    if base not in used:
        return base

    prefixed = _sanitize_name(f"{server}__{tool}", max_length)
    if prefixed not in used:
        return prefixed

    index = 2
    while True:
        candidate = _with_suffix(prefixed, f"_{index}", max_length)
        if candidate not in used:
            return candidate
        index += 1


def _attr(obj: Any, *names: str) -> Any:
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None


def _format_block(block: Any) -> str:
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        block_type = block.get("type")
        if block_type == "text":
            return str(block.get("text") or "")
        if block_type in ("image", "audio"):
            data = str(block.get("data") or "")
            mime = block.get("mimeType") or block.get("mime_type") or ""
            label = "图片" if block_type == "image" else "音频"
            return f"[{label}内容: {mime or '未知类型'}, base64 长度 {len(data)},已省略]"
        if block_type == "resource":
            resource = block.get("resource") or {}
            text = resource.get("text") if isinstance(resource, dict) else None
            if text is not None:
                return str(text)
            uri = resource.get("uri", "") if isinstance(resource, dict) else ""
            return f"[嵌入资源: {uri}]"
        if block_type == "resource_link":
            return f"[资源链接: {block.get('name') or ''} {block.get('uri') or ''}]".strip()
        return json.dumps(block, ensure_ascii=False)

    block_type = _attr(block, "type")
    if block_type == "text":
        return str(_attr(block, "text") or "")
    if block_type in ("image", "audio"):
        data = str(_attr(block, "data") or "")
        mime = _attr(block, "mime_type", "mimeType") or ""
        label = "图片" if block_type == "image" else "音频"
        return f"[{label}内容: {mime or '未知类型'}, base64 长度 {len(data)},已省略]"
    if block_type == "resource":
        resource = _attr(block, "resource")
        text = _attr(resource, "text") if resource is not None else None
        if text is not None:
            return str(text)
        uri = _attr(resource, "uri") if resource is not None else ""
        return f"[嵌入资源: {uri or ''}]"
    if block_type == "resource_link":
        name = _attr(block, "name") or ""
        uri = _attr(block, "uri") or ""
        return f"[资源链接: {name} {uri}]".strip()

    try:
        dumped = block.model_dump() if hasattr(block, "model_dump") else None
    except Exception:
        dumped = None
    if isinstance(dumped, dict):
        return _format_block(dumped)
    return str(block)


def _truncate(text: str, max_chars: int = MAX_RESULT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...(MCP 工具结果过长,已截断)"


def _format_call_result(
    result: Any,
    server: str,
    tool: str,
    max_chars: int = MAX_RESULT_CHARS,
) -> str:
    parts: List[str] = []
    for block in getattr(result, "content", None) or []:
        text = _format_block(block)
        if text:
            parts.append(text)

    structured = getattr(result, "structured_content", None)
    if structured is None:
        structured = getattr(result, "structuredContent", None)
    if structured is not None:
        try:
            structured_text = json.dumps(structured, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            structured_text = str(structured)
        parts.append("结构化数据:\n" + structured_text)

    text = "\n".join(parts).strip() or "(MCP 工具没有返回内容)"
    text = _truncate(text, max_chars)
    if getattr(result, "is_error", False):
        return f"MCP 工具返回错误 [{server}/{tool}]:\n{text}"
    return text


class _AsyncRuntime:
    """独占一个后台线程运行 asyncio 事件循环,把异步 MCP 调用桥接为同步调用。"""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="sAgent-MCP", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    def submit(self, coro, timeout: Optional[float]):
        loop = self._loop
        if loop is None or not loop.is_running():
            coro.close()
            raise McpOperationError("MCP 后台事件循环未运行。")
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise McpOperationError(f"MCP 操作超时(>{timeout:g}s)。" if timeout else "MCP 操作超时。") from exc

    def stop(self) -> None:
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if self._thread.is_alive():
            self._thread.join(timeout=5)


class McpManager:
    """管理 .mcp.json 中的所有 Server 连接与工具映射。"""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        default_connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        default_call_timeout: float = DEFAULT_CALL_TIMEOUT,
        max_tool_name_length: int = MAX_TOOL_NAME_LENGTH,
        max_result_chars: int = MAX_RESULT_CHARS,
    ):
        self.config_path = Path(config_path) if config_path is not None else default_config_path()
        self.default_connect_timeout = default_connect_timeout
        self.default_call_timeout = default_call_timeout
        self.max_tool_name_length = max_tool_name_length
        self.max_result_chars = max_result_chars
        self.errors: List[str] = []
        self._runtime: Optional[_AsyncRuntime] = None
        self._configs: List[McpServerConfig] = []
        self._connections: List[_ServerConnection] = []
        self._failed: Dict[str, str] = {}
        self._tool_map: Dict[str, McpToolRef] = {}
        self._registered = False
        self._started = False
        self._closed = False

    @property
    def tool_mapping(self) -> Dict[str, McpToolRef]:
        """LLM 暴露的工具名 -> (MCP Server 名称, 原始工具名)。"""
        return dict(self._tool_map)

    @property
    def started(self) -> bool:
        return self._started

    def status(self) -> List[McpServerStatus]:
        """返回所有已配置 Server 的连接状态与工具名,供 TUI 侧栏展示。"""
        connection_map = {
            connection.config.name: connection for connection in self._connections
        }
        result: List[McpServerStatus] = []
        for config in self._configs:
            connection = connection_map.get(config.name)
            if connection is not None and connection.connected:
                result.append(
                    McpServerStatus(
                        name=config.name,
                        transport=config.transport,
                        connected=True,
                        tools=tuple(tool.name for tool in connection.tools),
                    )
                )
            else:
                result.append(
                    McpServerStatus(
                        name=config.name,
                        transport=config.transport,
                        connected=False,
                        error=self._failed.get(config.name, "尚未连接"),
                    )
                )
        return result

    def start(self) -> List[str]:
        """读取配置并连接全部 Server;返回错误列表(不抛异常)。"""
        if self._started:
            return list(self.errors)
        self._started = True

        configs, errors = load_mcp_config(
            self.config_path,
            self.default_connect_timeout,
            self.default_call_timeout,
        )
        self._configs = configs
        self.errors.extend(errors)
        if not configs:
            return list(self.errors)

        if _MCP_IMPORT_ERROR is not None:
            self.errors.append(f"MCP Python SDK 不可用: {_MCP_IMPORT_ERROR}")
            for config in configs:
                self._failed[config.name] = "MCP Python SDK 不可用"
            return list(self.errors)

        self._runtime = _AsyncRuntime()
        for config in configs:
            connection = _ServerConnection(config)
            try:
                self._runtime.submit(connection.open(), config.connect_timeout)
            except Exception as exc:
                reason = _exception_text(exc)
                self.errors.append(f"MCP Server {config.name!r} 连接失败: {reason}")
                self._failed[config.name] = reason
                try:
                    self._runtime.submit(connection.close(), 5.0)
                except Exception:
                    pass
                continue
            self._connections.append(connection)

        if not self._connections:
            self._runtime.stop()
            self._runtime = None
        return list(self.errors)

    def register_tools(self, registry: ToolRegistry) -> None:
        """把已连接 Server 的工具注册到本地注册表(名称冲突时自动加前缀)。"""
        if self._registered:
            return
        self._registered = True

        used = set(registry.names())
        for connection in self._connections:
            server = connection.config.name
            for tool in connection.tools:
                if not tool.name:
                    continue
                exposed = _unique_tool_name(
                    server, tool.name, used, self.max_tool_name_length
                )
                used.add(exposed)
                self._tool_map[exposed] = McpToolRef(server=server, tool=tool.name)
                description = f"[MCP:{server}] {tool.description or '来自 MCP Server 的工具'}"
                registry.register(
                    ToolSpec(
                        name=exposed,
                        description=description,
                        parameters=tool.input_schema,
                        handler=self._make_handler(connection, tool.name),
                    )
                )

    def _make_handler(self, connection: _ServerConnection, tool_name: str):
        def handler(arguments: str) -> str:
            return self._dispatch(connection, tool_name, arguments)

        return handler

    def _dispatch(self, connection: _ServerConnection, tool_name: str, arguments: str) -> str:
        args = parse_arguments(arguments)
        if args is None:
            return "参数解析失败: arguments 不是合法的 JSON 对象。"

        runtime = self._runtime
        if runtime is None:
            return f"MCP 工具调用失败 [{connection.config.name}/{tool_name}]: MCP 客户端未启动。"
        try:
            result = runtime.submit(
                connection.call_tool(tool_name, args), connection.config.call_timeout
            )
        except Exception as exc:
            return (
                f"MCP 工具调用失败 [{connection.config.name}/{tool_name}]: "
                f"{_exception_text(exc)}"
            )
        return _format_call_result(
            result, connection.config.name, tool_name, self.max_result_chars
        )

    def close(self) -> None:
        """关闭所有 MCP 会话与后台事件循环(幂等)。"""
        if self._closed:
            return
        self._closed = True

        runtime = self._runtime
        if runtime is not None:
            for connection in self._connections:
                try:
                    runtime.submit(connection.close(), 5.0)
                except Exception:
                    pass
            runtime.stop()
            self._runtime = None
        self._connections.clear()
