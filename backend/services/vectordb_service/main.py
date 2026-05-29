"""
VectorDB Service - FastAPI application.

Provides REST API for storing and querying vector embeddings in ChromaDB.
This is a private service used only by the SDSA Agent.
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chromadb
from chromadb.config import Settings as ChromaSettings

app = FastAPI(
    title="VectorDB Service",
    description="Manages vector embeddings in ChromaDB for the SDSA Agent",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== ChromaDB Configuration ==============

CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "/data/chroma")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "documents")

# Initialize ChromaDB client with persistence
chroma_client: Optional[chromadb.PersistentClient] = None
collection = None


def get_chroma_collection():
    """Get or create the ChromaDB collection."""
    global chroma_client, collection
    
    if chroma_client is None:
        chroma_client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIRECTORY,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
    
    if collection is None:
        collection = chroma_client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
    
    return collection


# ============== Request/Response Models ==============

class EmbeddingAddRequest(BaseModel):
    chunk_id: str
    embedding: List[float]
    document: str  # Chunk content or "user::filepath" for images
    metadata: Dict[str, Any]


class EmbeddingBatchAddRequest(BaseModel):
    embeddings: List[EmbeddingAddRequest]


class EmbeddingQueryRequest(BaseModel):
    embedding: List[float]
    k: int = 5
    filter_metadata: Optional[Dict[str, Any]] = None


class EmbeddingQueryResult(BaseModel):
    chunk_id: str
    document: str
    metadata: Dict[str, Any]
    distance: float


class EmbeddingQueryResponse(BaseModel):
    results: List[EmbeddingQueryResult]


class DeleteByPrefixRequest(BaseModel):
    prefix: str


# ============== Startup Event ==============

@app.on_event("startup")
async def startup_event():
    """Initialize ChromaDB collection on startup."""
    get_chroma_collection()


# ============== Embedding Endpoints ==============

@app.post("/embeddings")
def add_embedding(request: EmbeddingAddRequest):
    """
    Add a single embedding to the vector database.
    If an embedding with the same chunk_id exists, it will be upserted.
    """
    coll = get_chroma_collection()
    
    try:
        # Upsert the embedding
        coll.upsert(
            ids=[request.chunk_id],
            embeddings=[request.embedding],
            documents=[request.document],
            metadatas=[request.metadata]
        )
        
        return {"status": "added", "chunk_id": request.chunk_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add embedding: {str(e)}")


@app.post("/embeddings/batch")
def add_embeddings_batch(request: EmbeddingBatchAddRequest):
    """
    Add multiple embeddings in a batch.
    """
    coll = get_chroma_collection()
    
    if not request.embeddings:
        return {"status": "success", "count": 0}
    
    try:
        # Prepare batch data
        ids = [e.chunk_id for e in request.embeddings]
        embeddings = [e.embedding for e in request.embeddings]
        documents = [e.document for e in request.embeddings]
        metadatas = [e.metadata for e in request.embeddings]
        
        # Upsert batch
        coll.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        return {"status": "added", "count": len(ids)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add embeddings: {str(e)}")


@app.post("/embeddings/query", response_model=EmbeddingQueryResponse)
def query_embeddings(request: EmbeddingQueryRequest):
    """
    Query for the top K most similar embeddings.
    """
    coll = get_chroma_collection()
    
    try:
        # Build query parameters
        query_params = {
            "query_embeddings": [request.embedding],
            "n_results": request.k,
            "include": ["documents", "metadatas", "distances"]
        }
        
        if request.filter_metadata:
            query_params["where"] = request.filter_metadata
        
        # Execute query
        results = coll.query(**query_params)
        
        # Format results
        query_results = []
        if results and results['ids'] and results['ids'][0]:
            for i, chunk_id in enumerate(results['ids'][0]):
                query_results.append(EmbeddingQueryResult(
                    chunk_id=chunk_id,
                    document=results['documents'][0][i] if results['documents'] else "",
                    metadata=results['metadatas'][0][i] if results['metadatas'] else {},
                    distance=results['distances'][0][i] if results['distances'] else 0.0
                ))
        
        return EmbeddingQueryResponse(results=query_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query embeddings: {str(e)}")


@app.get("/embeddings/{chunk_id}")
def get_embedding(chunk_id: str):
    """
    Get a specific embedding by chunk_id.
    """
    coll = get_chroma_collection()
    
    try:
        result = coll.get(
            ids=[chunk_id],
            include=["documents", "metadatas", "embeddings"]
        )
        
        if not result['ids']:
            raise HTTPException(status_code=404, detail="Embedding not found")
        
        return {
            "chunk_id": chunk_id,
            "document": result['documents'][0] if result['documents'] else None,
            "metadata": result['metadatas'][0] if result['metadatas'] else None,
            "embedding": result['embeddings'][0] if result['embeddings'] else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get embedding: {str(e)}")


@app.delete("/embeddings/{chunk_id}")
def delete_embedding(chunk_id: str):
    """
    Delete an embedding by chunk_id.
    """
    coll = get_chroma_collection()
    
    try:
        coll.delete(ids=[chunk_id])
        return {"status": "deleted", "chunk_id": chunk_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete embedding: {str(e)}")


@app.post("/embeddings/delete-by-prefix")
def delete_by_prefix(request: DeleteByPrefixRequest):
    """
    Delete all embeddings whose chunk_id starts with the given prefix.
    Useful for deleting all embeddings for a specific file.
    """
    coll = get_chroma_collection()
    
    try:
        # Get all matching IDs first
        # ChromaDB doesn't support prefix queries directly, so we need to get all and filter
        all_results = coll.get(include=[])
        
        if not all_results['ids']:
            return {"status": "success", "deleted_count": 0}
        
        # Filter by prefix
        ids_to_delete = [
            id for id in all_results['ids'] 
            if id.startswith(request.prefix)
        ]
        
        if ids_to_delete:
            coll.delete(ids=ids_to_delete)
        
        return {"status": "deleted", "deleted_count": len(ids_to_delete)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete embeddings: {str(e)}")


@app.delete("/embeddings/by-metadata")
def delete_by_metadata(
    user_id: int = Query(...),
    source_type: str = Query(...),
    source_id: str = Query(...)
):
    """
    Delete all embeddings matching specific metadata.
    """
    coll = get_chroma_collection()
    
    try:
        # Query for matching embeddings
        results = coll.get(
            where={
                "$and": [
                    {"user_id": user_id},
                    {"source_type": source_type},
                    {"source_id": source_id}
                ]
            },
            include=[]
        )
        
        if results['ids']:
            coll.delete(ids=results['ids'])
        
        return {"status": "deleted", "deleted_count": len(results['ids']) if results['ids'] else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete embeddings: {str(e)}")


@app.get("/embeddings/count")
def get_embedding_count():
    """
    Get the total number of embeddings in the collection.
    """
    coll = get_chroma_collection()
    
    try:
        count = coll.count()
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to count embeddings: {str(e)}")


@app.post("/embeddings/reset")
def reset_collection():
    """
    Reset (clear) the entire collection.
    WARNING: This deletes all embeddings.
    """
    global collection
    
    try:
        client = chroma_client
        if client:
            client.delete_collection(CHROMA_COLLECTION_NAME)
            collection = client.get_or_create_collection(
                name=CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
        
        return {"status": "reset", "collection": CHROMA_COLLECTION_NAME}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset collection: {str(e)}")


# ============== Health Check ==============

@app.get("/health")
def health_check():
    """Health check endpoint."""
    try:
        coll = get_chroma_collection()
        count = coll.count()
        return {
            "status": "healthy", 
            "service": "vectordb-service",
            "collection": CHROMA_COLLECTION_NAME,
            "embedding_count": count
        }
    except Exception as e:
        return {"status": "unhealthy", "service": "vectordb-service", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
