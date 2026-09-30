"""Data models for AnythingLLM MCP Server."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Document:
    """Document model."""
    
    name: str
    location: str = ""
    title: str = ""
    doc_author: str = ""
    description: str = ""
    doc_source: str = ""
    chunk_source: str = ""
    published: str = ""
    word_count: int = 0
    token_count_estimate: int = 0
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
        """Create Document from API response."""
        return cls(
            name=data.get("name", ""),
            location=data.get("location", ""),
            title=data.get("title", ""),
            doc_author=data.get("docAuthor", ""),
            description=data.get("description", ""),
            doc_source=data.get("docSource", ""),
            chunk_source=data.get("chunkSource", ""),
            published=data.get("published", ""),
            word_count=data.get("wordCount", 0),
            token_count_estimate=data.get("token_count_estimate", 0),
        )


@dataclass
class Workspace:
    """Workspace model."""
    
    id: int
    name: str
    slug: str
    created_at: str = ""
    open_ai_temp: float = 0.7
    open_ai_history: int = 20
    open_ai_prompt: str = ""
    chat_mode: str = "chat"
    top_n: int = 4
    documents: list[dict[str, Any]] = field(default_factory=list)
    threads: list[dict[str, Any]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Workspace":
        """Create Workspace from API response."""
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            slug=data.get("slug", ""),
            created_at=data.get("createdAt", ""),
            open_ai_temp=data.get("openAiTemp", 0.7),
            open_ai_history=data.get("openAiHistory", 20),
            open_ai_prompt=data.get("openAiPrompt", ""),
            chat_mode=data.get("chatMode", "chat"),
            top_n=data.get("topN", 4),
            documents=data.get("documents", []),
            threads=data.get("threads", []),
        )


@dataclass
class Thread:
    """Thread model."""
    
    id: int
    name: str
    slug: str
    user_id: Optional[int] = None
    workspace_id: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Thread":
        """Create Thread from API response."""
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            slug=data.get("slug", ""),
            user_id=data.get("user_id"),
            workspace_id=data.get("workspace_id"),
        )


@dataclass
class ChatMessage:
    """Chat message model."""
    
    role: str
    content: str
    sent_at: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatMessage":
        """Create ChatMessage from API response."""
        return cls(
            role=data.get("role", ""),
            content=data.get("content", ""),
            sent_at=data.get("sentAt", ""),
            sources=data.get("sources", []),
        )


@dataclass
class User:
    """User model."""
    
    id: int
    username: str
    role: str = "default"
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        """Create User from API response."""
        return cls(
            id=data.get("id", 0),
            username=data.get("username", ""),
            role=data.get("role", "default"),
        )


@dataclass
class SystemSettings:
    """System settings model."""
    
    settings: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemSettings":
        """Create SystemSettings from API response."""
        return cls(settings=data.get("settings", {}))