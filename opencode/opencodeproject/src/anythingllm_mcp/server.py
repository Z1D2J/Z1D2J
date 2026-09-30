"""AnythingLLM MCP Server - Main entry point."""

import logging
import sys
from typing import Any, Optional

from mcp.server import MCPServer

from . import __version__
from .config import get_config
from .tools import (
    # Auth
    verify_api_key,
    # Documents
    upload_document,
    upload_document_from_url,
    upload_raw_text,
    list_documents,
    get_document,
    delete_document,
    create_folder,
    delete_folder,
    move_files,
    # Workspaces
    create_workspace,
    list_workspaces,
    get_workspace,
    delete_workspace,
    update_workspace,
    add_documents_to_workspace,
    remove_documents_from_workspace,
    chat_with_workspace,
    vector_search,
    # Threads
    create_thread,
    list_threads,
    delete_thread,
    chat_with_thread,
    # System
    get_system_settings,
    update_system_settings,
    get_vector_count,
    export_chats,
    # Users
    list_users,
    create_user,
    update_user,
    delete_user,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Create MCP server instance
mcp = MCPServer(
    "anythingllm",
    version=__version__,
    description="MCP Server for accessing local AnythingLLM instance",
)

# Register tools using decorator syntax
@mcp.tool()
async def tool_verify_api_key() -> dict:
    """Verify the AnythingLLM API key is valid."""
    return await verify_api_key()

@mcp.tool()
async def tool_upload_document(
    file_path: str,
    folder_name: Optional[str] = None,
    add_to_workspaces: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    """Upload a document file to AnythingLLM."""
    return await upload_document(file_path, folder_name, add_to_workspaces, metadata)

@mcp.tool()
async def tool_upload_document_from_url(
    url: str,
    add_to_workspaces: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    """Upload a document from a URL."""
    return await upload_document_from_url(url, add_to_workspaces, metadata)

@mcp.tool()
async def tool_upload_raw_text(
    text_content: str,
    add_to_workspaces: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    """Upload raw text as a document."""
    return await upload_raw_text(text_content, add_to_workspaces, metadata)

@mcp.tool()
async def tool_list_documents(folder_name: Optional[str] = None) -> dict:
    """List all documents in AnythingLLM."""
    return await list_documents(folder_name)

@mcp.tool()
async def tool_get_document(document_name: str) -> dict:
    """Get details of a specific document."""
    return await get_document(document_name)

@mcp.tool()
async def tool_delete_document(document_names: list[str]) -> dict:
    """Permanently delete documents."""
    return await delete_document(document_names)

@mcp.tool()
async def tool_create_folder(folder_name: str) -> dict:
    """Create a document folder."""
    return await create_folder(folder_name)

@mcp.tool()
async def tool_delete_folder(folder_name: str) -> dict:
    """Delete a document folder and its contents."""
    return await delete_folder(folder_name)

@mcp.tool()
async def tool_move_files(files: list[dict[str, str]]) -> dict:
    """Move files between folders."""
    return await move_files(files)

@mcp.tool()
async def tool_create_workspace(
    name: str,
    similarity_threshold: float = 0.7,
    open_ai_temp: float = 0.7,
    open_ai_history: int = 20,
    open_ai_prompt: str = "",
    query_refusal_response: str = "",
    chat_mode: str = "chat",
    top_n: int = 4,
) -> dict:
    """Create a new workspace."""
    return await create_workspace(
        name, similarity_threshold, open_ai_temp, open_ai_history,
        open_ai_prompt, query_refusal_response, chat_mode, top_n,
    )

@mcp.tool()
async def tool_list_workspaces() -> dict:
    """List all workspaces."""
    return await list_workspaces()

@mcp.tool()
async def tool_get_workspace(workspace_slug: str) -> dict:
    """Get workspace details."""
    return await get_workspace(workspace_slug)

@mcp.tool()
async def tool_delete_workspace(workspace_slug: str) -> dict:
    """Delete a workspace."""
    return await delete_workspace(workspace_slug)

@mcp.tool()
async def tool_update_workspace(
    workspace_slug: str,
    name: Optional[str] = None,
    open_ai_temp: Optional[float] = None,
    open_ai_history: Optional[int] = None,
    open_ai_prompt: Optional[str] = None,
) -> dict:
    """Update workspace settings."""
    return await update_workspace(workspace_slug, name, open_ai_temp, open_ai_history, open_ai_prompt)

@mcp.tool()
async def tool_add_documents_to_workspace(
    workspace_slug: str,
    document_paths: list[str],
) -> dict:
    """Add documents to a workspace."""
    return await add_documents_to_workspace(workspace_slug, document_paths)

@mcp.tool()
async def tool_remove_documents_from_workspace(
    workspace_slug: str,
    document_paths: list[str],
) -> dict:
    """Remove documents from a workspace."""
    return await remove_documents_from_workspace(workspace_slug, document_paths)

@mcp.tool()
async def tool_chat_with_workspace(
    workspace_slug: str,
    message: str,
    mode: str = "chat",
    session_id: Optional[str] = None,
) -> dict:
    """Chat with a workspace."""
    return await chat_with_workspace(workspace_slug, message, mode, session_id)

@mcp.tool()
async def tool_vector_search(
    workspace_slug: str,
    query: str,
    top_n: int = 4,
    score_threshold: float = 0.75,
) -> dict:
    """Perform vector search in a workspace."""
    return await vector_search(workspace_slug, query, top_n, score_threshold)

@mcp.tool()
async def tool_create_thread(
    workspace_slug: str,
    name: str,
    user_id: Optional[int] = None,
) -> dict:
    """Create a new thread in a workspace."""
    return await create_thread(workspace_slug, name, user_id)

@mcp.tool()
async def tool_list_threads(workspace_slug: str) -> dict:
    """List all threads in a workspace."""
    return await list_threads(workspace_slug)

@mcp.tool()
async def tool_delete_thread(workspace_slug: str, thread_slug: str) -> dict:
    """Delete a thread."""
    return await delete_thread(workspace_slug, thread_slug)

@mcp.tool()
async def tool_chat_with_thread(
    workspace_slug: str,
    thread_slug: str,
    message: str,
    mode: str = "chat",
) -> dict:
    """Chat with a thread."""
    return await chat_with_thread(workspace_slug, thread_slug, message, mode)

@mcp.tool()
async def tool_get_system_settings() -> dict:
    """Get system settings."""
    return await get_system_settings()

@mcp.tool()
async def tool_update_system_settings(settings: dict[str, Any]) -> dict:
    """Update system settings."""
    return await update_system_settings(settings)

@mcp.tool()
async def tool_get_vector_count() -> dict:
    """Get the total vector count in the vector database."""
    return await get_vector_count()

@mcp.tool()
async def tool_export_chats(export_type: str = "json") -> dict:
    """Export chat history."""
    return await export_chats(export_type)

@mcp.tool()
async def tool_list_users() -> dict:
    """List all users."""
    return await list_users()

@mcp.tool()
async def tool_create_user(
    username: str,
    password: str,
    role: str = "default",
) -> dict:
    """Create a new user."""
    return await create_user(username, password, role)

@mcp.tool()
async def tool_update_user(
    user_id: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
    role: Optional[str] = None,
    suspended: Optional[int] = None,
) -> dict:
    """Update user information."""
    return await update_user(user_id, username, password, role, suspended)

@mcp.tool()
async def tool_delete_user(user_id: int) -> dict:
    """Delete a user."""
    return await delete_user(user_id)


def main() -> None:
    """Main entry point for the MCP server."""
    config = get_config()
    logger.info(f"Starting AnythingLLM MCP Server v{__version__}")
    logger.info(f"Connecting to: {config.base_url}")
    
    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Run the server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()