"""MCP Server 配置加载(读取当前项目目录下的 .mcp.json)。

只负责把配置文件解析成 McpServerConfig,不建立连接,也不 import MCP SDK。
配置错误与单个 Server 的错误都通过返回值上报,不影响其他 Server。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MCP_CONFIG_FILE = ".mcp.json"
DEFAULT_CONNECT_TIMEOUT = 20.0
DEFAULT_CALL_TIMEOUT = 120.0

_HTTP_TYPES = {"streamable_http", "streamable-http", "streamablehttp", "http"}
_STDIO_TYPES = {"stdio"}


class McpConfigError(Exception):
    """MCP 配置文件无法读取或整体格式错误。"""


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    transport: str
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    call_timeout: float = DEFAULT_CALL_TIMEOUT


def default_config_path() -> Path:
    """当前项目(启动 sAgent 时的工作目录)下的 .mcp.json。"""
    return Path.cwd() / MCP_CONFIG_FILE


def _string_map(value: Any, field_name: str, server: str) -> Tuple[Dict[str, str], Optional[str]]:
    if value is None:
        return {}, None
    if not isinstance(value, dict):
        return {}, f"MCP Server {server!r} 的 {field_name} 必须是 JSON 对象。"
    result: Dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            return {}, f"MCP Server {server!r} 的 {field_name} 的键和值都必须是字符串。"
        result[key] = item
    return result, None


def _string_list(value: Any, field_name: str, server: str) -> Tuple[List[str], Optional[str]]:
    if value is None:
        return [], None
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return [], f"MCP Server {server!r} 的 {field_name} 必须是字符串数组。"
    return list(value), None


def _positive_float(value: Any, field_name: str, server: str, default: float) -> Tuple[float, Optional[str]]:
    if value is None:
        return default, None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default, f"MCP Server {server!r} 的 {field_name} 必须是数字。"
    number = float(value)
    if number <= 0:
        return default, f"MCP Server {server!r} 的 {field_name} 必须大于 0。"
    return number, None


def _parse_server(
    name: str,
    entry: dict,
    default_connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
    default_call_timeout: float = DEFAULT_CALL_TIMEOUT,
) -> Tuple[Optional[McpServerConfig], Optional[str]]:
    if entry.get("disabled") is True:
        return None, None

    raw_type = entry.get("type") or entry.get("transport") or ""
    url = entry.get("url") or entry.get("httpUrl") or entry.get("http_url") or ""
    command = entry.get("command") or ""

    if not isinstance(raw_type, str):
        return None, f"MCP Server {name!r} 的 type 必须是字符串。"
    transport = raw_type.strip().lower()
    if not transport:
        if url:
            transport = "streamable_http"
        elif command:
            transport = "stdio"
        else:
            return None, f"MCP Server {name!r} 缺少 type/url/command,无法判断连接方式。"

    if transport in _HTTP_TYPES:
        if not isinstance(url, str) or not url.strip():
            return None, f"MCP Server {name!r} 使用 Streamable HTTP,但缺少合法的 url。"
        headers, error = _string_map(entry.get("headers"), "headers", name)
        if error:
            return None, error
        connect_timeout, error = _positive_float(
            entry.get("connectTimeout"), "connectTimeout", name, default_connect_timeout
        )
        if error:
            return None, error
        call_timeout, error = _positive_float(
            entry.get("callTimeout"), "callTimeout", name, default_call_timeout
        )
        if error:
            return None, error
        return (
            McpServerConfig(
                name=name,
                transport="streamable_http",
                url=url.strip(),
                headers=headers,
                connect_timeout=connect_timeout,
                call_timeout=call_timeout,
            ),
            None,
        )

    if transport in _STDIO_TYPES:
        if not isinstance(command, str) or not command.strip():
            return None, f"MCP Server {name!r} 使用 stdio,但缺少合法的 command。"
        args, error = _string_list(entry.get("args"), "args", name)
        if error:
            return None, error
        env, error = _string_map(entry.get("env"), "env", name)
        if error:
            return None, error
        cwd = entry.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            return None, f"MCP Server {name!r} 的 cwd 必须是字符串。"
        connect_timeout, error = _positive_float(
            entry.get("connectTimeout"), "connectTimeout", name, default_connect_timeout
        )
        if error:
            return None, error
        call_timeout, error = _positive_float(
            entry.get("callTimeout"), "callTimeout", name, default_call_timeout
        )
        if error:
            return None, error
        return (
            McpServerConfig(
                name=name,
                transport="stdio",
                command=command.strip(),
                args=args,
                env=env,
                cwd=cwd or None,
                connect_timeout=connect_timeout,
                call_timeout=call_timeout,
            ),
            None,
        )

    return None, f"MCP Server {name!r} 的协议 {raw_type!r} 暂不支持(仅支持 stdio 与 streamable_http)。"


def load_mcp_config(
    path: Optional[Path] = None,
    default_connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
    default_call_timeout: float = DEFAULT_CALL_TIMEOUT,
) -> Tuple[List[McpServerConfig], List[str]]:
    """读取 .mcp.json,返回 (合法 Server 配置, 错误信息列表)。

    文件不存在时返回空配置,不视为错误;文件整体损坏时返回一条错误信息。
    """
    config_path = Path(path) if path is not None else default_config_path()
    if not config_path.is_file():
        return [], []

    try:
        text = config_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return [], [f"读取 MCP 配置文件失败: {config_path} ({exc})"]

    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError as exc:
        return [], [f"MCP 配置文件解析失败: {config_path} ({exc})"]

    if not isinstance(data, dict):
        return [], [f"MCP 配置文件 {config_path} 的顶层必须是 JSON 对象。"]

    servers = data.get("mcpServers", data.get("mcp_servers"))
    if servers is None:
        return [], []
    if not isinstance(servers, dict):
        return [], [f"MCP 配置文件 {config_path} 中的 mcpServers 必须是 JSON 对象。"]

    configs: List[McpServerConfig] = []
    errors: List[str] = []
    for name, entry in servers.items():
        if not isinstance(name, str) or not name.strip():
            errors.append("MCP 配置中存在空的 Server 名称,已忽略。")
            continue
        if not isinstance(entry, dict):
            errors.append(f"MCP Server {name!r} 的配置必须是 JSON 对象。")
            continue
        config, error = _parse_server(
            name, entry, default_connect_timeout, default_call_timeout
        )
        if error:
            errors.append(error)
            continue
        if config is not None:
            configs.append(config)
    return configs, errors

