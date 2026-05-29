"""
SQLAlchemy database models for FileSystem Service.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Index, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """
    User table - contains the single hardcoded user (user_id=1).
    Exists for referential integrity.
    """
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, autoincrement=False)
    
    # Relationships
    files = relationship("File", back_populates="user", cascade="all, delete-orphan")
    subdirectories = relationship("Subdirectory", back_populates="user", cascade="all, delete-orphan")


class File(Base):
    """
    Files table - maps user file paths to content UUIDs in MinIO.
    
    Purpose: Track workspace files with their locations and metadata.
    
    Columns:
        - id: Auto-increment primary key
        - user_id: Owner user ID (FK to users)
        - filepath: Full path in workspace (e.g., /dir1/file.txt)
        - uuid: UUID of content in DocumentsService (MinIO)
        - file_type: File extension/type (e.g., "txt", "png")
        - created_at: Timestamp when file was created
        - updated_at: Timestamp when file was last updated
    
    Constraints:
        - PK: id (auto-increment)
        - Unique: (user_id, filepath) - each user's file paths are unique
        - Unique: (user_id, uuid) - each content UUID is unique per user
        - Index on user_id for quick directory listing
    """
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    filepath = Column(String(500), nullable=False)
    uuid = Column(String(36), nullable=False)
    file_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_files_user_filepath', 'user_id', 'filepath', unique=True),
        Index('idx_files_user_id', 'user_id'),
        Index('idx_files_user_uuid', 'user_id', 'uuid', unique=True),
    )
    
    # Relationship
    user = relationship("User", back_populates="files")


class Subdirectory(Base):
    """
    Subdirectories table - maps a directory to its direct children subdirectories.
    
    Purpose: Track directory structure for efficient listing.
    
    Columns:
        - id: Auto-increment primary key
        - user_id: Owner user ID (FK to users)
        - directory: Parent directory path (e.g., /dir1)
        - subdirectory: Name of subfolder (e.g., subdirA)
        - created_at: Timestamp when subdirectory was created
        - updated_at: Timestamp when subdirectory was last updated
    
    Constraints:
        - PK: id
        - Unique: (user_id, directory, subdirectory)
        - Index on (user_id, directory) for quick subdirectory listing
    """
    __tablename__ = "subdirectories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    directory = Column(String(500), nullable=False)
    subdirectory = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_subdirs_unique', 'user_id', 'directory', 'subdirectory', unique=True),
        Index('idx_subdirs_user_dir', 'user_id', 'directory'),
    )
    
    # Relationship
    user = relationship("User", back_populates="subdirectories")
