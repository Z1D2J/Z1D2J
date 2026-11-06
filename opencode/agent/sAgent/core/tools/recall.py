"""recallContext 工具: 检索 .agents/context/ 中归档的原始上下文。

压缩摘要可能丢失细节,LLM 可以调用本工具按关键词回溯原始对话。
"""

from typing import Optional

from ..context import ContextStore
from .base import ToolRegistry, ToolSpec, make_handler


def register(registry: ToolRegistry, store: ContextStore) -> None:
    def _recall(text: str, id: Optional[str] = None) -> str:
        return store.recall(text, id)

    registry.register(
        ToolSpec(
            name="recallContext",
            description=(
                "检索此前被压缩并归档的原始上下文。当上下文压缩摘要缺少关键细节时，"
                "使用本工具按关键词查找原始对话、工具调用参数或工具返回结果。"
                "id 可选，指定归档编号；不提供时检索所有历史归档。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "可选，上下文归档编号，例如 20261022-153000",
                    },
                    "text": {
                        "type": "string",
                        "description": "必需，要查找的关键词或文本内容",
                    },
                },
                "required": ["text"],
            },
            handler=make_handler(_recall, required=("text",), optional=("id",)),
        )
    )
