"""sAgent 核心业务层(core): 与界面完全解耦,可被 TUI/Web/Desktop 复用。

分层:
- L1 基础设施: config / errors / llm(传输)
- L2 领域: tools(业务能力)
- L3 应用 + 契约: agent(编排) / events(UI 通信契约)

对外只暴露稳定 API: Agent + 事件类型。
core 不 import tui 或任何 UI 框架。
"""

from .agent import Agent
from .config import Settings, load_config
from .context import ContextStore, ContextUsage
from .errors import AgentError, ConfigError
from .events import (
    AgentEvent,
    AssistantMessage,
    CompactionFailed,
    CompactionFinished,
    CompactionStarted,
    ContextStatus,
    ContextWarning,
    ErrorEvent,
    EventSink,
    McpServerInfo,
    McpStatus,
    ReasoningDelta,
    TextDelta,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    TurnStarted,
)
from .session import SessionInfo, SessionStore
from .skills import Skill, SkillCatalog
from .mcp import McpManager
from .tools import ToolRegistry, build_default_registry

__all__ = [
    "Agent",
    "Settings",
    "load_config",
    "ContextStore",
    "ContextUsage",
    "AgentError",
    "ConfigError",
    "SessionInfo",
    "SessionStore",
    "Skill",
    "SkillCatalog",
    "McpManager",
    "McpServerInfo",
    "McpStatus",
    "ToolRegistry",
    "build_default_registry",
    "AgentEvent",
    "EventSink",
    "TurnStarted",
    "TextDelta",
    "ReasoningDelta",
    "ToolCallStarted",
    "ToolCallFinished",
    "AssistantMessage",
    "TurnFinished",
    "ErrorEvent",
    "ContextStatus",
    "ContextWarning",
    "CompactionStarted",
    "CompactionFinished",
    "CompactionFailed",
]
