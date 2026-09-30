"""Test script to verify the MCP server can handle requests."""

import subprocess
import sys
import time
import os
import json

def test_server_requests():
    """Test if the MCP server can handle requests."""
    print("Testing MCP server requests...")
    
    # Start the server process
    env = os.environ.copy()
    env["ANYTHINGLLM_BASE_URL"] = "http://localhost:3001"
    env["ANYTHINGLLM_API_KEY"] = "test-api-key"
    env["PYTHONPATH"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
    
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "anythingllm_mcp.server"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        # Wait for the server to start
        time.sleep(1)
        
        # Send a simple MCP request (server/discover)
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "server/discover",
            "params": {},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                },
                "io.modelcontextprotocol/clientCapabilities": {}
            }
        }
        
        # Write the request to stdin
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        
        # Wait for the response
        time.sleep(1)
        
        # Check if the process is still running
        if process.poll() is None:
            print("[OK] Server is running")
            # Terminate the server
            process.terminate()
            process.wait(timeout=5)
            print("[OK] Server terminated successfully")
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"[ERROR] Server stopped unexpectedly")
            print(f"stdout: {stdout}")
            print(f"stderr: {stderr}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error testing server: {e}")
        return False

if __name__ == "__main__":
    success = test_server_requests()
    sys.exit(0 if success else 1)