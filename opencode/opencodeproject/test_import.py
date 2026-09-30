"""Simple test to verify the MCP server can be imported."""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

try:
    from anythingllm_mcp.server import mcp
    print("[OK] MCP server imported successfully")
    print(f"[OK] Server name: {mcp.name}")
    print(f"[OK] Server version: {mcp.version}")
    
    # List registered tools
    tools = list(mcp._tool_manager._tools.keys()) if hasattr(mcp, '_tool_manager') else []
    print(f"[OK] Registered tools: {len(tools)}")
    for tool in sorted(tools):
        print(f"  - {tool}")
    
    print("\n[OK] Everything looks good!")
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Error: {e}")
    sys.exit(1)