"""Authentication tools for AnythingLLM MCP Server."""

from ..client import AnythingLLMClient


async def verify_api_key() -> dict:
    """Verify the AnythingLLM API key is valid.
    
    Returns:
        Dictionary with verification result and status.
    """
    client = AnythingLLMClient()
    is_valid = await client.verify_api_key()
    
    return {
        "status": "success" if is_valid else "error",
        "authenticated": is_valid,
        "message": "API key is valid" if is_valid else "API key is invalid or server is unreachable",
    }