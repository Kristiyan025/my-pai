import os
import sys
from typing import List, Optional, Any, Dict
import base64

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from chunkers import DocumentChunker
from chunk_embedders import ChunkEmbedder, process_document, process_chat_message
import text_embedder
import image_embedder

app = FastAPI(
    title="SDSA Agent",
    description="Semantic Document Store Agent - Manages document embeddings",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VECTORDB_SERVICE_URL = os.getenv("VECTORDB_SERVICE_URL", "http://vectordb-service:8005")
CHATSTORE_AGENT_URL = os.getenv("CHATSTORE_AGENT_URL", "http://chatstore-agent:8011")
USER_ID = 1


class DocumentIndexRequest(BaseModel):
    user_id: int = USER_ID
    filepath: str
    content: str
    file_type: str
    is_base64: bool = False


class MessageIndexRequest(BaseModel):
    user_id: int = USER_ID
    chat_id: int
    message_id: int


class DocumentDeleteRequest(BaseModel):
    user_id: int = USER_ID
    filepath: str


class SimilarityQueryRequest(BaseModel):
    query_text: Optional[str] = None
    query_embedding: Optional[List[float]] = None
    k: int = 5
    filter_user_id: Optional[int] = None
    filter_source_type: Optional[str] = None


class SimilarityResult(BaseModel):
    chunk_id: str
    document: str
    metadata: Dict[str, Any]
    distance: float


class SimilarityQueryResponse(BaseModel):
    results: List[SimilarityResult]


async def store_embedding(embedding_result):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{VECTORDB_SERVICE_URL}/embeddings",
            json={
                "chunk_id": embedding_result.chunk_id,
                "embedding": embedding_result.embedding,
                "document": embedding_result.document,
                "metadata": embedding_result.metadata
            }
        )
        response.raise_for_status()


async def delete_embeddings_by_source(user_id: int, source_type: str, source_id: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{VECTORDB_SERVICE_URL}/embeddings/by-metadata",
            params={
                "user_id": user_id,
                "source_type": source_type,
                "source_id": source_id
            }
        )
        response.raise_for_status()


async def get_message_with_context(chat_id: int, message_id: int, context_count: int = 3):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{CHATSTORE_AGENT_URL}/chats/{chat_id}/messages/{message_id}/context",
            params={"context_count": context_count}
        )
        response.raise_for_status()
        return response.json()


@app.post("/documents/index")
async def index_document(request: DocumentIndexRequest):
    try:
        if request.is_base64:
            content = base64.b64decode(request.content)
        else:
            content = request.content
        
        try:
            await delete_embeddings_by_source(
                user_id=request.user_id,
                source_type="file",
                source_id=request.filepath
            )
        except Exception as e:
            print(f"Warning: Could not delete existing embeddings: {e}")
        
        chunk_embedder = ChunkEmbedder()
        embedding_count = 0
        
        async for embedding_result in process_document(
            content=content,
            file_type=request.file_type,
            user_id=request.user_id,
            filepath=request.filepath,
            chunk_embedder=chunk_embedder
        ):
            await store_embedding(embedding_result)
            embedding_count += 1
        
        text_embedder.unload_model()
        image_embedder.unload_model()
        
        return {
            "status": "indexed",
            "filepath": request.filepath,
            "embeddings_created": embedding_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@app.post("/documents/delete")
async def delete_document_embeddings(request: DocumentDeleteRequest):
    try:
        await delete_embeddings_by_source(
            user_id=request.user_id,
            source_type="file",
            source_id=request.filepath
        )
        
        return {
            "status": "deleted",
            "filepath": request.filepath
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@app.post("/messages/index")
async def index_message(request: MessageIndexRequest):
    try:
        # Get message with context
        context_data = await get_message_with_context(
            chat_id=request.chat_id,
            message_id=request.message_id,
            context_count=3
        )
        
        messages = context_data.get("messages", [])
        if not messages:
            raise HTTPException(status_code=404, detail="Message not found")
        
        target_message = None
        context_messages = []
        
        for msg in messages:
            if msg["message_id"] == request.message_id:
                target_message = msg
            else:
                context_messages.append(f"[{msg['user_role']}]: {msg['message_text']}")
        
        if not target_message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        source_id = f"chat:{request.chat_id}:msg:{request.message_id}"
        try:
            await delete_embeddings_by_source(
                user_id=request.user_id,
                source_type="message",
                source_id=source_id
            )
        except Exception:
            pass
        
        chunk_embedder = ChunkEmbedder()
        embedding_count = 0
        
        async for embedding_result in process_chat_message(
            message_text=target_message["message_text"],
            user_id=request.user_id,
            chat_id=request.chat_id,
            message_id=request.message_id,
            context_messages=context_messages,
            chunk_embedder=chunk_embedder
        ):
            await store_embedding(embedding_result)
            embedding_count += 1
        
        text_embedder.unload_model()
        
        return {
            "status": "indexed",
            "chat_id": request.chat_id,
            "message_id": request.message_id,
            "embeddings_created": embedding_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@app.post("/query", response_model=SimilarityQueryResponse)
async def query_similar(request: SimilarityQueryRequest):
    try:
        if request.query_embedding:
            embedding = request.query_embedding
        elif request.query_text:
            embedding = text_embedder.embed_text(request.query_text)
            text_embedder.unload_model()
        else:
            raise HTTPException(status_code=400, detail="Must provide query_text or query_embedding")
        
        filter_metadata = None
        if request.filter_user_id or request.filter_source_type:
            filter_metadata = {}
            if request.filter_user_id:
                filter_metadata["user_id"] = request.filter_user_id
            if request.filter_source_type:
                filter_metadata["source_type"] = request.filter_source_type
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{VECTORDB_SERVICE_URL}/embeddings/query",
                json={
                    "embedding": embedding,
                    "k": request.k,
                    "filter_metadata": filter_metadata
                }
            )
            response.raise_for_status()
            
            data = response.json()
            results = [
                SimilarityResult(
                    chunk_id=r["chunk_id"],
                    document=r["document"],
                    metadata=r["metadata"],
                    distance=r["distance"]
                )
                for r in data.get("results", [])
            ]
            
            return SimilarityQueryResponse(results=results)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/query/text")
async def query_by_text(
    query: str = Query(..., description="Text query"),
    k: int = Query(5, ge=1, le=50, description="Number of results"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    source_type: Optional[str] = Query(None, description="Filter by source type (file/message)")
):
    request = SimilarityQueryRequest(
        query_text=query,
        k=k,
        filter_user_id=user_id,
        filter_source_type=source_type
    )
    return await query_similar(request)


@app.post("/embed/text")
async def embed_text_endpoint(text: str):
    try:
        embedding = text_embedder.embed_text(text)
        text_embedder.unload_model()
        return {"embedding": embedding, "dimension": len(embedding)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")


@app.post("/embed/image")
async def embed_image_endpoint(image_base64: str):
    try:
        image_data = base64.b64decode(image_base64)
        embedding = image_embedder.embed_image(image_data)
        image_embedder.unload_model()
        return {"embedding": embedding, "dimension": len(embedding)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "sdsa-agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012)
