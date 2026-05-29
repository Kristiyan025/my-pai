import os
import sys
import base64
from typing import Optional, List, Dict, Any, AsyncGenerator, Tuple
import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

app = FastAPI(
    title="Conversational Agent",
    description="LLM-based conversational agent with RAG support",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
SDSA_AGENT_URL = os.getenv("SDSA_AGENT_URL", "http://sdsa-agent:8012")
CHATSTORE_AGENT_URL = os.getenv("CHATSTORE_AGENT_URL", "http://chatstore-agent:8011")
WORKSPACE_AGENT_URL = os.getenv("WORKSPACE_AGENT_URL", "http://workspace-agent:8010")
DOCUMENTS_SERVICE_URL = os.getenv("DOCUMENTS_SERVICE_URL", "http://documents-service:8004")
FILESYSTEM_SERVICE_URL = os.getenv("FILESYSTEM_SERVICE_URL", "http://filesystem-service:8006")
# Use multimodal LLaVA model by default to support image inputs
DEFAULT_MODEL = os.getenv("DEFAULT_LLM_MODEL", "llava:7b")
USER_ID = 1

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    use_rag: bool = True
    rag_k: int = 5
    system_prompt: Optional[str] = None
    stream: bool = False


class ChatResponse(BaseModel):
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    context_used: Optional[List[Dict]] = None


class SimplePromptRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: Optional[str] = None

async def retrieve_context(query: str, k: int = 5) -> List[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{SDSA_AGENT_URL}/query/text",
                params={"query": query, "k": k, "user_id": USER_ID}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
    except Exception as e:
        print(f"RAG retrieval error: {e}")
    
    return []


async def fetch_image_base64(filepath: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get file record from FileSystemService to get the UUID
            fs_response = await client.get(
                f"{FILESYSTEM_SERVICE_URL}/files/{USER_ID}",
                params={"filepath": filepath}
            )
            
            if fs_response.status_code != 200:
                print(f"File not found in filesystem: {filepath}")
                return None
            
            file_record = fs_response.json()
            doc_uuid = file_record["uuid"]
            
            # Get content from DocumentsService
            doc_response = await client.get(f"{DOCUMENTS_SERVICE_URL}/documents/{doc_uuid}")
            
            if doc_response.status_code != 200:
                print(f"Document content not found for UUID: {doc_uuid}")
                return None
            
            # Return base64 encoded content
            return base64.b64encode(doc_response.content).decode('utf-8')
    except Exception as e:
        print(f"Error fetching image {filepath}: {e}")
        return None


async def format_context_for_prompt(context_items: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    if not context_items:
        return "", []
    
    context_parts = []
    images_base64 = []
    
    for i, item in enumerate(context_items, 1):
        doc = item.get("document", "")
        metadata = item.get("metadata", {})
        source = metadata.get("source_id", "unknown")
        source_type = metadata.get("source_type", "unknown")
        chunk_type = metadata.get("chunk_type", "text")
        
        if chunk_type == "image":
            filepath = metadata.get("filepath", metadata.get("file_path", ""))
            
            if not filepath and "::" in doc:
                filepath = doc.split("::", 1)[1]
            
            if filepath:
                image_b64 = await fetch_image_base64(filepath)
                if image_b64:
                    images_base64.append(image_b64)
                    caption = metadata.get("caption", "")
                    extracted_text = metadata.get("extracted_text", "")
                    image_desc = f"**Image {len(images_base64)}** (from: {filepath})"
                    if caption:
                        image_desc += f"\nCaption: {caption}"
                    if extracted_text:
                        image_desc += f"\nText in image: {extracted_text}"
                    context_parts.append(image_desc)
                else:
                    caption = metadata.get("caption", "")
                    extracted_text = metadata.get("extracted_text", "")
                    if caption or extracted_text:
                        context_parts.append(f"**Image description** (from: {filepath}):\n{caption}\n{extracted_text}")
        else:
            doc = doc.strip()
            
            if source_type == "file":
                filepath = metadata.get("file_path", source)
                context_parts.append(f"**Document {i}** (from: {filepath}):\n{doc}")
            elif source_type == "message":
                context_parts.append(f"**From previous conversation**:\n{doc}")
            else:
                context_parts.append(f"**Document {i}**:\n{doc}")
    
    return "\n\n---\n\n".join(context_parts), images_base64

async def generate_response(
    messages: List[Dict[str, Any]],
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    images: Optional[List[str]] = None
) -> Dict[str, Any]:
    if images:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                msg["images"] = images
                break
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ollama error: {response.text}"
            )
        
        return response.json()


async def generate_response_stream(
    messages: List[Dict[str, Any]],
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    images: Optional[List[str]] = None
) -> AsyncGenerator[str, None]:
    if images:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                msg["images"] = images
                break
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                    except json.JSONDecodeError:
                        continue

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    model = request.model or DEFAULT_MODEL
    
    messages = []
    base_system = request.system_prompt or (
        "You are a helpful personal AI assistant. Your job is to help the user by answering their questions. "
        "When provided with context from documents or previous conversations, use that information directly to answer. "
        "Do NOT describe or analyze the context itself - use it to answer the user's actual question. "
        "If the context contains the information the user is asking about, extract and present that information clearly. "
        "If you don't have enough information to answer, say so."
    )
    
    context_used = []
    context_images = []
    if request.use_rag and request.messages:
        last_user_msg = None
        for msg in reversed(request.messages):
            if msg.role == "user":
                last_user_msg = msg.content
                break
        
        if last_user_msg:
            context_used = await retrieve_context(last_user_msg, k=request.rag_k)
            
            if context_used:
                # Format context and extract images
                context_text, context_images = await format_context_for_prompt(context_used)
                
                if context_images:
                    base_system += (
                        "\n\n## Document Content Retrieved for This Question\n"
                        "Below is relevant content from the user's documents, including images. "
                        "Analyze any images provided and use all context to answer their question:\n\n"
                        f"{context_text}\n\n"
                        "---\nNow answer the user's question based on the above content and images."
                    )
                else:
                    base_system += (
                        "\n\n## Document Content Retrieved for This Question\n"
                        "Below is relevant content from the user's documents. Use this to answer their question:\n\n"
                        f"{context_text}\n\n"
                        "---\nNow answer the user's question based on the above content."
                    )
    
    messages.append({"role": "system", "content": base_system})
    
    for msg in request.messages:
        messages.append({"role": msg.role, "content": msg.content})
    
    if request.stream:
        async def stream_generator():
            async for chunk in generate_response_stream(
                messages, model, request.temperature, request.max_tokens,
                images=context_images if context_images else None
            ):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream"
        )
    else:
        result = await generate_response(
            messages, model, request.temperature, request.max_tokens,
            images=context_images if context_images else None
        )
        
        response_content = result.get("message", {}).get("content", "")
        
        return ChatResponse(
            content=response_content,
            model=model,
            usage={
                "prompt_tokens": result.get("prompt_eval_count", 0),
                "completion_tokens": result.get("eval_count", 0)
            },
            context_used=[
                {
                    "source": c.get("metadata", {}).get("source_id", "unknown"),
                    "type": c.get("metadata", {}).get("source_type", "unknown"),
                    "distance": c.get("distance", 0)
                }
                for c in context_used
            ] if context_used else None
        )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    request.stream = True
    return await chat(request)


@app.post("/generate")
async def generate(request: SimplePromptRequest):
    model = request.model or DEFAULT_MODEL
    
    messages = []
    
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    
    messages.append({"role": "user", "content": request.prompt})
    
    result = await generate_response(
        messages, model, request.temperature, request.max_tokens
    )
    
    return {
        "content": result.get("message", {}).get("content", ""),
        "model": model
    }


@app.post("/summarize")
async def summarize(text: str, max_length: int = 500, model: Optional[str] = None):
    model = model or DEFAULT_MODEL
    
    messages = [
        {
            "role": "system",
            "content": f"Summarize the following text concisely in no more than {max_length} characters. Focus on the key points."
        },
        {"role": "user", "content": text}
    ]
    
    result = await generate_response(messages, model, temperature=0.3, max_tokens=max_length)
    
    return {
        "summary": result.get("message", {}).get("content", ""),
        "original_length": len(text)
    }


@app.post("/extract")
async def extract_info(
    text: str,
    extraction_type: str = Query(..., description="Type: entities, keywords, topics, sentiment"),
    model: Optional[str] = None
):
    model = model or DEFAULT_MODEL
    
    prompts = {
        "entities": "Extract all named entities (people, organizations, locations, dates) from the text. Return as a JSON list.",
        "keywords": "Extract the most important keywords from the text. Return as a JSON list of strings.",
        "topics": "Identify the main topics discussed in the text. Return as a JSON list of topic strings.",
        "sentiment": "Analyze the sentiment of the text. Return JSON with 'sentiment' (positive/negative/neutral) and 'confidence' (0-1)."
    }
    
    if extraction_type not in prompts:
        raise HTTPException(status_code=400, detail=f"Unknown extraction type: {extraction_type}")
    
    messages = [
        {"role": "system", "content": prompts[extraction_type] + " Only return valid JSON, no other text."},
        {"role": "user", "content": text}
    ]
    
    result = await generate_response(messages, model, temperature=0.1, max_tokens=1000)
    
    content = result.get("message", {}).get("content", "[]")
    
    try:
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        extracted = json.loads(content.strip())
    except json.JSONDecodeError:
        extracted = content
    
    return {
        "type": extraction_type,
        "result": extracted
    }


@app.post("/translate")
async def translate(
    text: str,
    target_language: str,
    source_language: str = "auto",
    model: Optional[str] = None
):
    model = model or DEFAULT_MODEL
    
    if source_language == "auto":
        system_prompt = f"Translate the following text to {target_language}. Only return the translation, no other text."
    else:
        system_prompt = f"Translate the following text from {source_language} to {target_language}. Only return the translation, no other text."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]
    
    result = await generate_response(messages, model, temperature=0.3, max_tokens=len(text) * 2)
    
    return {
        "translation": result.get("message", {}).get("content", ""),
        "target_language": target_language,
        "source_language": source_language
    }

@app.get("/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "models": [m["name"] for m in data.get("models", [])],
                    "default": DEFAULT_MODEL
                }
    except Exception as e:
        return {"models": [], "default": DEFAULT_MODEL, "error": str(e)}


@app.post("/models/load")
async def load_model(model_name: str):
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": model_name, "prompt": "", "keep_alive": "5m"}
            )
            
            return {"status": "loaded", "model": model_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")

@app.get("/health")
async def health_check():
    ollama_healthy = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_healthy = response.status_code == 200
    except Exception:
        pass
    
    return {
        "status": "healthy" if ollama_healthy else "degraded",
        "service": "conversational-agent",
        "ollama_connected": ollama_healthy
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8018)
