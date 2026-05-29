"""

import os
import sys
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

app = FastAPI(
    title="ChatStore Agent",
    description="Manages chat sessions and messages",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHATMESSAGES_SERVICE_URL = os.getenv("CHATMESSAGES_SERVICE_URL", "http://chatmessages-service:8003")
SDSA_AGENT_URL = os.getenv("SDSA_AGENT_URL", "http://sdsa-agent:8012")
USER_ID = 1



class ChatCreate(BaseModel):
    chat_name: str


class ChatResponse(BaseModel):
    user_id: int
    chat_id: int
    chat_name: str
    created_at: datetime


class ChatListResponse(BaseModel):
    chats: List[ChatResponse]


class MessageCreate(BaseModel):
    message_text: str
    user_role: str = "user"


class MessageResponse(BaseModel):
    chat_id: int
    message_id: int
    created_at: datetime
    message_text: str
    user_role: str


class MessagesListResponse(BaseModel):
    messages: List[MessageResponse]


class ChatUpdate(BaseModel):
    chat_name: str



async def notify_sdsa_message_indexed(chat_id: int, message_id: int):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                f"{SDSA_AGENT_URL}/messages/index",
                json={
                    "user_id": USER_ID,
                    "chat_id": chat_id,
                    "message_id": message_id
                }
            )
    except Exception as e:
        print(f"Warning: Failed to notify SDSA for message indexing: {e}")



@app.get("/chats", response_model=ChatListResponse)
async def list_chats():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{CHATMESSAGES_SERVICE_URL}/chats/{USER_ID}")
        response.raise_for_status()
        
        chats_data = response.json()
        return ChatListResponse(
            chats=[ChatResponse(
                user_id=c["user_id"],
                chat_id=c["chat_id"],
                chat_name=c["chat_name"],
                created_at=c["created_at"]
            ) for c in chats_data]
        )


@app.post("/chats", response_model=ChatResponse)
async def create_chat(request: ChatCreate):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{CHATMESSAGES_SERVICE_URL}/chats",
            json={
                "user_id": USER_ID,
                "chat_name": request.chat_name
            }
        )
        response.raise_for_status()
        
        chat_data = response.json()
        return ChatResponse(
            user_id=chat_data["user_id"],
            chat_id=chat_data["chat_id"],
            chat_name=chat_data["chat_name"],
            created_at=chat_data["created_at"]
        )


@app.get("/chats/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: int):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{CHATMESSAGES_SERVICE_URL}/chats/{USER_ID}/{chat_id}")
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Chat not found")
        response.raise_for_status()
        
        chat_data = response.json()
        return ChatResponse(
            user_id=chat_data["user_id"],
            chat_id=chat_data["chat_id"],
            chat_name=chat_data["chat_name"],
            created_at=chat_data["created_at"]
        )


@app.put("/chats/{chat_id}", response_model=ChatResponse)
async def update_chat(chat_id: int, request: ChatUpdate):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.put(
            f"{CHATMESSAGES_SERVICE_URL}/chats/{USER_ID}/{chat_id}",
            json={"chat_name": request.chat_name}
        )
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Chat not found")
        response.raise_for_status()
        
        chat_data = response.json()
        return ChatResponse(
            user_id=chat_data["user_id"],
            chat_id=chat_data["chat_id"],
            chat_name=chat_data["chat_name"],
            created_at=chat_data["created_at"]
        )


@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: int):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(f"{CHATMESSAGES_SERVICE_URL}/chats/{USER_ID}/{chat_id}")
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Chat not found")
        response.raise_for_status()
        
        return {"status": "deleted", "chat_id": chat_id}



@app.get("/chats/{chat_id}/messages", response_model=MessagesListResponse)
async def get_messages(
    chat_id: int,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of messages")
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{CHATMESSAGES_SERVICE_URL}/messages/{chat_id}",
            params={"limit": limit}
        )
        response.raise_for_status()
        
        messages_data = response.json()
        return MessagesListResponse(
            messages=[MessageResponse(
                chat_id=m["chat_id"],
                message_id=m["message_id"],
                created_at=m["created_at"],
                message_text=m["message_text"],
                user_role=m["user_role"]
            ) for m in messages_data]
        )


@app.post("/chats/{chat_id}/messages", response_model=MessageResponse)
async def add_message(chat_id: int, request: MessageCreate):
    if request.user_role not in ['user', 'assistant', 'system']:
        raise HTTPException(status_code=400, detail="user_role must be 'user', 'assistant', or 'system'")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{CHATMESSAGES_SERVICE_URL}/messages",
            json={
                "chat_id": chat_id,
                "message_text": request.message_text,
                "user_role": request.user_role
            }
        )
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Chat not found")
        response.raise_for_status()
        
        msg_data = response.json()
        
        await notify_sdsa_message_indexed(chat_id, msg_data["message_id"])
        
        return MessageResponse(
            chat_id=msg_data["chat_id"],
            message_id=msg_data["message_id"],
            created_at=msg_data["created_at"],
            message_text=msg_data["message_text"],
            user_role=msg_data["user_role"]
        )


@app.get("/chats/{chat_id}/messages/{message_id}", response_model=MessageResponse)
async def get_message(chat_id: int, message_id: int):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{CHATMESSAGES_SERVICE_URL}/messages/{chat_id}/{message_id}")
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Message not found")
        response.raise_for_status()
        
        msg_data = response.json()
        return MessageResponse(
            chat_id=msg_data["chat_id"],
            message_id=msg_data["message_id"],
            created_at=msg_data["created_at"],
            message_text=msg_data["message_text"],
            user_role=msg_data["user_role"]
        )


@app.get("/chats/{chat_id}/messages/{message_id}/context", response_model=MessagesListResponse)
async def get_message_context(
    chat_id: int,
    message_id: int,
    context_count: int = Query(3, ge=1, le=10, description="Number of previous messages")
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{CHATMESSAGES_SERVICE_URL}/messages/{chat_id}/context/{message_id}",
            params={"context_count": context_count}
        )
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Message not found")
        response.raise_for_status()
        
        messages_data = response.json()
        return MessagesListResponse(
            messages=[MessageResponse(
                chat_id=m["chat_id"],
                message_id=m["message_id"],
                created_at=m["created_at"],
                message_text=m["message_text"],
                user_role=m["user_role"]
            ) for m in messages_data]
        )


@app.get("/chats/{chat_id}/messages/count")
async def get_message_count(chat_id: int):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{CHATMESSAGES_SERVICE_URL}/messages/{chat_id}/count")
        response.raise_for_status()
        
        return response.json()



@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "chatstore-agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)
