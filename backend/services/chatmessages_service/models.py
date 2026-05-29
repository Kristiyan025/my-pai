"""
SQLAlchemy database models for ChatMessages Service.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, Index, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class UserRole(enum.Enum):
    """Role of the message sender."""
    USER = "user"
    SYSTEM = "system"


class User(Base):
    """
    User table - contains the single hardcoded user (user_id=1).
    """
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, autoincrement=False)
    
    # Relationships
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")


class Chat(Base):
    """
    Chats table - stores chat sessions for each user.
    
    Purpose: Track chat conversations.
    
    Columns:
        - chat_id: Primary key (auto-increment)
        - user_id: Owner user ID (FK to users)
        - chat_name: Display name for the chat
    
    Constraints:
        - PK: chat_id
        - Index on user_id for quick chat listing
    """
    __tablename__ = "chats"
    
    chat_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    chat_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_chats_user_id', 'user_id'),
    )
    
    # Relationships
    user = relationship("User", back_populates="chats")
    messages = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan")


class ChatMessage(Base):
    """
    Chat Messages table - stores messages within chats (immutable).
    
    Purpose: Store conversation messages.
    
    Columns:
        - chat_id: FK to chats
        - created_at: Timestamp of message (UTC), part of PK for ordering
        - message_id: Sequential ID within chat
        - message_text: Content of the message
            - May contain <file path="/path/to/file"/> references
        - user_role: 'user' or 'system'
    
    Constraints:
        - PK: (chat_id, created_at) - clusters messages by chat and time
        - Index on chat_id for message retrieval
        - user_role limited to 'user' or 'system'
    """
    __tablename__ = "chat_messages"
    
    chat_id = Column(Integer, ForeignKey("chats.chat_id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    message_id = Column(Integer, nullable=False)
    message_text = Column(Text, nullable=False)
    user_role = Column(String(10), nullable=False)  # 'user' or 'system'
    
    # Composite primary key
    __table_args__ = (
        PrimaryKeyConstraint('chat_id', 'created_at'),
        Index('idx_messages_chat_id', 'chat_id'),
        Index('idx_messages_chat_message_id', 'chat_id', 'message_id'),
    )
    
    # Relationship
    chat = relationship("Chat", back_populates="messages")
