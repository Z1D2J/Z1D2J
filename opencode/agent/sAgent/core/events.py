"""事件契约层(core 与 UI 之间唯一的通信协议,UI 无关)。

core 通过 EventSink 把 AgentEvent 逐个推送给界面;
TUI / 未来 Web / Desktop 各自实现一个 sink,把事件翻译成对应框架的更新。
"""

from dataclasses import dataclass, field
from typing import Callable, Union


@dataclass(frozen=True)
class TextDelta:
    """模型回复的增量文本。"""

    text: str


@dataclass(frozen=True)
class ReasoningDelta:
    """思考过程的增量文本(如接口返回 reasoning_content)。"""

    text: str


@dataclass(frozen=True)
class ToolCallStarted:
    """一个工具开始执行前触发。"""

    name: str
    arguments: str


@dataclass(frozen=True)
class ToolCallFinished:
    """一个工具执行完毕后触发。"""

    name: str
    result: str


@dataclass(frozen=True)
class AssistantMessage:
    """一轮回复最终落定(无工具调用,可结束本轮)。"""

    text: str
    reasoning: str = ""


@dataclass(frozen=True)
class TurnStarted:
    """用户提交提示词,开始新的一轮。"""

    prompt: str


@dataclass(frozen=True)
class TurnFinished:
    """本轮完全结束(含全部工具往返),可以接受下一条输入。"""


@dataclass(frozen=True)
class ErrorEvent:
    """运行期错误,message 为用户可读文案。"""

    message: str


@dataclass(frozen=True)
class ContextStatus:
    """当前会话的上下文占用情况。"""

    tokens: int
    window: int
    percent: float
    default_window: bool


@dataclass(frozen=True)
class ContextWarning:
    """上下文达到压缩阈值时的提示。"""

    message: str


@dataclass(frozen=True)
class CompactionStarted:
    """用户执行 /compact,开始压缩上下文。"""


@dataclass(frozen=True)
class CompactionFinished:
    """压缩成功: 附带归档编号和压缩前后的文本,供 UI 对照显示。"""

    archive_id: str
    created_at: str
    original: str
    summary: str


@dataclass(frozen=True)
class CompactionFailed:
    """压缩失败,原有上下文保持不变。"""

    message: str


@dataclass(frozen=True)
class McpServerInfo:
    """单个 MCP Server 的连接状态与可用工具。"""

    name: str
    transport: str
    connected: bool
    tools: tuple = ()
    error: str = ""


@dataclass(frozen=True)
class McpStatus:
    """MCP 异步加载状态;loading=True 表示仍在连接。"""

    loading: bool
    servers: tuple = ()
    errors: tuple = ()


AgentEvent = Union[
    TurnStarted,
    TextDelta,
    ReasoningDelta,
    ToolCallStarted,
    ToolCallFinished,
    AssistantMessage,
    TurnFinished,
    ErrorEvent,
    ContextStatus,
    ContextWarning,
    CompactionStarted,
    CompactionFinished,
    CompactionFailed,
    McpServerInfo,
    McpStatus,
]

EventSink = Callable[[AgentEvent], None]


def null_sink(event: AgentEvent) -> None:
    """默认空实现,便于 core 单独使用。"""
    return None
