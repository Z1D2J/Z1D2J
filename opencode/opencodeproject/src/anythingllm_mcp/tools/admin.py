"""User management tools for AnythingLLM MCP Server."""

from typing import Any, Optional

from ..client import AnythingLLMClient


async def list_users() -> dict:
    """List all users.
    
    Returns:
        Dictionary with list of users.
    """
    client = AnythingLLMClient()
    try:
        users = await client.list_users()
        return {
            "status": "success",
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                }
                for user in users
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def create_user(
    username: str,
    password: str,
    role: str = "default",
) -> dict:
    """Create a new user.
    
    Args:
        username: Username for the new user.
        password: Password for the new user.
        role: User role (default or admin).
    
    Returns:
        Dictionary with creation result.
    """
    client = AnythingLLMClient()
    try:
        result = await client.create_user(username, password, role)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def update_user(
    user_id: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
    role: Optional[str] = None,
    suspended: Optional[int] = None,
) -> dict:
    """Update user information.
    
    Args:
        user_id: ID of the user to update.
        username: New username.
        password: New password.
        role: New role.
        suspended: Suspension status (0 = active, 1 = suspended).
    
    Returns:
        Dictionary with update result.
    """
    client = AnythingLLMClient()
    try:
        updates: dict[str, Any] = {}
        if username is not None:
            updates["username"] = username
        if password is not None:
            updates["password"] = password
        if role is not None:
            updates["role"] = role
        if suspended is not None:
            updates["suspended"] = suspended
        
        result = await client.update_user(user_id, updates)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def delete_user(user_id: int) -> dict:
    """Delete a user.
    
    Args:
        user_id: ID of the user to delete.
    
    Returns:
        Dictionary with deletion result.
    """
    client = AnythingLLMClient()
    try:
        result = await client.delete_user(user_id)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}