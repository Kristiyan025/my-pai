"""
Shared utility functions for My PAI backend services.
"""

import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple
import httpx
from fastapi import HTTPException


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def normalize_path(path: str) -> str:
    """
    Normalize a file path:
    - Ensure it starts with /
    - Remove trailing slashes
    - Collapse multiple slashes
    - Resolve .. and .
    """
    if not path:
        return "/"
    
    # Ensure starts with /
    if not path.startswith("/"):
        path = "/" + path
    
    # Collapse multiple slashes
    path = re.sub(r'/+', '/', path)
    
    # Resolve path components
    parts = path.split("/")
    resolved = []
    for part in parts:
        if part == "" or part == ".":
            continue
        elif part == "..":
            if resolved:
                resolved.pop()
        else:
            resolved.append(part)
    
    result = "/" + "/".join(resolved)
    return result if result != "/" else "/"


def get_parent_directory(filepath: str) -> str:
    """Get the parent directory of a file path."""
    normalized = normalize_path(filepath)
    if normalized == "/":
        return "/"
    parent = str(Path(normalized).parent)
    return parent if parent != "" else "/"


def get_filename(filepath: str) -> str:
    """Get the filename from a file path."""
    return Path(filepath).name


def get_file_extension(filepath: str) -> str:
    """Get the file extension (without dot) from a filepath."""
    ext = Path(filepath).suffix
    return ext[1:].lower() if ext else ""


def join_path(*parts: str) -> str:
    """Join path parts and normalize."""
    joined = "/".join(p.strip("/") for p in parts if p)
    return normalize_path(joined)


def generate_chunk_id(user_id: int, source_type: str, source_id: str, 
                      chunk_type: str, chunk_index: int, 
                      embedding_type: str = "text") -> str:
    """
    Generate a unique chunk ID for vector database.
    
    Args:
        user_id: User ID
        source_type: "file" or "message"
        source_id: Filepath or message identifier
        chunk_type: "text" or "image"
        chunk_index: Index of the chunk
        embedding_type: "text" or "vision"
    """
    raw = f"{user_id}:{source_type}:{source_id}:{chunk_type}:{chunk_index}:{embedding_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def extract_file_references(text: str) -> List[str]:
    """
    Extract file references from message text.
    References are in format: <file path="/path/to/file"/>
    """
    pattern = r'<file\s+path=["\']([^"\']+)["\']\s*/>'
    return re.findall(pattern, text)


def is_image_file(file_type: str) -> bool:
    """Check if file type is an image."""
    return file_type.lower() in ["png", "jpeg", "jpg", "webp", "bmp", "gif"]


def is_document_file(file_type: str) -> bool:
    """Check if file type is a document (Office/PDF)."""
    return file_type.lower() in ["pdf", "doc", "docx", "pptx"]


def is_code_file(file_type: str) -> bool:
    """Check if file type is a code file."""
    return file_type.lower() in [
        "py", "cpp", "h", "hpp", "java", "r", "js", "ts", 
        "html", "css", "json", "yaml", "yml", "xml"
    ]


def is_text_file(file_type: str) -> bool:
    """Check if file type is a text file."""
    return file_type.lower() in ["txt", "csv", "md", "mdx"]


def is_notebook_file(file_type: str) -> bool:
    """Check if file type is a Jupyter notebook."""
    return file_type.lower() == "ipynb"


async def make_sync_request(
    method: str,
    url: str,
    json_data: Optional[dict] = None,
    data: Optional[dict] = None,
    files: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: float = 30.0,
    headers: Optional[dict] = None
) -> httpx.Response:
    """
    Make a synchronous HTTP request to another service.
    All inter-service communication is synchronous as per requirements.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.request(
                method=method,
                url=url,
                json=json_data,
                data=data,
                files=files,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Service error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Service unavailable: {str(e)}"
            )


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to be safe for storage."""
    # Remove path separators and null bytes
    filename = filename.replace("/", "_").replace("\\", "_").replace("\0", "")
    # Remove potentially dangerous characters
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    return filename


def validate_path_security(path: str, base_dir: str = "/") -> bool:
    """
    Validate that a path doesn't escape the base directory.
    Prevents directory traversal attacks.
    """
    normalized = normalize_path(path)
    normalized_base = normalize_path(base_dir)
    
    # Check if normalized path starts with base
    return normalized.startswith(normalized_base) or normalized_base == "/"


def get_mime_type(file_type: str) -> str:
    """Get MIME type for a file extension."""
    mime_types = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "gif": "image/gif",
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ipynb": "application/x-ipynb+json",
        "md": "text/markdown",
        "mdx": "text/markdown",
        "py": "text/x-python",
        "cpp": "text/x-c++src",
        "h": "text/x-chdr",
        "hpp": "text/x-c++hdr",
        "java": "text/x-java",
        "r": "text/x-r",
        "js": "application/javascript",
        "ts": "application/typescript",
        "html": "text/html",
        "css": "text/css",
        "json": "application/json",
        "yaml": "application/x-yaml",
        "yml": "application/x-yaml",
        "xml": "application/xml",
        "txt": "text/plain",
        "csv": "text/csv"
    }
    return mime_types.get(file_type.lower(), "application/octet-stream")
