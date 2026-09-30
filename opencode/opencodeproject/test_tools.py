"""Test all tools can be imported and called."""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Set environment variables
import os
os.environ["ANYTHINGLLM_BASE_URL"] = "http://localhost:3001"
os.environ["ANYTHINGLLM_API_KEY"] = "test-api-key"

# Import all tools
from anythingllm_mcp.tools import (
    verify_api_key,
    upload_document,
    upload_document_from_url,
    upload_raw_text,
    list_documents,
    get_document,
    delete_document,
    create_folder,
    delete_folder,
    move_files,
    create_workspace,
    list_workspaces,
    get_workspace,
    delete_workspace,
    update_workspace,
    add_documents_to_workspace,
    remove_documents_from_workspace,
    chat_with_workspace,
    vector_search,
    create_thread,
    list_threads,
    delete_thread,
    chat_with_thread,
    get_system_settings,
    update_system_settings,
    get_vector_count,
    export_chats,
    list_users,
    create_user,
    update_user,
    delete_user,
)

print("All tools imported successfully!")
print(f"Total tools: {len(dir()) - 1}")