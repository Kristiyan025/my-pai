"""
APIKeys Service - FastAPI application.

Provides REST API for managing API keys (e.g., Spotify) in MySQL.
This is a private service used only by the Spotify Agent.
"""

import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Add parent to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database import get_db, init_db
from models import APIKey

app = FastAPI(
    title="APIKeys Service",
    description="Manages API keys in MySQL for the Spotify Agent",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Request/Response Models ==============

class SpotifyKeyUpdate(BaseModel):
    spotify_api_key: Optional[str] = None
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None
    spotify_redirect_uri: Optional[str] = None


class APIKeyResponse(BaseModel):
    user_id: int
    has_spotify_key: bool
    spotify_client_id: Optional[str] = None
    spotify_redirect_uri: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SpotifyCredentialsResponse(BaseModel):
    """Internal response with actual credentials (for Spotify Agent only)."""
    user_id: int
    spotify_api_key: Optional[str] = None
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None
    spotify_redirect_uri: Optional[str] = None


# ============== Startup Event ==============

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


# ============== API Endpoints ==============

@app.get("/keys/{user_id}", response_model=APIKeyResponse)
def get_api_keys(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get API key metadata for a user (does not expose actual keys).
    """
    api_key = db.query(APIKey).filter(APIKey.user_id == user_id).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API keys not found for user")
    
    return APIKeyResponse(
        user_id=api_key.user_id,
        has_spotify_key=api_key.spotify_api_key is not None,
        spotify_client_id=api_key.spotify_client_id,
        spotify_redirect_uri=api_key.spotify_redirect_uri,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at
    )


@app.get("/keys/{user_id}/spotify", response_model=SpotifyCredentialsResponse)
def get_spotify_credentials(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get Spotify credentials for a user.
    This endpoint is for internal use by the Spotify Agent only.
    """
    api_key = db.query(APIKey).filter(APIKey.user_id == user_id).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API keys not found for user")
    
    return SpotifyCredentialsResponse(
        user_id=api_key.user_id,
        spotify_api_key=api_key.spotify_api_key,
        spotify_client_id=api_key.spotify_client_id,
        spotify_client_secret=api_key.spotify_client_secret,
        spotify_redirect_uri=api_key.spotify_redirect_uri
    )


@app.put("/keys/{user_id}/spotify", response_model=APIKeyResponse)
def update_spotify_key(
    user_id: int,
    spotify_data: SpotifyKeyUpdate,
    db: Session = Depends(get_db)
):
    """
    Set or update Spotify credentials for a user.
    """
    api_key = db.query(APIKey).filter(APIKey.user_id == user_id).first()
    
    if not api_key:
        # Create new record
        api_key = APIKey(
            user_id=user_id,
            spotify_api_key=spotify_data.spotify_api_key,
            spotify_client_id=spotify_data.spotify_client_id,
            spotify_client_secret=spotify_data.spotify_client_secret,
            spotify_redirect_uri=spotify_data.spotify_redirect_uri,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(api_key)
    else:
        # Update existing record
        if spotify_data.spotify_api_key is not None:
            api_key.spotify_api_key = spotify_data.spotify_api_key
        if spotify_data.spotify_client_id is not None:
            api_key.spotify_client_id = spotify_data.spotify_client_id
        if spotify_data.spotify_client_secret is not None:
            api_key.spotify_client_secret = spotify_data.spotify_client_secret
        if spotify_data.spotify_redirect_uri is not None:
            api_key.spotify_redirect_uri = spotify_data.spotify_redirect_uri
        api_key.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(api_key)
    
    return APIKeyResponse(
        user_id=api_key.user_id,
        has_spotify_key=api_key.spotify_api_key is not None,
        spotify_client_id=api_key.spotify_client_id,
        spotify_redirect_uri=api_key.spotify_redirect_uri,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at
    )


@app.delete("/keys/{user_id}/spotify")
def delete_spotify_key(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Remove Spotify credentials for a user.
    """
    api_key = db.query(APIKey).filter(APIKey.user_id == user_id).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API keys not found for user")
    
    api_key.spotify_api_key = None
    api_key.spotify_client_id = None
    api_key.spotify_client_secret = None
    api_key.spotify_redirect_uri = None
    api_key.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {"status": "deleted", "user_id": user_id}


# ============== Health Check ==============

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "apikeys-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
