"""Workspace management tools for AnythingLLM MCP Server."""

from typing import Any, Optional

from ..client import AnythingLLMClient


async def create_workspace(
    name: str,
    similarity_threshold: float = 0.7,
    open_ai_temp: float = 0.7,
    open_ai_history: int = 20,
    open_ai_prompt: str = "",
    query_refusal_response: str = "",
    chat_mode: str = "chat",
    top_n: int = 4,
) -> dict:
    """Create a new workspace.
    
    Args:
        name: Name of the workspace.
        similarity_threshold: Similarity threshold for document matching.
        open_ai_temp: OpenAI temperature setting.
        open_ai_history: OpenAI history length.
        open_ai_prompt: Custom prompt for the workspace.
        query_refusal_response: Response when query is refused.
        chat_mode: Chat mode (chat, query, automatic).
        top_n: Number of top results to return.
    
    Returns:
        Dictionary with creation result and workspace information.
    """
    client = AnythingLLMClient()
    try:
        workspace = await client.create_workspace(
            name=name,
            settings={
                "similarityThreshold": similarity_threshold,
                "openAiTemp": open_ai_temp,
                "openAiHistory": open_ai_history,
                "openAiPrompt": open_ai_prompt,
                "queryRefusalResponse": query_refusal_response,
                "chatMode": chat_mode,
                "topN": top_n,
            },
        )
        return {
            "status": "success",
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "slug": workspace.slug,
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def list_workspaces() -> dict:
    """List all workspaces.
    
    Returns:
        Dictionary with list of workspaces.
    """
    client = AnythingLLMClient()
    try:
        workspaces = await client.list_workspaces()
        return {
            "status": "success",
            "workspaces": [
                {
                    "id": ws.id,
                    "name": ws.name,
                    "slug": ws.slug,
                }
                for ws in workspaces
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def get_workspace(workspace_slug: str) -> dict:
    """Get workspace details.
    
    Args:
        workspace_slug: Slug of the workspace to retrieve.
    
    Returns:
        Dictionary with workspace details.
    """
    client = AnythingLLMClient()
    try:
        workspace = await client.get_workspace(workspace_slug)
        return {
            "status": "success",
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "slug": workspace.slug,
                "chat_mode": workspace.chat_mode,
                "documents": workspace.documents,
                "threads": workspace.threads,
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def delete_workspace(workspace_slug: str) -> dict:
    """Delete a workspace.
    
    Args:
        workspace_slug: Slug of the workspace to delete.
    
    Returns:
        Dictionary with deletion result.
    """
    client = AnythingLLMClient()
    try:
        result = await client.delete_workspace(workspace_slug)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def update_workspace(
    workspace_slug: str,
    name: Optional[str] = None,
    open_ai_temp: Optional[float] = None,
    open_ai_history: Optional[int] = None,
    open_ai_prompt: Optional[str] = None,
) -> dict:
    """Update workspace settings.
    
    Args:
        workspace_slug: Slug of the workspace to update.
        name: New name for the workspace.
        open_ai_temp: New temperature setting.
        open_ai_history: New history length.
        open_ai_prompt: New custom prompt.
    
    Returns:
        Dictionary with update result.
    """
    client = AnythingLLMClient()
    try:
        settings: dict[str, Any] = {}
        if name is not None:
            settings["name"] = name
        if open_ai_temp is not None:
            settings["openAiTemp"] = open_ai_temp
        if open_ai_history is not None:
            settings["openAiHistory"] = open_ai_history
        if open_ai_prompt is not None:
            settings["openAiPrompt"] = open_ai_prompt
        
        result = await client.update_workspace(workspace_slug, settings)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def add_documents_to_workspace(
    workspace_slug: str,
    document_paths: list[str],
) -> dict:
    """Add documents to a workspace.
    
    Args:
        workspace_slug: Slug of the workspace.
        document_paths: List of document paths to add.
    
    Returns:
        Dictionary with update result.
    """
    client = AnythingLLMClient()
    try:
        result = await client.update_embeddings(
            workspace_slug=workspace_slug,
            adds=document_paths,
            deletes=[],
        )
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def remove_documents_from_workspace(
    workspace_slug: str,
    document_paths: list[str],
) -> dict:
    """Remove documents from a workspace.
    
    Args:
        workspace_slug: Slug of the workspace.
        document_paths: List of document paths to remove.
    
    Returns:
        Dictionary with update result.
    """
    client = AnythingLLMClient()
    try:
        result = await client.update_embeddings(
            workspace_slug=workspace_slug,
            adds=[],
            deletes=document_paths,
        )
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def chat_with_workspace(
    workspace_slug: str,
    message: str,
    mode: str = "chat",
    session_id: Optional[str] = None,
) -> dict:
    """Chat with a workspace.
    
    Args:
        workspace_slug: Slug of the workspace to chat with.
        message: Message to send.
        mode: Chat mode (chat, query, automatic).
        session_id: Session ID for conversation tracking.
    
    Returns:
        Dictionary with chat response.
    """
    client = AnythingLLMClient()
    try:
        result = await client.chat(
            workspace_slug=workspace_slug,
            message=message,
            mode=mode,
            session_id=session_id,
        )
        return {
            "status": "success",
            "response": result.get("textResponse", ""),
            "sources": result.get("sources", []),
            "type": result.get("type", ""),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def vector_search(
    workspace_slug: str,
    query: str,
    top_n: int = 4,
    score_threshold: float = 0.75,
) -> dict:
    """Perform vector search in a workspace.
    
    Args:
        workspace_slug: Slug of the workspace to search.
        query: Search query.
        top_n: Number of top results to return.
        score_threshold: Minimum similarity score.
    
    Returns:
        Dictionary with search results.
    """
    client = AnythingLLMClient()
    try:
        result = await client.vector_search(
            workspace_slug=workspace_slug,
            query=query,
            top_n=top_n,
            score_threshold=score_threshold,
        )
        return {
            "status": "success",
            "results": result.get("results", []),
            "search_mode": result.get("searchMode", ""),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}