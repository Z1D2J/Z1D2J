"""Document management tools for AnythingLLM MCP Server."""

from typing import Any, Optional

from ..client import AnythingLLMClient


async def upload_document(
    file_path: str,
    folder_name: Optional[str] = None,
    add_to_workspaces: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    """Upload a document file to AnythingLLM.
    
    Args:
        file_path: Path to the file to upload.
        folder_name: Target folder name (optional).
        add_to_workspaces: Comma-separated workspace slugs to embed into (optional).
        metadata: Metadata for the document (optional).
    
    Returns:
        Dictionary with upload result and document information.
    """
    client = AnythingLLMClient()
    try:
        documents = await client.upload_document(
            file_path=file_path,
            folder_name=folder_name,
            add_to_workspaces=add_to_workspaces,
            metadata=metadata,
        )
        return {
            "status": "success",
            "documents": [
                {
                    "name": doc.name,
                    "title": doc.title,
                    "location": doc.location,
                    "word_count": doc.word_count,
                }
                for doc in documents
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def upload_document_from_url(
    url: str,
    add_to_workspaces: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    """Upload a document from a URL.
    
    Args:
        url: URL to scrape and upload.
        add_to_workspaces: Comma-separated workspace slugs to embed into (optional).
        metadata: Metadata for the document (optional).
    
    Returns:
        Dictionary with upload result and document information.
    """
    client = AnythingLLMClient()
    try:
        documents = await client.upload_document_from_url(
            url=url,
            add_to_workspaces=add_to_workspaces,
            metadata=metadata,
        )
        return {
            "status": "success",
            "documents": [
                {
                    "name": doc.name,
                    "title": doc.title,
                    "location": doc.location,
                    "word_count": doc.word_count,
                }
                for doc in documents
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def upload_raw_text(
    text_content: str,
    add_to_workspaces: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    """Upload raw text as a document.
    
    Args:
        text_content: Raw text content to upload.
        add_to_workspaces: Comma-separated workspace slugs to embed into (optional).
        metadata: Metadata for the document (optional).
    
    Returns:
        Dictionary with upload result and document information.
    """
    client = AnythingLLMClient()
    try:
        documents = await client.upload_raw_text(
            text_content=text_content,
            add_to_workspaces=add_to_workspaces,
            metadata=metadata,
        )
        return {
            "status": "success",
            "documents": [
                {
                    "name": doc.name,
                    "title": doc.title,
                    "location": doc.location,
                    "word_count": doc.word_count,
                }
                for doc in documents
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def list_documents(folder_name: Optional[str] = None) -> dict:
    """List all documents in AnythingLLM.
    
    Args:
        folder_name: Optional folder name to filter by.
    
    Returns:
        Dictionary with document list.
    """
    client = AnythingLLMClient()
    try:
        result = await client.list_documents(folder_name=folder_name)
        return {"status": "success", "documents": result.get("localFiles", {})}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def get_document(document_name: str) -> dict:
    """Get details of a specific document.
    
    Args:
        document_name: Name of the document to retrieve.
    
    Returns:
        Dictionary with document details.
    """
    client = AnythingLLMClient()
    try:
        result = await client.get_document(document_name)
        return {"status": "success", "document": result.get("localFiles", {})}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def delete_document(document_names: list[str]) -> dict:
    """Permanently delete documents.
    
    Args:
        document_names: List of document names to delete.
    
    Returns:
        Dictionary with deletion result.
    """
    client = AnythingLLMClient()
    try:
        result = await client.delete_documents(document_names)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def create_folder(folder_name: str) -> dict:
    """Create a document folder.
    
    Args:
        folder_name: Name of the folder to create.
    
    Returns:
        Dictionary with creation result.
    """
    client = AnythingLLMClient()
    try:
        result = await client.create_folder(folder_name)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def delete_folder(folder_name: str) -> dict:
    """Delete a document folder and its contents.
    
    Args:
        folder_name: Name of the folder to delete.
    
    Returns:
        Dictionary with deletion result.
    """
    client = AnythingLLMClient()
    try:
        result = await client.delete_folder(folder_name)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def move_files(files: list[dict[str, str]]) -> dict:
    """Move files between folders.
    
    Args:
        files: List of file movements, each with 'from' and 'to' keys.
    
    Returns:
        Dictionary with move result.
    """
    client = AnythingLLMClient()
    try:
        result = await client.move_files(files)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}