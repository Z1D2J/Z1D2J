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


AgentEvent = Union[
    TurnStarted,
    TextDelta,
    ReasoningDelta,
    ToolCallStarted,
    ToolCallFinished,
    AssistantMessage,
    TurnFinished,
    ErrorEvent,
]

EventSink = Callable[[AgentEvent], None]


def null_sink(event: AgentEvent) -> None:
    """默认空实现,便于 core 单独使用。"""
    return None
