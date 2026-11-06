"""工具装配入口: 组装默认工具注册表。"""

from pathlib import Path
from typing import Optional

from ..config import Settings
from .base import ToolRegistry, ToolSpec, call_fields, make_handler, parse_arguments
from . import builtin, file_ops, office_cli, run_cli, web_fetch, web_search

__all__ = [
    "ToolRegistry",
    "ToolSpec",
    "call_fields",
    "make_handler",
    "parse_arguments",
    "build_default_registry",
]


def build_default_registry(settings: Optional[Settings] = None) -> ToolRegistry:
    registry = ToolRegistry()
    if settings is None:
        builtin.register(registry)
        file_ops.register(registry)
        office_cli.register(registry)
        run_cli.register(registry)
        web_fetch.register(registry)
        web_search.register(registry)
        return registry

    builtin.register(registry)
    file_ops.register(registry, max_read_chars=settings.file_read_max_chars)
    office_cli.register(
        registry,
        default_timeout=settings.office_timeout,
        max_timeout=settings.office_max_timeout,
        max_output_chars=settings.office_max_output_chars,
    )
    run_cli.register(
        registry,
        default_timeout=settings.run_cli_timeout,
        max_timeout=settings.run_cli_max_timeout,
        max_output_chars=settings.run_cli_max_output_chars,
    )
    web_fetch.register(
        registry,
        timeout=settings.web_fetch_timeout,
        connect_timeout=settings.web_fetch_connect_timeout,
        max_result_chars=settings.web_fetch_max_chars,
    )
    web_search.register(
        registry,
        config_file=Path(settings.config_file) if settings.config_file else None,
        api_key=settings.search_api_key,
        timeout=settings.web_search_timeout,
        default_top_k=settings.web_search_top_k,
        max_top_k=settings.web_search_max_top_k,
        snippet_max_chars=settings.web_search_snippet_max_chars,
        result_max_chars=settings.web_search_result_max_chars,
        query_max_chars=settings.web_search_query_max_chars,
    )
    return registry
