"""MCP tools for AnythingLLM integration."""

from .auth import verify_api_key
from .documents import (
    create_folder,
    delete_document,
    delete_folder,
    get_document,
    list_documents,
    move_files,
    upload_document,
    upload_document_from_url,
    upload_raw_text,
)
from .workspaces import (
    chat_with_workspace,
    create_workspace,
    delete_workspace,
    get_workspace,
    list_workspaces,
    remove_documents_from_workspace,
    add_documents_to_workspace,
    update_workspace,
    vector_search,
)
from .threads import (
    chat_with_thread,
    create_thread,
    delete_thread,
    list_threads,
)
from .system import (
    export_chats,
    get_system_settings,
    get_vector_count,
    update_system_settings,
)
from .admin import (
    create_user,
    delete_user,
    list_users,
    update_user,
)

__all__ = [
    # Auth
    "verify_api_key",
    # Documents
    "upload_document",
    "upload_document_from_url",
    "upload_raw_text",
    "list_documents",
    "get_document",
    "delete_document",
    "create_folder",
    "delete_folder",
    "move_files",
    # Workspaces
    "create_workspace",
    "list_workspaces",
    "get_workspace",
    "delete_workspace",
    "update_workspace",
    "add_documents_to_workspace",
    "remove_documents_from_workspace",
    "chat_with_workspace",
    "vector_search",
    # Threads
    "create_thread",
    "list_threads",
    "delete_thread",
    "chat_with_thread",
    # System
    "get_system_settings",
    "update_system_settings",
    "get_vector_count",
    "export_chats",
    # Users
    "list_users",
    "create_user",
    "update_user",
    "delete_user",
]