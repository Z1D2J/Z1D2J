"""Pytest configuration for AnythingLLM MCP Server tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from anythingllm_mcp.config import AnythingLLMConfig
from anythingllm_mcp.client import AnythingLLMClient


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    return AnythingLLMConfig(
        base_url="http://localhost:3001",
        api_key="test-api-key",
        timeout=30,
        debug=False,
    )


@pytest.fixture
def mock_client(mock_config):
    """Create a mock client."""
    return AnythingLLMClient(config=mock_config)


@pytest.fixture
def mock_httpx_response():
    """Create a mock HTTP response."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"authenticated": True}
    response.raise_for_status = MagicMock()
    return response