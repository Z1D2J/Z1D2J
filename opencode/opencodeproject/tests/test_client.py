"""Tests for AnythingLLM MCP Server client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from anythingllm_mcp.client import AnythingLLMClient
from anythingllm_mcp.config import AnythingLLMConfig


@pytest.fixture
def config():
    """Create a test configuration."""
    return AnythingLLMConfig(
        base_url="http://localhost:3001",
        api_key="test-api-key",
        timeout=30,
    )


@pytest.fixture
def client(config):
    """Create a test client."""
    return AnythingLLMClient(config=config)


@pytest.mark.asyncio
async def test_verify_api_key_success(client):
    """Test successful API key verification."""
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {"authenticated": True}
        result = await client.verify_api_key()
        assert result is True
        mock_request.assert_called_once_with("GET", "/v1/auth")


@pytest.mark.asyncio
async def test_verify_api_key_failure(client):
    """Test failed API key verification."""
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = Exception("Unauthorized")
        result = await client.verify_api_key()
        assert result is False


@pytest.mark.asyncio
async def test_list_workspaces(client):
    """Test listing workspaces."""
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {
            "workspaces": [
                {"id": 1, "name": "Test Workspace", "slug": "test-workspace"}
            ]
        }
        workspaces = await client.list_workspaces()
        assert len(workspaces) == 1
        assert workspaces[0].name == "Test Workspace"
        assert workspaces[0].slug == "test-workspace"


@pytest.mark.asyncio
async def test_create_workspace(client):
    """Test creating a workspace."""
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {
            "workspace": {"id": 1, "name": "New Workspace", "slug": "new-workspace"}
        }
        workspace = await client.create_workspace("New Workspace")
        assert workspace.name == "New Workspace"
        assert workspace.slug == "new-workspace"


@pytest.mark.asyncio
async def test_chat(client):
    """Test chatting with workspace."""
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {
            "textResponse": "Hello! How can I help you?",
            "sources": [],
            "type": "chat",
        }
        result = await client.chat("test-workspace", "Hello")
        assert result["textResponse"] == "Hello! How can I help you?"


@pytest.mark.asyncio
async def test_vector_search(client):
    """Test vector search."""
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {
            "results": [
                {"chunk": "Test chunk", "score": 0.95, "metadata": {}}
            ],
            "searchMode": "vector",
        }
        result = await client.vector_search("test-workspace", "test query")
        assert len(result["results"]) == 1
        assert result["results"][0]["score"] == 0.95