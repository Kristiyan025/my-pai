"""
Documents Service - FastAPI application.

Provides REST API for storing and retrieving document content in MinIO.
This is a private service used only by the Workspace Agent.
"""

import os
import io
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from minio import Minio
from minio.error import S3Error

app = FastAPI(
    title="Documents Service",
    description="Manages document content in MinIO for the Workspace Agent",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== MinIO Configuration ==============

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "documents")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

minio_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    """Get or create MinIO client."""
    global minio_client
    if minio_client is None:
        minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
    return minio_client


def ensure_bucket():
    """Ensure the documents bucket exists."""
    client = get_minio_client()
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)


# ============== Request/Response Models ==============

class DocumentUploadResponse(BaseModel):
    uuid: str
    size: int
    content_type: str


class DocumentCopyResponse(BaseModel):
    src_uuid: str
    dest_uuid: str
    size: int


# ============== Startup Event ==============

@app.on_event("startup")
async def startup_event():
    """Initialize MinIO bucket on startup."""
    ensure_bucket()


# ============== Document Endpoints ==============

@app.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    custom_uuid: Optional[str] = Query(None, description="Optional custom UUID")
):
    """
    Upload a document and store it in MinIO.
    Returns the UUID of the stored document.
    """
    client = get_minio_client()
    
    # Generate or use provided UUID
    doc_uuid = custom_uuid if custom_uuid else str(uuid.uuid4())
    
    # Read file content
    content = await file.read()
    content_stream = io.BytesIO(content)
    content_type = file.content_type or "application/octet-stream"
    
    try:
        # Upload to MinIO
        client.put_object(
            MINIO_BUCKET,
            doc_uuid,
            content_stream,
            length=len(content),
            content_type=content_type
        )
        
        return DocumentUploadResponse(
            uuid=doc_uuid,
            size=len(content),
            content_type=content_type
        )
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")


@app.post("/documents/raw", response_model=DocumentUploadResponse)
async def upload_raw_document(
    content: bytes,
    content_type: str = Query("application/octet-stream"),
    custom_uuid: Optional[str] = Query(None, description="Optional custom UUID")
):
    """
    Upload raw bytes as a document.
    """
    client = get_minio_client()
    
    doc_uuid = custom_uuid if custom_uuid else str(uuid.uuid4())
    content_stream = io.BytesIO(content)
    
    try:
        client.put_object(
            MINIO_BUCKET,
            doc_uuid,
            content_stream,
            length=len(content),
            content_type=content_type
        )
        
        return DocumentUploadResponse(
            uuid=doc_uuid,
            size=len(content),
            content_type=content_type
        )
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")


@app.put("/documents/{doc_uuid}", response_model=DocumentUploadResponse)
async def update_document(
    doc_uuid: str,
    file: UploadFile = File(...)
):
    """
    Update an existing document's content.
    """
    client = get_minio_client()
    
    # Verify document exists
    try:
        client.stat_object(MINIO_BUCKET, doc_uuid)
    except S3Error:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Read and upload new content
    content = await file.read()
    content_stream = io.BytesIO(content)
    content_type = file.content_type or "application/octet-stream"
    
    try:
        client.put_object(
            MINIO_BUCKET,
            doc_uuid,
            content_stream,
            length=len(content),
            content_type=content_type
        )
        
        return DocumentUploadResponse(
            uuid=doc_uuid,
            size=len(content),
            content_type=content_type
        )
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")


@app.get("/documents/{doc_uuid}")
async def get_document(doc_uuid: str):
    """
    Retrieve a document by UUID.
    Returns the document content as a stream.
    """
    client = get_minio_client()
    
    try:
        # Get object
        response = client.get_object(MINIO_BUCKET, doc_uuid)
        
        # Get content type from metadata
        stat = client.stat_object(MINIO_BUCKET, doc_uuid)
        content_type = stat.content_type or "application/octet-stream"
        
        # Stream the response
        def iterfile():
            for chunk in response.stream(32 * 1024):  # 32KB chunks
                yield chunk
            response.close()
            response.release_conn()
        
        return StreamingResponse(
            iterfile(),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={doc_uuid}",
                "X-Document-UUID": doc_uuid
            }
        )
    except S3Error as e:
        if "NoSuchKey" in str(e):
            raise HTTPException(status_code=404, detail="Document not found")
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")


@app.get("/documents/{doc_uuid}/bytes")
async def get_document_bytes(doc_uuid: str):
    """
    Retrieve a document's raw bytes.
    """
    client = get_minio_client()
    
    try:
        response = client.get_object(MINIO_BUCKET, doc_uuid)
        content = response.read()
        response.close()
        response.release_conn()
        
        stat = client.stat_object(MINIO_BUCKET, doc_uuid)
        
        return {
            "uuid": doc_uuid,
            "content": content,
            "content_type": stat.content_type,
            "size": stat.size
        }
    except S3Error as e:
        if "NoSuchKey" in str(e):
            raise HTTPException(status_code=404, detail="Document not found")
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")


@app.get("/documents/{doc_uuid}/metadata")
async def get_document_metadata(doc_uuid: str):
    """
    Get document metadata without downloading content.
    """
    client = get_minio_client()
    
    try:
        stat = client.stat_object(MINIO_BUCKET, doc_uuid)
        return {
            "uuid": doc_uuid,
            "size": stat.size,
            "content_type": stat.content_type,
            "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
            "etag": stat.etag
        }
    except S3Error as e:
        if "NoSuchKey" in str(e):
            raise HTTPException(status_code=404, detail="Document not found")
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")


@app.delete("/documents/{doc_uuid}")
async def delete_document(doc_uuid: str):
    """
    Delete a document by UUID.
    """
    client = get_minio_client()
    
    try:
        # Verify document exists
        client.stat_object(MINIO_BUCKET, doc_uuid)
        
        # Delete object
        client.remove_object(MINIO_BUCKET, doc_uuid)
        
        return {"status": "deleted", "uuid": doc_uuid}
    except S3Error as e:
        if "NoSuchKey" in str(e):
            raise HTTPException(status_code=404, detail="Document not found")
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")


@app.post("/documents/{src_uuid}/copy", response_model=DocumentCopyResponse)
async def copy_document(
    src_uuid: str,
    dest_uuid: Optional[str] = Query(None, description="Optional destination UUID")
):
    """
    Copy a document to a new UUID.
    """
    client = get_minio_client()
    
    # Generate or use provided destination UUID
    new_uuid = dest_uuid if dest_uuid else str(uuid.uuid4())
    
    try:
        # Get source object
        response = client.get_object(MINIO_BUCKET, src_uuid)
        content = response.read()
        response.close()
        response.release_conn()
        
        # Get source metadata
        stat = client.stat_object(MINIO_BUCKET, src_uuid)
        
        # Upload to new UUID
        content_stream = io.BytesIO(content)
        client.put_object(
            MINIO_BUCKET,
            new_uuid,
            content_stream,
            length=len(content),
            content_type=stat.content_type
        )
        
        return DocumentCopyResponse(
            src_uuid=src_uuid,
            dest_uuid=new_uuid,
            size=len(content)
        )
    except S3Error as e:
        if "NoSuchKey" in str(e):
            raise HTTPException(status_code=404, detail="Source document not found")
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")


@app.get("/documents/{doc_uuid}/exists")
async def document_exists(doc_uuid: str):
    """
    Check if a document exists.
    """
    client = get_minio_client()
    
    try:
        client.stat_object(MINIO_BUCKET, doc_uuid)
        return {"exists": True, "uuid": doc_uuid}
    except S3Error:
        return {"exists": False, "uuid": doc_uuid}


# ============== Health Check ==============

@app.get("/health")
def health_check():
    """Health check endpoint."""
    try:
        client = get_minio_client()
        client.bucket_exists(MINIO_BUCKET)
        return {"status": "healthy", "service": "documents-service", "minio": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "service": "documents-service", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
