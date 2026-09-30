"""System management tools for AnythingLLM MCP Server."""

from typing import Any, Optional

from ..client import AnythingLLMClient


async def get_system_settings() -> dict:
    """Get system settings.
    
    Returns:
        Dictionary with system settings.
    """
    client = AnythingLLMClient()
    try:
        settings = await client.get_system_settings()
        return {"status": "success", "settings": settings.settings}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def update_system_settings(settings: dict[str, Any]) -> dict:
    """Update system settings.
    
    Args:
        settings: Dictionary of settings to update.
    
    Returns:
        Dictionary with update result.
    """
    client = AnythingLLMClient()
    try:
        result = await client.update_system_settings(settings)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def get_vector_count() -> dict:
    """Get the total vector count in the vector database.
    
    Returns:
        Dictionary with vector count.
    """
    client = AnythingLLMClient()
    try:
        count = await client.get_vector_count()
        return {"status": "success", "vector_count": count}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def export_chats(export_type: str = "json") -> dict:
    """Export chat history.
    
    Args:
        export_type: Export format (json, jsonl, csv, jsonAlpaca).
    
    Returns:
        Dictionary with exported chat data.
    """
    client = AnythingLLMClient()
    try:
        chats = await client.export_chats(export_type)
        return {"status": "success", "chats": chats, "format": export_type}
    except Exception as e:
        return {"status": "error", "message": str(e)}