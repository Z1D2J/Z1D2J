"""Example usage of AnythingLLM MCP Server."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Set environment variables
os.environ["ANYTHINGLLM_BASE_URL"] = "http://localhost:3001"
os.environ["ANYTHINGLLM_API_KEY"] = "your-api-key-here"

from mcp import Client


async def main():
    """Example usage of the MCP server."""
    print("Connecting to AnythingLLM MCP Server...")
    
    # Connect to the MCP server
    async with Client("anythingllm-mcp-server") as client:
        print("Connected to MCP server")
        
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:50]}...")
        
        # Verify API key
        print("\nVerifying API key...")
        result = await client.call_tool("tool_verify_api_key", {})
        print(f"API key verification: {result.structured_content}")
        
        # List workspaces
        print("\nListing workspaces...")
        result = await client.call_tool("tool_list_workspaces", {})
        print(f"Workspaces: {result.structured_content}")
        
        # List documents
        print("\nListing documents...")
        result = await client.call_tool("tool_list_documents", {})
        print(f"Documents: {result.structured_content}")
        
        # Get system settings
        print("\nGetting system settings...")
        result = await client.call_tool("tool_get_system_settings", {})
        print(f"System settings: {result.structured_content}")


if __name__ == "__main__":
    asyncio.run(main())