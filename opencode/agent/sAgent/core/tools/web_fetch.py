"""fetchWeb 工具: 通过本地 curl 抓取网页,trafilatura 提取正文转 Markdown。

调用链: URL → subprocess(参数列表, 无 shell) → curl.exe → HTML
       → trafilatura.extract(markdown) → 正文 Markdown + 来源 URL
异常处理覆盖: URL 非法 / 超时 / curl 失败(DNS、连接、HTTP 状态) /
             输出为空 / 正文提取失败。
"""

import re
import subprocess

import trafilatura

from .base import ToolRegistry, ToolSpec, make_handler

CURL_TIMEOUT = 60
CURL_CONNECT_TIMEOUT = 15
MAX_RESULT_CHARS = 30000
CURL_TIMEOUT_RUNTIME = CURL_TIMEOUT
CURL_CONNECT_TIMEOUT_RUNTIME = CURL_CONNECT_TIMEOUT
MAX_RESULT_CHARS_RUNTIME = MAX_RESULT_CHARS
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# curl 退出码 → 用户可读文案
_CURL_ERRORS = {
    6: "域名解析失败,请检查网址是否拼写正确。",
    7: "无法连接到目标网站,站点可能宕机或拒绝访问。",
    28: "网页请求超时:{}",
    47: "重定向次数过多。",
    56: "接收响应数据失败,网络中断。",
}

status_line = re.compile(r"error:\s*(\d{3})")


def _curl_error_message(stderr: str) -> str:
    match = status_line.search(stderr)
    code = match.group(1) if match else "?"
    return f"目标网站返回了错误的 HTTP 状态码 ({code}),页面可能不存在或禁止访问。"


def _run_curl(url: str, timeout: int = 0) -> str:
    """以参数列表方式调用 curl 抓取 HTML;失败抛 ValueError(文案用户可读)。"""
    if timeout <= 0:
        timeout = CURL_TIMEOUT_RUNTIME
    command = [
        "curl",
        "-sSLf",
        "--compressed",
        "--max-time", str(timeout),
        "--connect-timeout", str(CURL_CONNECT_TIMEOUT_RUNTIME),
        "--retry", "1",
        "--user-agent", USER_AGENT,
        "--",
        url,
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 10,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"网页请求超时(>{timeout}s),请稍后重试。") from exc
    except OSError as exc:
        raise ValueError(f"无法启动本地 curl 程序: {exc}") from exc

    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
        if result.returncode == 22:
            raise ValueError(_curl_error_message(stderr))
        text = _CURL_ERRORS.get(result.returncode)
        if text and "{" in text:
            text = text.format(stderr.splitlines()[0] if stderr else "无响应")
        raise ValueError(text or f"curl 调用失败(退出码 {result.returncode}): {stderr[:200]}")

    html = (result.stdout or b"").decode("utf-8", errors="replace").strip()
    if not html:
        raise ValueError("网页返回了空内容。")
    return html


def fetch_web_page(url: str, timeout: int = 0) -> str:
    """工具实现: 返回 Markdown 正文 + 来源 URL。"""
    if not isinstance(url, str) or not re.match(r"^https?://[^\s]+$", url.strip()):
        return "参数错误: url 必须是 http/https 开头的合法链接。"
    url = url.strip()
    try:
        html = _run_curl(url, timeout)
    except ValueError as exc:
        return f"获取网页失败: {exc}"

    try:
        markdown = trafilatura.extract(
            html,
            output_format="markdown",
            include_links=True,
            include_tables=True,
            url=url,
            favor_precision=True,
        )
    except Exception:  # noqa: BLE001  提取器任何内部错误都按提取失败处理
        markdown = None
    if not markdown or not markdown.strip():
        return (
            f"获取网页 {url} 成功,但无法从页面提取正文"
            "(可能为纯脚本页面、需登录或非文章型页面)。"
        )

    limit = MAX_RESULT_CHARS_RUNTIME
    if len(markdown) > limit:
        markdown = markdown[:limit] + "\n\n(内容过长已截断)"
    return f"# 来源\n{url}\n\n{markdown}"


_TOOL_SPEC = (
    "fetchWeb",
    "获取指定网页的主要内容。输入一个 http/https 网页 URL,返回该网页正文,已转成 Markdown"
    "(保留标题、段落、列表、表格、链接),并自动去除导航栏、广告、页脚等无关内容。"
    "返回结果的标题部分附有原始 URL。适用于查询网页文章、文档、新闻等页面内容。",
    {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要获取的网页地址,必须是 http:// 或 https:// 开头的完整 URL"},
            "timeout": {"type": "integer", "description": "可选,网页请求超时秒数,默认 60"},
        },
        "required": ["url"],
    },
    fetch_web_page,
    ("url",),
    ("timeout",),
)


def register(
    registry: ToolRegistry,
    timeout: int = CURL_TIMEOUT,
    connect_timeout: int = CURL_CONNECT_TIMEOUT,
    max_result_chars: int = MAX_RESULT_CHARS,
) -> None:
    global CURL_TIMEOUT_RUNTIME, CURL_CONNECT_TIMEOUT_RUNTIME, MAX_RESULT_CHARS_RUNTIME
    CURL_TIMEOUT_RUNTIME = timeout
    CURL_CONNECT_TIMEOUT_RUNTIME = connect_timeout
    MAX_RESULT_CHARS_RUNTIME = max_result_chars
    parameters = dict(_TOOL_SPEC[2])
    properties = dict(parameters.get("properties", {}))
    properties["timeout"] = {
        "type": "integer",
        "description": f"可选,网页请求超时秒数,默认 {timeout}",
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
