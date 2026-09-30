# AnythingLLM MCP Server

MCP Server for accessing local AnythingLLM instance through the Model Context Protocol.

## Features

- **Document Management**: Upload, list, delete documents
- **Workspace Management**: Create, configure, and chat with workspaces
- **Thread Management**: Create and manage conversation threads
- **System Settings**: View and update system configuration
- **User Management**: Manage users (requires multi-user mode)

## Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv add "mcp[cli]" httpx2 python-dotenv pydantic

# Or using pip
pip install "mcp[cli]" httpx2 python-dotenv pydantic
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

Edit `.env`:
```bash
ANYTHINGLLM_BASE_URL=http://localhost:3001
ANYTHINGLLM_API_KEY=your-api-key-here
```

### 3. Run the Server

```bash
# Using uv
uv run python -m anythingllm_mcp.server

# Or using python directly
python -m anythingllm_mcp.server
```

### 4. Configure MCP Client

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "anythingllm": {
      "command": "python",
      "args": ["-m", "anythingllm_mcp.server"],
      "cwd": "D:\\ZDJ\\opencodeproject",
      "env": {
        "ANYTHINGLLM_BASE_URL": "http://localhost:3001",
        "ANYTHINGLLM_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

## Available Tools

### Authentication
- `tool_verify_api_key` - Verify the API key is valid

### Document Management
- `tool_upload_document` - Upload a file
- `tool_upload_document_from_url` - Upload from URL
- `tool_upload_raw_text` - Upload raw text
- `tool_list_documents` - List all documents
- `tool_get_document` - Get document details
- `tool_delete_document` - Delete documents
- `tool_create_folder` - Create a folder
- `tool_delete_folder` - Delete a folder
- `tool_move_files` - Move files between folders

### Workspace Management
- `tool_create_workspace` - Create a workspace
- `tool_list_workspaces` - List all workspaces
- `tool_get_workspace` - Get workspace details
- `tool_delete_workspace` - Delete a workspace
- `tool_update_workspace` - Update workspace settings
- `tool_add_documents_to_workspace` - Add documents
- `tool_remove_documents_from_workspace` - Remove documents
- `tool_chat_with_workspace` - Chat with workspace
- `tool_vector_search` - Search vectors

### Thread Management
- `tool_create_thread` - Create a thread
- `tool_list_threads` - List workspace threads
- `tool_delete_thread` - Delete a thread
- `tool_chat_with_thread` - Chat with thread

### System Management
- `tool_get_system_settings` - Get system settings
- `tool_update_system_settings` - Update system settings
- `tool_get_vector_count` - Get vector count
- `tool_export_chats` - Export chat history

### User Management (Admin)
- `tool_list_users` - List all users
- `tool_create_user` - Create a user
- `tool_update_user` - Update user
- `tool_delete_user` - Delete a user

## Development

### Run Tests

```bash
pytest
```

### Code Quality

```bash
# Linting
ruff check .

# Type checking
mypy src/

# Formatting
ruff format .
```

### MCP Inspector

```bash
uv run mcp dev src/anythingllm_mcp/server.py
```

## License

MIT License