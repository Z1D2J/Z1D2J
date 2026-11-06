"""工具注册与调度框架(业务能力层的基础件,UI 无关)。

新增工具只需: 写一个 `def fn(...) -> str` 实现 + 一条 ToolSpec 注册,
参数校验/OSError 兜底由 make_handler 统一处理。
"""

import json
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict
    handler: Callable[[str], str]

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def parse_arguments(arguments: str):
    try:
        args = json.loads(arguments) if arguments.strip() else {}
    except ValueError:
        return None
    return args if isinstance(args, dict) else None


def make_handler(
    func: Callable,
    required: Sequence[str] = (),
    optional: Sequence[str] = (),
) -> Callable[[str], str]:
    """把普通函数包装成 (JSON 字符串) -> 结果字符串 的工具 handler。"""

    def handler(arguments: str) -> str:
        args = parse_arguments(arguments)
        if args is None:
            return "参数解析失败: arguments 不是合法的 JSON 对象。"
        kwargs = {}
        for key in required:
            value = args.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                return f"参数错误: 缺少必填参数 {key}。"
            kwargs[key] = value
        for key in optional:
            if key in args and args[key] is not None:
                kwargs[key] = args[key]
        try:
            return func(**kwargs)
        except OSError as exc:
            return f"文件操作失败: {exc}"

    return handler


def call_fields(call: dict) -> Tuple[str, str]:
    """从标准格式 function 嵌套(或旧扁平格式)中取出工具名与参数。"""
    function = call.get("function")
    if isinstance(function, dict):
        return function.get("name") or "", function.get("arguments") or ""
    return call.get("name") or "", call.get("arguments") or ""


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def names(self) -> list:
        """已注册的工具名列表(用于 MCP 工具命名冲突检测)。"""
        return list(self._tools)

    def definitions(self) -> list:
        """OpenAI tools 数组格式的工具定义。"""
        return [spec.to_openai() for spec in self._tools.values()]

    def dispatch(self, call: dict) -> str:
        """执行一条 tool_calls 条目,永远返回字符串结果(不抛业务异常)。"""
        name, arguments = call_fields(call)
        spec = self._tools.get(name)
        if spec is None:
            return f"未知工具: {name}"
        return spec.handler(arguments or "")
