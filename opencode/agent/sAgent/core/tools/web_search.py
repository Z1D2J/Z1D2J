"""searchWeb 工具: 调用百度千帆 AI 搜索,为 LLM 提供互联网实时信息。

调用链: query → 百度千帆 /v2/ai_search/web_search → references
       → 整理为"编号 + 标题 + URL + 摘要(日期)"返回给 LLM。
鉴权: API Key 只从 config.ini [search] 小节 / 环境变量读取,不硬编码。
异常处理: 缺少配置 / 网络失败 / 超时 / HTTP 错误 / 接口错误体 / 空结果,
全部以清晰中文文案作为工具结果返回,不向上抛异常。
"""

from pathlib import Path
from typing import List, Optional

import requests

from ..config import CONFIG_FILE, load_search_api_key
from .base import ToolRegistry, ToolSpec, make_handler

SEARCH_ENDPOINT = "https://qianfan.baidubce.com/v2/ai_search/web_search"
SEARCH_TIMEOUT = 30
DEFAULT_TOP_K = 8
MAX_TOP_K = 20
QUERY_MAX_CHARS = 72  # 接口限制,超出会被截断
SNIPPET_MAX_CHARS = 300
RESULT_MAX_CHARS = 12000
VALID_RECENCY = ("week", "month", "semiyear", "year")

SEARCH_CONFIG_FILE: Optional[Path] = CONFIG_FILE
SEARCH_API_KEY_RUNTIME = ""
SEARCH_TIMEOUT_RUNTIME = SEARCH_TIMEOUT
DEFAULT_TOP_K_RUNTIME = DEFAULT_TOP_K
MAX_TOP_K_RUNTIME = MAX_TOP_K
QUERY_MAX_CHARS_RUNTIME = QUERY_MAX_CHARS
SNIPPET_MAX_CHARS_RUNTIME = SNIPPET_MAX_CHARS
RESULT_MAX_CHARS_RUNTIME = RESULT_MAX_CHARS

_MISSING_KEY_MESSAGE = (
    "错误: 搜索功能未配置。请在 config.ini 的 [search] 小节添加 baidu_qianfan_api_key,"
    "或设置环境变量 BAIDU_QIANFAN_API_KEY 后重试。"
)


def _api_key() -> str:
    """每次调用时读取(允许运行中补充配置),key 只来自配置/环境变量。"""
    return load_search_api_key(SEARCH_CONFIG_FILE) or SEARCH_API_KEY_RUNTIME


def _classify_http_error(status: int, detail: str) -> str:
    if status in (401, 403):
        return "错误: 搜索 API Key 无效或没有权限,请检查 config.ini 中的 baidu_qianfan_api_key。"
    if status == 429:
        return "错误: 搜索请求过于频繁或额度不足,请稍后重试。"
    if status >= 500:
        return "错误: 搜索服务端暂时不可用,请稍后重试。"
    return f"错误: 搜索接口调用失败 (HTTP {status})。{detail}"


def _format_references(references: List[dict], top_k: int) -> str:
    lines = []
    used = 0
    for ref in references[:top_k]:
        title = (ref.get("title") or ref.get("web_anchor") or "(无标题)").strip()
        url = (ref.get("url") or "").strip()
        snippet = (ref.get("snippet") or ref.get("web_anchor") or "").strip()
        if len(snippet) > SNIPPET_MAX_CHARS_RUNTIME:
            snippet = snippet[:SNIPPET_MAX_CHARS_RUNTIME] + "…"
        date = (ref.get("date") or "").strip()
        line = f"[{ref.get('id', len(lines) + 1)}] {title}"
        if url:
            line += f"\n    来源: {url}"
        if snippet:
            line += f"\n    摘要: {snippet}"
        if date:
            line += f"\n    日期: {date}"
        block = line + "\n"
        if used + len(block) > RESULT_MAX_CHARS_RUNTIME:
            lines.append("(结果过多已截断)")
            break
        lines.append(block)
        used += len(block)
    if not lines:
        return ""
    return "\n".join(lines).rstrip()


def search_web(query: str, top_k: int = 0, recency: str = "") -> str:
    """工具实现: 搜索并整理摘要 + 参考来源(标题/URL)。"""
    if not isinstance(query, str) or not query.strip():
        return "参数错误: query(搜索关键词或问题)不能为空。"
    query = query.strip()
    if len(query) > QUERY_MAX_CHARS_RUNTIME:
        query = query[:QUERY_MAX_CHARS_RUNTIME]

    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        top_k = DEFAULT_TOP_K_RUNTIME
    top_k = min(top_k, MAX_TOP_K_RUNTIME)

    if recency:
        if not isinstance(recency, str) or recency not in VALID_RECENCY:
            return f"参数错误: recency 可选值为 {'/'.join(VALID_RECENCY)}(可选,不填则不限时间)。"

    api_key = _api_key()
    if not api_key:
        return _MISSING_KEY_MESSAGE

    body = {
        "messages": [{"role": "user", "content": query}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": top_k}],
    }
    if recency:
        body["search_recency_filter"] = recency

    try:
        response = requests.post(
            SEARCH_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=SEARCH_TIMEOUT_RUNTIME,
        )
    except requests.exceptions.Timeout:
        return f"错误: 搜索请求超时(>{SEARCH_TIMEOUT_RUNTIME}s),请稍后重试。"
    except requests.exceptions.RequestException:
        return "错误: 搜索请求网络失败或传输中断,请检查网络后重试。"

    try:
        data = response.json()
    except ValueError:
        return _classify_http_error(response.status_code, "")

    if not isinstance(data, dict):
        return f"错误: 搜索接口返回了异常格式的数据 (HTTP {response.status_code})。"

    if data.get("code") is not None and data.get("references") is None:
        code = data.get("code")
        message = data.get("message") or ""
        if response.status_code in (401, 403):
            return _classify_http_error(response.status_code, "")
        detail = str(message).strip()[:300]
        return f"错误: 搜索接口返回错误(code {code})。{detail}"

    if not response.ok:
        detail = str(data.get("message") or "").strip()[:300]
        return _classify_http_error(response.status_code, f"详情: {detail}" if detail else "")

    references = data.get("references") or []
    if not isinstance(references, list) or not references:
        return f"搜索 '{query}' 没有找到相关结果,可尝试换个关键词。"

    formatted = _format_references(references, top_k)
    if not formatted:
        return f"搜索 '{query}' 没有找到相关结果,可尝试换个关键词。"
    return (
        f"搜索 '{query}' 的结果(共 {len(references[:top_k])} 条,含摘要与参考来源标题/URL):\n\n"
        + formatted
    )


_TOOL_SPEC = (
    "searchWeb",
    "使用百度搜索引擎查询互联网实时信息。输入搜索关键词或问题 query,返回多条搜索结果的摘要,"
    "以及每条结果的参考来源标题和 URL。适用于需要最新消息、实时动态、新闻、行情等场景;"
    "获取网页完整正文请改用 fetchWeb。",
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或自然语言问题,例如 '2026 AI 大模型 最新进展'",
            },
            "top_k": {
                "type": "integer",
                "description": "可选,返回结果条数,默认 8,最大 20",
            },
            "recency": {
                "type": "string",
                "enum": ["week", "month", "semiyear", "year"],
                "description": "可选,时间范围过滤: week 最近7天 / month 最近30天 / semiyear 最近半年 / year 最近一年",
            },
        },
        "required": ["query"],
    },
    search_web,
    ("query",),
    ("top_k", "recency"),
)


def register(
    registry: ToolRegistry,
    config_file: Optional[Path] = None,
    api_key: str = "",
    timeout: int = SEARCH_TIMEOUT,
    default_top_k: int = DEFAULT_TOP_K,
    max_top_k: int = MAX_TOP_K,
    query_max_chars: int = QUERY_MAX_CHARS,
    snippet_max_chars: int = SNIPPET_MAX_CHARS,
    result_max_chars: int = RESULT_MAX_CHARS,
) -> None:
    global SEARCH_CONFIG_FILE, SEARCH_API_KEY_RUNTIME, SEARCH_TIMEOUT_RUNTIME
    global DEFAULT_TOP_K_RUNTIME, MAX_TOP_K_RUNTIME, QUERY_MAX_CHARS_RUNTIME
    global SNIPPET_MAX_CHARS_RUNTIME, RESULT_MAX_CHARS_RUNTIME
    SEARCH_CONFIG_FILE = config_file
    SEARCH_API_KEY_RUNTIME = api_key
    SEARCH_TIMEOUT_RUNTIME = timeout
    DEFAULT_TOP_K_RUNTIME = default_top_k
    MAX_TOP_K_RUNTIME = max_top_k
    QUERY_MAX_CHARS_RUNTIME = query_max_chars
    SNIPPET_MAX_CHARS_RUNTIME = snippet_max_chars
    RESULT_MAX_CHARS_RUNTIME = result_max_chars
    parameters = dict(_TOOL_SPEC[2])
    properties = dict(parameters.get("properties", {}))
    properties["top_k"] = {
        "type": "integer",
        "description": f"可选,返回结果条数,默认 {default_top_k},最大 {max_top_k}",
    }
    parameters["properties"] = properties
    registry.register(
        ToolSpec(
            name=_TOOL_SPEC[0],
            description=_TOOL_SPEC[1],
            parameters=parameters,
            handler=make_handler(_TOOL_SPEC[3], required=_TOOL_SPEC[4], optional=_TOOL_SPEC[5]),
        )
    )
