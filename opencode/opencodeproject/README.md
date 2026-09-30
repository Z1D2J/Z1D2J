# AnythingLLM MCP Server

MCP Server for accessing local AnythingLLM instance through the Model Context Protocol.

## Features

- **Document Management**: Upload, list, delete documents
- **Workspace Management**: Create, configure, and chat with workspaces
- **Thread Management**: Create and manage conversation threads
- **System Settings**: View and update system configuration
- **User Management**: Manage users (requires multi-user mode)

## Installation

### Using pip

```bash
pip install anythingllm-mcp-server
```

### Using uv (recommended)

```bash
uv add anythingllm-mcp-server
```

## Configuration

### Environment Variables

Create a `.env` file or set the following environment variables:

```bash
# AnythingLLM instance URL (default: http://localhost:3001)
ANYTHINGLLM_BASE_URL=http://localhost:3001

# AnythingLLM API Key
ANYTHINGLLM_API_KEY=your-api-key-here

# Request timeout in seconds (default: 30)
ANYTHINGLLM_TIMEOUT=30

# Enable debug logging (default: false)
ANYTHINGLLM_DEBUG=false
```

### MCP Configuration

Add the following to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "anythingllm": {
      "command": "python",
      "args": ["-m", "anythingllm_mcp.server"],
      "env": {
        "ANYTHINGLLM_BASE_URL": "http://localhost:3001",
        "ANYTHINGLLM_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

## Usage

### Running the Server

```bash
# Using uv
uv run python -m anythingllm_mcp.server

# Or using pip installed package
anythingllm-mcp-server
```

### Available Tools

#### Authentication

- `verify_api_key()` - Verify the API key is valid

#### Document Management

- `upload_document(file_path, folder_name?, add_to_workspaces?, metadata?)` - Upload a file
- `upload_document_from_url(url, add_to_workspaces?, metadata?)` - Upload from URL
- `upload_raw_text(text_content, add_to_workspaces?, metadata?)` - Upload raw text
- `list_documents(folder_name?)` - List all documents
- `get_document(document_name)` - Get document details
- `delete_document(document_names)` - Delete documents
- `create_folder(folder_name)` - Create a folder
- `delete_folder(folder_name)` - Delete a folder
- `move_files(files)` - Move files between folders

#### Workspace Management

- `create_workspace(name, settings?)` - Create a workspace
- `list_workspaces()` - List all workspaces
- `get_workspace(workspace_slug)` - Get workspace details
- `delete_workspace(workspace_slug)` - Delete a workspace
- `update_workspace(workspace_slug, settings)` - Update workspace settings
- `add_documents_to_workspace(workspace_slug, document_paths)` - Add documents
- `remove_documents_from_workspace(workspace_slug, document_paths)` - Remove documents
- `chat_with_workspace(workspace_slug, message, mode?, session_id?)` - Chat with workspace
- `vector_search(workspace_slug, query, top_n?, score_threshold?)` - Search vectors

#### Thread Management

- `create_thread(workspace_slug, name, user_id?)` - Create a thread
- `list_threads(workspace_slug)` - List workspace threads
- `delete_thread(workspace_slug, thread_slug)` - Delete a thread
- `chat_with_thread(workspace_slug, thread_slug, message, mode?)` - Chat with thread

#### System Management

- `get_system_settings()` - Get system settings
- `update_system_settings(settings)` - Update system settings
- `get_vector_count()` - Get vector count
- `export_chats(export_type?)` - Export chat history

#### User Management (Admin)

- `list_users()` - List all users
- `create_user(username, password, role?)` - Create a user
- `update_user(user_id, updates)` - Update user
- `delete_user(user_id)` - Delete a user

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/anythingllm-mcp-server.git
cd anythingllm-mcp-server

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=anythingllm_mcp

# Run specific test file
pytest tests/test_client.py
```

### Code Quality

```bash
# Run linter
ruff check .

# Run type checker
mypy src/

# Format code
ruff format .
```

### Using MCP Inspector

```bash
# Start the MCP Inspector
uv run mcp dev src/anythingllm_mcp/server.py
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.