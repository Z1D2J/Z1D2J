"""OpenAI 兼容接口的流式客户端(传输层)。

职责:
- 组装请求(messages + tools)并发起 stream 请求
- 把网络/协议错误翻译成用户可读的 AgentError
- 解析 SSE,产出规范化 StreamEvent(见下)

不感知任何具体工具、对话策略与界面。
"""

from dataclasses import dataclass
from typing import Iterator, List, Union

import json

import requests

from ..config import Settings
from ..errors import AgentError


@dataclass(frozen=True)
class StreamText:
    text: str


@dataclass(frozen=True)
class StreamReasoning:
    text: str


@dataclass(frozen=True)
class StreamToolCalls:
    """一轮增量聚合完成后的标准格式 tool_calls 列表。"""

    calls: List[dict]


StreamEvent = Union[StreamText, StreamReasoning, StreamToolCalls]


def _error_detail(response) -> str:
    if response is None:
        return ""
    try:
        err = response.json()["error"]
        message = err.get("message") if isinstance(err, dict) else err
    except (ValueError, KeyError, TypeError, AttributeError):
        return ""
    if isinstance(message, str) and message.strip():
        return message.strip()[:300]
    return ""


def _http_error_message(exc: requests.exceptions.HTTPError, timeout: int) -> str:
    response = exc.response
    status = response.status_code if response is not None else 0
    if status in (401, 403):
        msg = "API Key 无效或没有权限,请检查 config.ini。"
    elif status == 429:
        msg = "请求过于频繁或额度不足,请稍后重试。"
    elif status == 404:
        msg = "接口地址或模型不存在,请检查 config.ini 中的 base_url / model。"
    elif status >= 500:
        msg = "服务端暂时不可用,请稍后重试。"
    else:
        msg = f"调用失败 (HTTP {status}),请稍后重试。"
    detail = _error_detail(response)
    return f"{msg}\n详情: {detail}" if detail else msg


class LLMClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    def stream(self, messages: list, tools: list) -> Iterator[StreamEvent]:
        """发起流式请求并按序产出 StreamEvent;错误以 AgentError 抛出。"""
        settings = self._settings
        try:
            resp = requests.post(
                f"{settings.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.model,
                    "messages": messages,
                    "stream": True,
                    "tools": tools,
                },
                stream=True,
                timeout=(10, settings.timeout),
            )
        except requests.exceptions.Timeout as exc:
            raise AgentError(f"请求超时 (>{settings.timeout}s),请稍后重试。") from exc
        except requests.exceptions.RequestException as exc:
            raise AgentError("网络连接失败或传输中断,请检查网络后重试。") from exc

        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            resp.close()
            raise AgentError(_http_error_message(exc, settings.timeout)) from exc
        resp.encoding = "utf-8"

        try:
            yield from self._iter_events(resp)
        finally:
            resp.close()

    @staticmethod
    def _iter_events(resp) -> Iterator[StreamEvent]:
        tool_calls: dict = {}
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                data = json.loads(payload)
            except ValueError:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("error"):
                err = data["error"]
                message = err.get("message") if isinstance(err, dict) else err
                raise AgentError(f"接口返回错误: {message}")
            choices = data.get("choices")
            if not choices:
                continue
            delta = choices[0].get("delta") or {}

            content = delta.get("content")
            if isinstance(content, str) and content:
                yield StreamText(content)

            reasoning = delta.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                yield StreamReasoning(reasoning)

            for item in delta.get("tool_calls") or []:
                if not isinstance(item, dict):
                    continue
                index = item.get("index", 0)
                entry = tool_calls.setdefault(
                    index,
                    {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                )
                if item.get("id"):
                    entry["id"] = item["id"]
                function = item.get("function") or {}
                if function.get("name"):
                    entry["function"]["name"] += function["name"]
                if function.get("arguments"):
                    entry["function"]["arguments"] += function["arguments"]
        if tool_calls:
            yield StreamToolCalls([tool_calls[key] for key in sorted(tool_calls)])
