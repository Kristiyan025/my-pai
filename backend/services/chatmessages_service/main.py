"""
ChatMessages Service - FastAPI application.

Provides REST API for managing chats and messages in MySQL.
This is a private service used only by the ChatStore Agent.
"""

import os
import sys
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

# Add parent to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database import get_db, init_db
from models import Chat, ChatMessage, User

app = FastAPI(
    title="ChatMessages Service",
    description="Manages chats and messages in MySQL for the ChatStore Agent",
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

class ChatCreate(BaseModel):
    user_id: int
    chat_name: str


class ChatResponse(BaseModel):
    user_id: int
    chat_id: int
    chat_name: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    chat_id: int
    message_text: str
    user_role: str  # 'user' or 'system'


class MessageResponse(BaseModel):
    chat_id: int
    message_id: int
    created_at: datetime
    message_text: str
    user_role: str
    
    class Config:
        from_attributes = True


class ChatUpdate(BaseModel):
    chat_name: str


# ============== Startup Event ==============

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


# ============== Chat Endpoints ==============

@app.post("/chats", response_model=ChatResponse)
def create_chat(
    chat_data: ChatCreate,
    db: Session = Depends(get_db)
):
    """Create a new chat for a user."""
    # Get next chat_id for this user
    max_chat_id = db.query(func.max(Chat.chat_id)).filter(
        Chat.user_id == chat_data.user_id
    ).scalar()
    
    next_chat_id = (max_chat_id or 0) + 1
    
    chat = Chat(
        user_id=chat_data.user_id,
        chat_id=next_chat_id,
        chat_name=chat_data.chat_name,
        created_at=datetime.utcnow()
    )
    
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@app.get("/chats/{user_id}", response_model=List[ChatResponse])
def get_user_chats(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get all chats for a user."""
    chats = db.query(Chat).filter(
        Chat.user_id == user_id
    ).order_by(desc(Chat.created_at)).all()
    
    return chats


@app.get("/chats/{user_id}/{chat_id}", response_model=ChatResponse)
def get_chat(
    user_id: int,
    chat_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific chat."""
    chat = db.query(Chat).filter(
        Chat.user_id == user_id,
        Chat.chat_id == chat_id
    ).first()
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    return chat


@app.put("/chats/{user_id}/{chat_id}", response_model=ChatResponse)
def update_chat(
    user_id: int,
    chat_id: int,
    update_data: ChatUpdate,
    db: Session = Depends(get_db)
):
    """Update a chat's name."""
    chat = db.query(Chat).filter(
        Chat.user_id == user_id,
        Chat.chat_id == chat_id
    ).first()
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    chat.chat_name = update_data.chat_name
    db.commit()
    db.refresh(chat)
    return chat


@app.delete("/chats/{user_id}/{chat_id}")
def delete_chat(
    user_id: int,
    chat_id: int,
    db: Session = Depends(get_db)
):
    """Delete a chat and all its messages."""
    chat = db.query(Chat).filter(
        Chat.user_id == user_id,
        Chat.chat_id == chat_id
    ).first()
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Delete all messages first
    db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).delete()
    
    # Delete chat
    db.delete(chat)
    db.commit()
    
    return {"status": "deleted", "chat_id": chat_id}


# ============== Message Endpoints ==============

@app.post("/messages", response_model=MessageResponse)
def create_message(
    message_data: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Add a new message to a chat.
    Messages are immutable once created.
    """
    # Verify chat exists
    chat = db.query(Chat).filter(Chat.chat_id == message_data.chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Get next message_id for this chat
    max_msg_id = db.query(func.max(ChatMessage.message_id)).filter(
        ChatMessage.chat_id == message_data.chat_id
    ).scalar()
    
    next_msg_id = (max_msg_id or 0) + 1
    
    # Validate user_role
    if message_data.user_role not in ['user', 'assistant', 'system']:
        raise HTTPException(status_code=400, detail="user_role must be 'user', 'assistant', or 'system'")
    
    created_at = datetime.utcnow()
    
    message = ChatMessage(
        chat_id=message_data.chat_id,
        message_id=next_msg_id,
        created_at=created_at,
        message_text=message_data.message_text,
        user_role=message_data.user_role
    )
    
    db.add(message)
    db.commit()
    
    # Return a Pydantic model to avoid SQLAlchemy session issues with composite PK
    return MessageResponse(
        chat_id=message_data.chat_id,
        message_id=next_msg_id,
        created_at=created_at,
        message_text=message_data.message_text,
        user_role=message_data.user_role
    )


@app.get("/messages/{chat_id}", response_model=List[MessageResponse])
def get_messages(
    chat_id: int,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of messages to return"),
    before_id: Optional[int] = Query(None, description="Get messages before this message_id"),
    db: Session = Depends(get_db)
):
    """
    Get the last N messages in a chat.
    """
    query = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id)
    
    if before_id is not None:
        query = query.filter(ChatMessage.message_id < before_id)
    
    # Get most recent messages
    messages = query.order_by(desc(ChatMessage.created_at)).limit(limit).all()
    
    # Return in chronological order
    return list(reversed(messages))


@app.get("/messages/{chat_id}/{message_id}", response_model=MessageResponse)
def get_message(
    chat_id: int,
    message_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific message by ID."""
    message = db.query(ChatMessage).filter(
        ChatMessage.chat_id == chat_id,
        ChatMessage.message_id == message_id
    ).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return message


@app.get("/messages/{chat_id}/context/{message_id}", response_model=List[MessageResponse])
def get_message_context(
    chat_id: int,
    message_id: int,
    context_count: int = Query(3, ge=1, le=10, description="Number of previous messages to include"),
    db: Session = Depends(get_db)
):
    """
    Get a message and its context (previous N messages).
    Useful for SDSA embedding context.
    """
    # Get the target message and previous messages
    messages = db.query(ChatMessage).filter(
        ChatMessage.chat_id == chat_id,
        ChatMessage.message_id <= message_id
    ).order_by(desc(ChatMessage.message_id)).limit(context_count + 1).all()
    
    if not messages:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Return in chronological order
    return list(reversed(messages))


@app.get("/messages/{chat_id}/count")
def get_message_count(
    chat_id: int,
    db: Session = Depends(get_db)
):
    """Get the total number of messages in a chat."""
    count = db.query(func.count(ChatMessage.message_id)).filter(
        ChatMessage.chat_id == chat_id
    ).scalar()
    
    return {"chat_id": chat_id, "count": count}


# ============== Health Check ==============

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "chatmessages-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
