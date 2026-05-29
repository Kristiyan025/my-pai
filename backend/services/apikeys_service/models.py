"""
SQLAlchemy database models for APIKeys Service.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class APIKey(Base):
    """
    API Keys table - stores API keys (e.g., Spotify) per user.
    
    Purpose: Store user's API keys for external services.
    
    Columns:
        - user_id: User ID (PK)
        - spotify_api_key: Spotify API key (nullable)
        - created_at: When the record was created
        - updated_at: When the record was last updated
    
    Constraints:
        - PK: user_id
    """
    __tablename__ = "api_keys"
    
    user_id = Column(Integer, primary_key=True, autoincrement=False)
    spotify_api_key = Column(String(500), nullable=True)
    spotify_client_id = Column(String(255), nullable=True)
    spotify_client_secret = Column(String(255), nullable=True)
    spotify_redirect_uri = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
