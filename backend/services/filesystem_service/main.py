"""
FileSystem Service - FastAPI application.

Provides REST API for managing file metadata (paths, UUIDs, etc.) in MySQL.
This is a private service used only by the Workspace Agent.
"""

import os
import sys
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Add parent to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database import get_db, init_db
from models import File, Subdirectory, User

app = FastAPI(
    title="FileSystem Service",
    description="Manages file metadata in MySQL for the Workspace Agent",
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

class FileRecordCreate(BaseModel):
    user_id: int
    filepath: str
    uuid: str
    file_type: str


class FileRecordUpdate(BaseModel):
    uuid: Optional[str] = None
    file_type: Optional[str] = None


class FileRecordResponse(BaseModel):
    user_id: int
    filepath: str
    uuid: str
    file_type: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SubdirectoryCreate(BaseModel):
    user_id: int
    directory: str
    subdirectory: str


class SubdirectoryResponse(BaseModel):
    user_id: int
    directory: str
    subdirectory: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DirectoryListingResponse(BaseModel):
    files: List[FileRecordResponse]
    subdirectories: List[str]


class FilePathUpdate(BaseModel):
    new_filepath: str


# ============== Startup Event ==============

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


# ============== File Endpoints ==============

@app.post("/files", response_model=FileRecordResponse)
def create_file_record(
    file_record: FileRecordCreate,
    db: Session = Depends(get_db)
):
    """Create a new file record."""
    # Check if file already exists
    existing = db.query(File).filter(
        File.user_id == file_record.user_id,
        File.filepath == file_record.filepath
    ).first()
    
    if existing:
        raise HTTPException(status_code=409, detail="File already exists at this path")
    
    # Create file record
    file = File(
        user_id=file_record.user_id,
        filepath=file_record.filepath,
        uuid=file_record.uuid,
        file_type=file_record.file_type,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(file)
    
    # Create parent directory entries if needed
    _ensure_directory_structure(db, file_record.user_id, file_record.filepath)
    
    db.commit()
    db.refresh(file)
    return file


@app.get("/files/{user_id}", response_model=FileRecordResponse)
def get_file_record(
    user_id: int,
    filepath: str = Query(..., description="Full file path")
):
    """Get a file record by user_id and filepath."""
    with next(get_db()) as db:
        file = db.query(File).filter(
            File.user_id == user_id,
            File.filepath == filepath
        ).first()
        
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        return file


@app.get("/files/{user_id}/by-uuid/{uuid}", response_model=FileRecordResponse)
def get_file_by_uuid(
    user_id: int,
    uuid: str,
    db: Session = Depends(get_db)
):
    """Get a file record by UUID."""
    file = db.query(File).filter(
        File.user_id == user_id,
        File.uuid == uuid
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return file


@app.put("/files/{user_id}", response_model=FileRecordResponse)
def update_file_record(
    user_id: int,
    filepath: str = Query(..., description="Full file path"),
    update: FileRecordUpdate = None,
    db: Session = Depends(get_db)
):
    """Update a file record (e.g., new UUID after content update)."""
    file = db.query(File).filter(
        File.user_id == user_id,
        File.filepath == filepath
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if update.uuid is not None:
        file.uuid = update.uuid
    if update.file_type is not None:
        file.file_type = update.file_type
    
    file.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(file)
    return file


@app.put("/files/{user_id}/rename", response_model=FileRecordResponse)
def rename_file(
    user_id: int,
    filepath: str = Query(..., description="Current file path"),
    update: FilePathUpdate = None,
    db: Session = Depends(get_db)
):
    """Rename/move a file by changing its filepath."""
    file = db.query(File).filter(
        File.user_id == user_id,
        File.filepath == filepath
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if target path already exists
    existing = db.query(File).filter(
        File.user_id == user_id,
        File.filepath == update.new_filepath
    ).first()
    
    if existing:
        raise HTTPException(status_code=409, detail="File already exists at target path")
    
    # Update filepath
    file.filepath = update.new_filepath
    file.updated_at = datetime.utcnow()
    
    # Ensure new directory structure exists
    _ensure_directory_structure(db, user_id, update.new_filepath)
    
    db.commit()
    db.refresh(file)
    return file


@app.delete("/files/{user_id}")
def delete_file_record(
    user_id: int,
    filepath: str = Query(..., description="Full file path"),
    db: Session = Depends(get_db)
):
    """Delete a file record."""
    file = db.query(File).filter(
        File.user_id == user_id,
        File.filepath == filepath
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    db.delete(file)
    db.commit()
    return {"status": "deleted", "filepath": filepath}


@app.get("/files/{user_id}/list", response_model=DirectoryListingResponse)
def list_directory(
    user_id: int,
    directory: str = Query("/", description="Directory path to list"),
    db: Session = Depends(get_db)
):
    """List all files and subdirectories in a directory."""
    # Normalize directory path
    if not directory.endswith("/"):
        directory = directory + "/"
    if directory == "/":
        prefix = "/"
    else:
        prefix = directory
    
    # Get files in this directory (files that start with directory and have no additional /)
    files = db.query(File).filter(
        File.user_id == user_id
    ).all()
    
    # Filter files that are directly in this directory
    direct_files = []
    for f in files:
        if directory == "/":
            # Root directory: files like /file.txt (one slash at start, no other slashes)
            remaining = f.filepath[1:] if f.filepath.startswith("/") else f.filepath
            if "/" not in remaining:
                direct_files.append(f)
        else:
            # Non-root: files that start with directory and have no more slashes after
            if f.filepath.startswith(prefix):
                remaining = f.filepath[len(prefix):]
                if "/" not in remaining and remaining:
                    direct_files.append(f)
    
    # Get subdirectories
    target_dir = "/" if directory == "/" else directory.rstrip("/")
    subdirs = db.query(Subdirectory).filter(
        Subdirectory.user_id == user_id,
        Subdirectory.directory == target_dir
    ).all()
    
    return DirectoryListingResponse(
        files=direct_files,
        subdirectories=[s.subdirectory for s in subdirs]
    )


@app.get("/files/{user_id}/all", response_model=List[FileRecordResponse])
def list_all_files(
    user_id: int,
    prefix: Optional[str] = Query(None, description="Optional path prefix filter"),
    db: Session = Depends(get_db)
):
    """List all files for a user, optionally filtered by path prefix."""
    query = db.query(File).filter(File.user_id == user_id)
    
    if prefix:
        query = query.filter(File.filepath.startswith(prefix))
    
    return query.all()


# ============== Subdirectory Endpoints ==============

@app.post("/subdirectories", response_model=SubdirectoryResponse)
def create_subdirectory(
    subdir: SubdirectoryCreate,
    db: Session = Depends(get_db)
):
    """Create a new subdirectory record."""
    # Check if already exists
    existing = db.query(Subdirectory).filter(
        Subdirectory.user_id == subdir.user_id,
        Subdirectory.directory == subdir.directory,
        Subdirectory.subdirectory == subdir.subdirectory
    ).first()
    
    if existing:
        return existing  # Already exists, return it
    
    subdirectory = Subdirectory(
        user_id=subdir.user_id,
        directory=subdir.directory,
        subdirectory=subdir.subdirectory,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(subdirectory)
    db.commit()
    db.refresh(subdirectory)
    return subdirectory


@app.get("/subdirectories/{user_id}", response_model=List[str])
def list_subdirectories(
    user_id: int,
    directory: str = Query("/", description="Parent directory path"),
    db: Session = Depends(get_db)
):
    """List all subdirectories in a directory."""
    subdirs = db.query(Subdirectory).filter(
        Subdirectory.user_id == user_id,
        Subdirectory.directory == directory
    ).all()
    
    return [s.subdirectory for s in subdirs]


@app.delete("/subdirectories/{user_id}")
def delete_subdirectory(
    user_id: int,
    directory: str = Query(..., description="Parent directory path"),
    subdirectory: str = Query(..., description="Subdirectory name"),
    recursive: bool = Query(False, description="Delete recursively"),
    db: Session = Depends(get_db)
):
    """Delete a subdirectory record."""
    subdir = db.query(Subdirectory).filter(
        Subdirectory.user_id == user_id,
        Subdirectory.directory == directory,
        Subdirectory.subdirectory == subdirectory
    ).first()
    
    if not subdir:
        raise HTTPException(status_code=404, detail="Subdirectory not found")
    
    if recursive:
        # Build full path of subdirectory
        full_path = f"{directory.rstrip('/')}/{subdirectory}"
        
        # Delete all files under this subdirectory
        db.query(File).filter(
            File.user_id == user_id,
            File.filepath.startswith(full_path + "/")
        ).delete(synchronize_session=False)
        
        # Delete all subdirectories under this subdirectory
        db.query(Subdirectory).filter(
            Subdirectory.user_id == user_id,
            Subdirectory.directory.startswith(full_path)
        ).delete(synchronize_session=False)
    
    db.delete(subdir)
    db.commit()
    return {"status": "deleted", "directory": directory, "subdirectory": subdirectory}


@app.put("/subdirectories/{user_id}/rename")
def rename_subdirectory(
    user_id: int,
    directory: str = Query(..., description="Parent directory path"),
    old_name: str = Query(..., description="Current subdirectory name"),
    new_name: str = Query(..., description="New subdirectory name"),
    db: Session = Depends(get_db)
):
    """Rename a subdirectory and update all file paths under it."""
    subdir = db.query(Subdirectory).filter(
        Subdirectory.user_id == user_id,
        Subdirectory.directory == directory,
        Subdirectory.subdirectory == old_name
    ).first()
    
    if not subdir:
        raise HTTPException(status_code=404, detail="Subdirectory not found")
    
    old_path = f"{directory.rstrip('/')}/{old_name}"
    new_path = f"{directory.rstrip('/')}/{new_name}"
    
    # Update subdirectory name
    subdir.subdirectory = new_name
    subdir.updated_at = datetime.utcnow()
    
    # Update all file paths under this subdirectory
    files = db.query(File).filter(
        File.user_id == user_id,
        File.filepath.startswith(old_path + "/")
    ).all()
    
    for f in files:
        f.filepath = f.filepath.replace(old_path, new_path, 1)
        f.updated_at = datetime.utcnow()
    
    # Update all nested subdirectory records
    nested_subdirs = db.query(Subdirectory).filter(
        Subdirectory.user_id == user_id,
        Subdirectory.directory.startswith(old_path)
    ).all()
    
    for s in nested_subdirs:
        s.directory = s.directory.replace(old_path, new_path, 1)
        s.updated_at = datetime.utcnow()
    
    db.commit()
    return {"status": "renamed", "old_path": old_path, "new_path": new_path}


# ============== Helper Functions ==============

def _ensure_directory_structure(db: Session, user_id: int, filepath: str):
    """
    Ensure all parent directories exist for a given filepath.
    Creates subdirectory records as needed.
    """
    from pathlib import PurePosixPath
    
    path = PurePosixPath(filepath)
    parts = list(path.parts)[1:-1]  # Exclude root and filename
    
    current_dir = "/"
    for part in parts:
        # Check if subdirectory record exists
        existing = db.query(Subdirectory).filter(
            Subdirectory.user_id == user_id,
            Subdirectory.directory == current_dir,
            Subdirectory.subdirectory == part
        ).first()
        
        if not existing:
            subdir = Subdirectory(
                user_id=user_id,
                directory=current_dir,
                subdirectory=part,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(subdir)
        
        # Update current directory
        if current_dir == "/":
            current_dir = f"/{part}"
        else:
            current_dir = f"{current_dir}/{part}"


# ============== Health Check ==============

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "filesystem-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
