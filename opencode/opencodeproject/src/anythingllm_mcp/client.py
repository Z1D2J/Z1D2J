"""AnythingLLM API client for MCP Server."""

import logging
from typing import Any, Optional

import httpx

from .config import AnythingLLMConfig, get_config
from .models import (
    ChatMessage,
    Document,
    SystemSettings,
    Thread,
    User,
    Workspace,
)

logger = logging.getLogger(__name__)


class AnythingLLMClient:
    """Client for interacting with AnythingLLM API."""
    
    def __init__(self, config: Optional[AnythingLLMConfig] = None):
        """Initialize the client."""
        self.config = config or get_config()
        self.base_url = self.config.base_url.rstrip("/api").rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make an API request."""
        url = f"{self.base_url}/api{endpoint}"
        
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=self.headers, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=self.headers, json=data)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=self.headers, json=data)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Request error: {e}")
                raise
    
    # Authentication
    
    async def verify_api_key(self) -> bool:
        """Verify API key is valid."""
        try:
            result = await self._request("GET", "/v1/auth")
            return result.get("authenticated", False)
        except Exception:
            return False
    
    # Documents
    
    async def upload_document(
        self,
        file_path: str,
        folder_name: Optional[str] = None,
        add_to_workspaces: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[Document]:
        """Upload a document file."""
        url = f"{self.base_url}/api/v1/document/upload"
        if folder_name:
            url = f"{url}/{folder_name}"
        
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            with open(file_path, "rb") as f:
                files = {"file": f}
                data = {}
                if add_to_workspaces:
                    data["addToWorkspaces"] = add_to_workspaces
                if metadata:
                    data["metadata"] = metadata
                
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                result = response.json()
        
        documents = []
        for doc_data in result.get("documents", []):
            documents.append(Document.from_dict(doc_data))
        return documents
    
    async def upload_document_from_url(
        self,
        url: str,
        add_to_workspaces: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[Document]:
        """Upload a document from URL."""
        data: dict[str, Any] = {"link": url}
        if add_to_workspaces:
            data["addToWorkspaces"] = add_to_workspaces
        if metadata:
            data["metadata"] = metadata
        
        result = await self._request("POST", "/v1/document/upload-link", data)
        documents = []
        for doc_data in result.get("documents", []):
            documents.append(Document.from_dict(doc_data))
        return documents
    
    async def upload_raw_text(
        self,
        text_content: str,
        add_to_workspaces: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[Document]:
        """Upload raw text as document."""
        data: dict[str, Any] = {"textContent": text_content}
        if add_to_workspaces:
            data["addToWorkspaces"] = add_to_workspaces
        if metadata:
            data["metadata"] = metadata
        
        result = await self._request("POST", "/v1/document/raw-text", data)
        documents = []
        for doc_data in result.get("documents", []):
            documents.append(Document.from_dict(doc_data))
        return documents
    
    async def list_documents(self, folder_name: Optional[str] = None) -> dict[str, Any]:
        """List all documents."""
        params = {}
        if folder_name:
            params["folder"] = folder_name
        return await self._request("GET", "/v1/documents", params=params)
    
    async def get_document(self, document_name: str) -> dict[str, Any]:
        """Get a single document."""
        return await self._request("GET", f"/v1/document/{document_name}")
    
    async def delete_documents(self, document_names: list[str]) -> dict[str, Any]:
        """Permanently delete documents."""
        return await self._request(
            "DELETE", "/v1/system/remove-documents", {"names": document_names}
        )
    
    async def create_folder(self, folder_name: str) -> dict[str, Any]:
        """Create a document folder."""
        return await self._request(
            "POST", "/v1/document/create-folder", {"name": folder_name}
        )
    
    async def delete_folder(self, folder_name: str) -> dict[str, Any]:
        """Delete a document folder."""
        return await self._request(
            "DELETE", "/v1/document/remove-folder", {"name": folder_name}
        )
    
    async def move_files(self, files: list[dict[str, str]]) -> dict[str, Any]:
        """Move files."""
        return await self._request("POST", "/v1/document/move-files", {"files": files})
    
    # Workspaces
    
    async def create_workspace(
        self,
        name: str,
        settings: Optional[dict[str, Any]] = None,
    ) -> Workspace:
        """Create a new workspace."""
        data: dict[str, Any] = {"name": name}
        if settings:
            data.update(settings)
        
        result = await self._request("POST", "/v1/workspace/new", data)
        return Workspace.from_dict(result.get("workspace", {}))
    
    async def list_workspaces(self) -> list[Workspace]:
        """List all workspaces."""
        result = await self._request("GET", "/v1/workspaces")
        workspaces = []
        for ws_data in result.get("workspaces", []):
            workspaces.append(Workspace.from_dict(ws_data))
        return workspaces
    
    async def get_workspace(self, workspace_slug: str) -> Workspace:
        """Get workspace details."""
        result = await self._request("GET", f"/v1/workspace/{workspace_slug}")
        return Workspace.from_dict(result.get("workspace", {}))
    
    async def delete_workspace(self, workspace_slug: str) -> dict[str, Any]:
        """Delete a workspace."""
        return await self._request("DELETE", f"/v1/workspace/{workspace_slug}")
    
    async def update_workspace(
        self,
        workspace_slug: str,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Update workspace settings."""
        return await self._request(
            "POST", f"/v1/workspace/{workspace_slug}/update", settings
        )
    
    async def update_embeddings(
        self,
        workspace_slug: str,
        adds: list[str],
        deletes: list[str],
    ) -> dict[str, Any]:
        """Add or remove documents from workspace."""
        return await self._request(
            "POST",
            f"/v1/workspace/{workspace_slug}/update-embeddings",
            {"adds": adds, "deletes": deletes},
        )
    
    async def chat(
        self,
        workspace_slug: str,
        message: str,
        mode: str = "chat",
        session_id: Optional[str] = None,
        attachments: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Chat with workspace."""
        data: dict[str, Any] = {"message": message, "mode": mode}
        if session_id:
            data["sessionId"] = session_id
        if attachments:
            data["attachments"] = attachments
        
        return await self._request(
            "POST", f"/v1/workspace/{workspace_slug}/chat", data
        )
    
    async def vector_search(
        self,
        workspace_slug: str,
        query: str,
        top_n: int = 4,
        score_threshold: float = 0.75,
    ) -> dict[str, Any]:
        """Perform vector search."""
        return await self._request(
            "POST",
            f"/v1/workspace/{workspace_slug}/vector-search",
            {"query": query, "topN": top_n, "scoreThreshold": score_threshold},
        )
    
    # Workspace Threads
    
    async def create_thread(
        self,
        workspace_slug: str,
        name: str,
        user_id: Optional[int] = None,
    ) -> Thread:
        """Create a new thread."""
        data: dict[str, Any] = {"name": name}
        if user_id:
            data["userId"] = user_id
        
        result = await self._request(
            "POST", f"/v1/workspace/{workspace_slug}/thread/new", data
        )
        return Thread.from_dict(result.get("thread", {}))
    
    async def list_threads(self, workspace_slug: str) -> list[Thread]:
        """List workspace threads."""
        result = await self._request(
            "GET", f"/v1/workspace/{workspace_slug}/chats"
        )
        threads = []
        for thread_data in result.get("threads", []):
            threads.append(Thread.from_dict(thread_data))
        return threads
    
    async def delete_thread(self, workspace_slug: str, thread_slug: str) -> dict[str, Any]:
        """Delete a thread."""
        return await self._request(
            "DELETE", f"/v1/workspace/{workspace_slug}/thread/{thread_slug}"
        )
    
    async def chat_with_thread(
        self,
        workspace_slug: str,
        thread_slug: str,
        message: str,
        mode: str = "chat",
    ) -> dict[str, Any]:
        """Chat with thread."""
        return await self._request(
            "POST",
            f"/v1/workspace/{workspace_slug}/thread/{thread_slug}/chat",
            {"message": message, "mode": mode},
        )
    
    # System
    
    async def get_system_settings(self) -> SystemSettings:
        """Get system settings."""
        result = await self._request("GET", "/v1/system")
        return SystemSettings.from_dict(result)
    
    async def update_system_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Update system settings."""
        return await self._request("POST", "/v1/system/update-env", settings)
    
    async def get_vector_count(self) -> int:
        """Get vector count."""
        result = await self._request("GET", "/v1/system/vector-count")
        return result.get("vectorCount", 0)
    
    async def export_chats(self, export_type: str = "json") -> list[dict[str, Any]]:
        """Export chat history."""
        return await self._request(
            "GET", "/v1/system/export-chats", params={"type": export_type}
        )
    
    # Users (Admin)
    
    async def list_users(self) -> list[User]:
        """List all users."""
        result = await self._request("GET", "/v1/users")
        users = []
        for user_data in result.get("users", []):
            users.append(User.from_dict(user_data))
        return users
    
    async def create_user(
        self,
        username: str,
        password: str,
        role: str = "default",
    ) -> dict[str, Any]:
        """Create a new user."""
        return await self._request(
            "POST",
            "/v1/admin/users/new",
            {"username": username, "password": password, "role": role},
        )
    
    async def update_user(
        self,
        user_id: int,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update user."""
        return await self._request(
            "POST", f"/v1/admin/users/{user_id}", updates
        )
    
    async def delete_user(self, user_id: int) -> dict[str, Any]:
        """Delete user."""
        return await self._request("DELETE", f"/v1/admin/users/{user_id}")