"""Thread management tools for AnythingLLM MCP Server."""

from typing import Optional

from ..client import AnythingLLMClient


async def create_thread(
    workspace_slug: str,
    name: str,
    user_id: Optional[int] = None,
) -> dict:
    """Create a new thread in a workspace.
    
    Args:
        workspace_slug: Slug of the workspace.
        name: Name of the thread.
        user_id: User ID (optional).
    
    Returns:
        Dictionary with creation result and thread information.
    """
    client = AnythingLLMClient()
    try:
        thread = await client.create_thread(
            workspace_slug=workspace_slug,
            name=name,
            user_id=user_id,
        )
        return {
            "status": "success",
            "thread": {
                "id": thread.id,
                "name": thread.name,
                "slug": thread.slug,
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def list_threads(workspace_slug: str) -> dict:
    """List all threads in a workspace.
    
    Args:
        workspace_slug: Slug of the workspace.
    
    Returns:
        Dictionary with list of threads.
    """
    client = AnythingLLMClient()
    try:
        threads = await client.list_threads(workspace_slug)
        return {
            "status": "success",
            "threads": [
                {
                    "id": thread.id,
                    "name": thread.name,
                    "slug": thread.slug,
                }
                for thread in threads
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def delete_thread(workspace_slug: str, thread_slug: str) -> dict:
    """Delete a thread.
    
    Args:
        workspace_slug: Slug of the workspace.
        thread_slug: Slug of the thread to delete.
    
    Returns:
        Dictionary with deletion result.
    """
    client = AnythingLLMClient()
    try:
        result = await client.delete_thread(workspace_slug, thread_slug)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def chat_with_thread(
    workspace_slug: str,
    thread_slug: str,
    message: str,
    mode: str = "chat",
) -> dict:
    """Chat with a thread.
    
    Args:
        workspace_slug: Slug of the workspace.
        thread_slug: Slug of the thread to chat with.
        message: Message to send.
        mode: Chat mode (chat, query).
    
    Returns:
        Dictionary with chat response.
    """
    client = AnythingLLMClient()
    try:
        result = await client.chat_with_thread(
            workspace_slug=workspace_slug,
            thread_slug=thread_slug,
            message=message,
            mode=mode,
        )
        return {
            "status": "success",
            "response": result.get("textResponse", ""),
            "sources": result.get("sources", []),
            "type": result.get("type", ""),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}