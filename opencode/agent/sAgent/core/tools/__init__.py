"""工具装配入口: 组装默认工具注册表。"""

from .base import ToolRegistry, ToolSpec, call_fields, make_handler, parse_arguments
from . import builtin, file_ops

__all__ = [
    "ToolRegistry",
    "ToolSpec",
    "call_fields",
    "make_handler",
    "parse_arguments",
    "build_default_registry",
]


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    builtin.register(registry)
    file_ops.register(registry)
    return registry
