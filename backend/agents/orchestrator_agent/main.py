import os
import sys
from typing import Optional, List, Dict, Any
import json
import asyncio
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx

app = FastAPI(
    title="Orchestrator Agent",
    description="Central coordinator for My PAI assistant",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


TASKPLANNER_URL = os.getenv("TASKPLANNER_URL", "http://taskplanner-agent:8019")
CONVERSATIONAL_URL = os.getenv("CONVERSATIONAL_URL", "http://conversational-agent:8018")
WORKSPACE_URL = os.getenv("WORKSPACE_URL", "http://workspace-agent:8010")
CHATSTORE_URL = os.getenv("CHATSTORE_URL", "http://chatstore-agent:8011")
SDSA_URL = os.getenv("SDSA_URL", "http://sdsa-agent:8012")
WEBSEARCH_URL = os.getenv("WEBSEARCH_URL", "http://websearch-agent:8013")
SPOTIFY_URL = os.getenv("SPOTIFY_URL", "http://spotify-agent:8014")
VOICEIO_URL = os.getenv("VOICEIO_URL", "http://voiceio-agent:8015")
FILETRANSFORM_URL = os.getenv("FILETRANSFORM_URL", "http://filetransform-agent:8016")
GENERALTASK_URL = os.getenv("GENERALTASK_URL", "http://generaltask-agent:8017")

USER_ID = 1

AGENT_URLS = {
    "workspace": WORKSPACE_URL,
    "chatstore": CHATSTORE_URL,
    "sdsa": SDSA_URL,
    "websearch": WEBSEARCH_URL,
    "spotify": SPOTIFY_URL,
    "voiceio": VOICEIO_URL,
    "filetransform": FILETRANSFORM_URL,
    "generaltask": GENERALTASK_URL,
    "conversational": CONVERSATIONAL_URL,
    "taskplanner": TASKPLANNER_URL,
}

AGENT_ACTIONS = {
    "workspace": {
        "list_files": ("GET", "/list", lambda p: {"directory": p.get("path", "/")}),
        "read_file": ("GET", "/file/text", lambda p: {"path": p.get("path")}),
        "write_file": ("POST", "/write", lambda p: {"path": p.get("path"), "content": p.get("content", "")}),
        "save_image": ("POST", "/save-image", lambda p: {"path": p.get("path"), "image_base64": p.get("image_base64"), "content_type": p.get("content_type", "image/jpeg")}),
        "copy_file": ("POST", "/copy", lambda p: {"src_paths": [p.get("source")], "dest_dir": p.get("destination")}),
        "move_file": ("POST", "/move", lambda p: {"src_paths": [p.get("source")], "dest_dir": p.get("destination")}),
        "delete_file": ("POST", "/files/delete", lambda p: {"paths": [p.get("path")]}),
        "create_directory": ("POST", "/directory", lambda p: {"path": p.get("path")}),
    },
    "chatstore": {
        "list_chats": ("GET", "/chats", lambda p: {}),
        "create_chat": ("POST", "/chats", lambda p: p),
        "get_chat": ("GET", "/chats/{chat_id}", lambda p: {}),
        "add_message": ("POST", "/chats/{chat_id}/messages", lambda p: p),
        "get_messages": ("GET", "/chats/{chat_id}/messages", lambda p: {}),
    },
    "sdsa": {
        "search_documents": ("GET", "/query/text", lambda p: {"query": p.get("query"), "k": p.get("k", 5)}),
        "index_document": ("POST", "/documents/index", lambda p: p),
        "search_messages": ("GET", "/query/text", lambda p: {"query": p.get("query"), "source_type": "message"}),
    },
    "websearch": {
        "search_web": ("GET", "/search", lambda p: {"query": p.get("query"), "max_results": p.get("max_results", 5)}),
        "fetch_url": ("POST", "/fetch", lambda p: p),
        "search_and_fetch": ("POST", "/search-and-fetch", lambda p: p),
        "search_images": ("GET", "/images/search", lambda p: {"query": p.get("query"), "max_results": p.get("max_results", 5)}),
        "download_image": ("POST", "/images/download", lambda p: {"query": p.get("query"), "save_path": p.get("save_path")}),
    },
    "spotify": {
        "play_music": ("POST", "/playback/play", lambda p: p),
        "pause_music": ("POST", "/playback/pause", lambda p: {}),
        "next_track": ("POST", "/playback/next", lambda p: {}),
        "previous_track": ("POST", "/playback/previous", lambda p: {}),
        "search_music": ("GET", "/search", lambda p: {"query": p.get("query")}),
        "set_volume": ("POST", "/playback/volume", lambda p: {"volume": p.get("volume")}),
    },
    "voiceio": {
        "transcribe_audio": ("POST", "/stt/base64", lambda p: p),
        "generate_speech": ("POST", "/tts", lambda p: p),
    },
    "filetransform": {
        "convert_format": ("POST", "/convert/path", lambda p: {"source_path": p.get("source_path"), "output_path": p.get("output_path"), "target_format": p.get("target_format")}),
        "resize_image": ("POST", "/image/resize", lambda p: p),
        "extract_text": ("POST", "/extract-text", lambda p: p),
    },
    "generaltask": {
        "evaluate_math": ("POST", "/math/evaluate", lambda p: {"expression": p.get("expression")}),
        "execute_code": ("POST", "/code/execute", lambda p: p),
        "analyze_data": ("POST", "/data/analyze", lambda p: p),
        "convert_units": ("POST", "/units/convert", lambda p: p),
        "generate_random": ("GET", "/random/number", lambda p: p),
    },
    "conversational": {
        "generate_response": ("POST", "/chat", lambda p: p),
        "summarize": ("POST", "/summarize", lambda p: p),
        "extract_info": ("POST", "/extract", lambda p: p),
        "translate": ("POST", "/translate", lambda p: p),
    },
}


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    chat_id: Optional[int] = None
    conversation_history: List[Message] = Field(default_factory=list)
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    chat_id: Optional[int] = None
    tasks_executed: List[Dict[str, Any]] = Field(default_factory=list)
    context_used: List[Dict[str, Any]] = Field(default_factory=list)
    images: List[Dict[str, Any]] = Field(default_factory=list)


class TaskResult(BaseModel):
    task_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


async def execute_task(task: Dict[str, Any], previous_results: Dict[str, Any]) -> TaskResult:
    task_id = task.get("task_id", "unknown")
    agent = task.get("agent")
    action = task.get("action")
    parameters = task.get("parameters", {})
    
    resolved_params = resolve_parameters(parameters, previous_results)
    
    if agent not in AGENT_URLS:
        return TaskResult(
            task_id=task_id,
            success=False,
            error=f"Unknown agent: {agent}"
        )
    
    if agent not in AGENT_ACTIONS or action not in AGENT_ACTIONS[agent]:
        return TaskResult(
            task_id=task_id,
            success=False,
            error=f"Unknown action: {action} for agent {agent}"
        )
    
    method, endpoint, param_mapper = AGENT_ACTIONS[agent][action]
    base_url = AGENT_URLS[agent]
    
    try:
        formatted_endpoint = endpoint.format(**resolved_params)
        url = f"{base_url}{formatted_endpoint}"
        
        mapped_params = param_mapper(resolved_params)
        
        async with httpx.AsyncClient(timeout=1200.0) as client:
            if method == "GET":
                response = await client.get(url, params=mapped_params)
            elif method == "POST":
                response = await client.post(url, json=mapped_params)
            elif method == "DELETE":
                response = await client.delete(url, params=mapped_params)
            elif method == "PUT":
                response = await client.put(url, json=mapped_params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if response.status_code in (200, 201):
                return TaskResult(
                    task_id=task_id,
                    success=True,
                    result=response.json() if response.text else None
                )
            else:
                return TaskResult(
                    task_id=task_id,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}"
                )
                
    except Exception as e:
        return TaskResult(
            task_id=task_id,
            success=False,
            error=str(e)
        )


def resolve_parameters(params: Dict[str, Any], previous_results: Dict[str, Any]) -> Dict[str, Any]:
    resolved = {}
    
    for key, value in params.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            ref_path = value[2:-1].split(".")
            try:
                result = previous_results
                for part in ref_path:
                    if isinstance(result, dict):
                        result = result.get(part)
                    elif hasattr(result, part):
                        result = getattr(result, part)
                    else:
                        result = None
                        break
                resolved[key] = result
            except Exception:
                resolved[key] = value
        elif isinstance(value, dict):
            resolved[key] = resolve_parameters(value, previous_results)
        else:
            resolved[key] = value
    
    return resolved


async def execute_plan(plan: Dict[str, Any]) -> Dict[str, TaskResult]:
    results = {}
    
    parallel_groups = plan.get("parallel_groups", [[t["task_id"] for t in plan.get("tasks", [])]])
    tasks_by_id = {t["task_id"]: t for t in plan.get("tasks", [])}
    
    for group in parallel_groups:
        group_tasks = [tasks_by_id[tid] for tid in group if tid in tasks_by_id]
        
        if len(group_tasks) == 1:
            task_result = await execute_task(group_tasks[0], results)
            results[task_result.task_id] = task_result
        else:
            for task in group_tasks:
                task_result = await execute_task(task, results)
                results[task_result.task_id] = task_result
    
    return results


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        chat_id = request.chat_id
        
        if not chat_id:
            try:
                async with httpx.AsyncClient(timeout=200.0) as client:
                    chat_name = request.message[:50] + ("..." if len(request.message) > 50 else "")
                    response = await client.post(
                        f"{CHATSTORE_URL}/chats",
                        json={"chat_name": chat_name, "user_id": USER_ID}
                    )
                    if response.status_code == 200:
                        chat_data = response.json()
                        chat_id = chat_data.get("chat_id")
                        print(f"Created new chat with ID: {chat_id}")
            except Exception as e:
                print(f"Failed to create chat: {e}")
        
        if chat_id:
            try:
                async with httpx.AsyncClient(timeout=200.0) as client:
                    await client.post(
                        f"{CHATSTORE_URL}/chats/{chat_id}/messages",
                        json={"user_role": "user", "message_text": request.message, "timestamp": datetime.now().isoformat()}
                    )
            except Exception as e:
                print(f"Failed to store message: {e}")
        
        context = [{"role": m.role, "content": m.content} for m in request.conversation_history]
        
        plan = None
        try:
            async with httpx.AsyncClient(timeout=1200.0) as client:
                response = await client.post(
                    f"{TASKPLANNER_URL}/plan",
                    json={
                        "user_message": request.message,
                        "conversation_context": context
                    }
                )
                if response.status_code == 200:
                    plan = response.json()
        except Exception as e:
            print(f"Planning failed: {e}")
        
        tasks_executed = []
        task_results = {}
        
        if plan and plan.get("tasks"):
            non_conversational_plan = {
                **plan,
                "tasks": [t for t in plan["tasks"] if t.get("agent") != "conversational"],
                "parallel_groups": [
                    [tid for tid in group if any(
                        t["task_id"] == tid and t.get("agent") != "conversational"
                        for t in plan["tasks"]
                    )]
                    for group in plan.get("parallel_groups", [])
                ]
            }
            non_conversational_plan["parallel_groups"] = [g for g in non_conversational_plan["parallel_groups"] if g]
            
            if non_conversational_plan["tasks"]:
                task_results = await execute_plan(non_conversational_plan)
                
                for task_id, result in task_results.items():
                    tasks_executed.append({
                        "task_id": task_id,
                        "agent": next((t["agent"] for t in plan["tasks"] if t["task_id"] == task_id), "unknown"),
                        "success": result.success,
                        "result_summary": str(result.result)[:200] if result.result else None,
                        "error": result.error
                    })
        
        images = []
        if plan and plan.get("tasks"):
            for task_id, result in task_results.items():
                if result.success and result.result and isinstance(result.result, dict):
                    if "image_base64" in result.result:
                        images.append({
                            "base64": result.result.get("image_base64"),
                            "content_type": result.result.get("content_type", "image/jpeg"),
                            "title": result.result.get("title", "Downloaded image"),
                            "source_url": result.result.get("source_url"),
                        })
                    if "path" in result.result and result.result.get("success"):
                        agent = next((t["agent"] for t in plan["tasks"] if t["task_id"] == task_id), "")
                        if agent == "workspace":
                            saved_path = result.result.get("path", "")
                            if saved_path and any(saved_path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                                images.append({
                                    "path": saved_path,
                                    "title": f"Saved to {saved_path}",
                                })
        
        system_context = ""
        if task_results:
            context_parts = []
            for task_id, result in task_results.items():
                if result.success and result.result:
                    res = result.result
                    task_agent = next((t["agent"] for t in plan["tasks"] if t["task_id"] == task_id), "")
                    task_action = next((t["action"] for t in plan["tasks"] if t["task_id"] == task_id), "")
                    if isinstance(res, dict):
                        if "results" in res and isinstance(res["results"], list):
                            search_results = []
                            for item in res["results"][:5]:
                                if isinstance(item, dict):
                                    title = item.get("title", "")
                                    snippet = item.get("snippet", item.get("description", ""))
                                    url = item.get("url", "")
                                    if title or snippet:
                                        search_results.append(f"- {title}: {snippet} ({url})")
                            if search_results:
                                context_parts.append(f"Web search results:\n" + "\n".join(search_results))
                        if "success" in res and res["success"]:
                            summary_parts = []
                            for key in ["source_path", "output_path", "filepath", "path", "source_format", "target_format", "status"]:
                                if key in res:
                                    summary_parts.append(f"{key}: {res[key]}")
                            if summary_parts:
                                context_parts.append(f"Task {task_agent}.{task_action} completed successfully: " + ", ".join(summary_parts))
                            else:
                                context_parts.append(f"Task {task_agent}.{task_action} completed successfully")
                        elif "title" in res and "results" not in res:
                            context_parts.append(f"Found: {res.get('title', '')}")
                        if "source_url" in res:
                            context_parts.append(f"Source: {res.get('source_url', '')}")
                        if "content" in res:
                            context_parts.append(f"Content: {str(res.get('content', ''))[:500]}")
                        if "text_content" in res:
                            context_parts.append(f"File content: {str(res.get('text_content', ''))[:500]}")
                        if "text" in res:
                            context_parts.append(f"Text content: {str(res.get('text', ''))[:500]}")
                        if "directory" in res:
                            files = res.get("files", [])
                            subdirs = res.get("subdirectories", [])
                            listing = f"Directory {res['directory']}:"
                            if subdirs:
                                listing += f"\n  Subdirectories: {', '.join(subdirs)}"
                            if files:
                                file_names = [f.get("filepath", f.get("name", "")) for f in files[:20]]
                                listing += f"\n  Files: {', '.join(file_names)}"
                            context_parts.append(listing)
                    else:
                        context_parts.append(f"Task {task_agent}.{task_action} result: {str(res)[:300]}")
                elif not result.success and result.error:
                    context_parts.append(f"Task {task_id} failed: {result.error}")
            
            if context_parts:
                system_context = "\n\n".join(context_parts)
                if images:
                    system_context += "\nImages have been retrieved and will be displayed to the user."
        
        task_system_prompt = None
        if system_context:
            task_system_prompt = (
                "You are a personal AI assistant with access to tools and agents. "
                "The following actions have ALREADY been executed on the user's behalf. "
                "DO NOT suggest how to do these tasks - they are ALREADY DONE. "
                "Simply report the results to the user in a natural, helpful way.\n\n"
                "COMPLETED ACTIONS:\n" + system_context
            )
        
        messages = [
            {"role": m.role, "content": m.content}
            for m in request.conversation_history
        ]
        messages.append({"role": "user", "content": request.message})
        
        final_response = ""
        context_used = []
        
        try:
            chat_payload = {
                "messages": messages,
                "use_rag": not bool(task_system_prompt),
                "stream": request.stream
            }
            if task_system_prompt:
                chat_payload["system_prompt"] = task_system_prompt
            
            async with httpx.AsyncClient(timeout=2400.0) as client:
                response = await client.post(
                    f"{CONVERSATIONAL_URL}/chat",
                    json=chat_payload
                )
                if response.status_code == 200:
                    data = response.json()
                    final_response = data.get("content", "")
                    context_used = data.get("context_used") or []
        except Exception as e:
            final_response = f"I encountered an error generating a response: {str(e)}"
        
        if chat_id:
            try:
                async with httpx.AsyncClient(timeout=200.0) as client:
                    save_response = await client.post(
                        f"{CHATSTORE_URL}/chats/{chat_id}/messages",
                        json={"user_role": "assistant", "message_text": final_response}
                    )
                    if save_response.status_code != 200:
                        print(f"Failed to save assistant message: {save_response.status_code} - {save_response.text}")
            except Exception as e:
                print(f"Error saving assistant message: {e}")
        
        return ChatResponse(
            response=final_response,
            chat_id=chat_id,
            tasks_executed=tasks_executed,
            context_used=context_used,
            images=images
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@app.post("/simple-chat")
async def simple_chat(message: str, use_rag: bool = True):
    try:
        async with httpx.AsyncClient(timeout=2400.0) as client:
            response = await client.post(
                f"{CONVERSATIONAL_URL}/chat",
                json={
                    "messages": [{"role": "user", "content": message}],
                    "use_rag": use_rag
                }
            )
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_json()
            
            message = data.get("message", "")
            chat_id = data.get("chat_id")
            history = data.get("conversation_history", [])
            
            await websocket.send_json({"type": "ack", "status": "processing"})
            
            response = await chat(ChatRequest(
                message=message,
                chat_id=chat_id,
                conversation_history=[Message(**m) for m in history]
            ))
            
            await websocket.send_json({
                "type": "response",
                "data": response.model_dump()
            })
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


@app.get("/status")
async def get_status():
    status = {}
    
    async with httpx.AsyncClient(timeout=100.0) as client:
        for agent_name, url in AGENT_URLS.items():
            try:
                response = await client.get(f"{url}/health")
                status[agent_name] = {
                    "healthy": response.status_code == 200,
                    "status": response.json() if response.status_code == 200 else None
                }
            except Exception as e:
                status[agent_name] = {
                    "healthy": False,
                    "error": str(e)
                }
    
    return {"agents": status}


@app.get("/files")
async def list_files(path: str = "/"):
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.get(
                f"{WORKSPACE_URL}/list",
                params={"directory": path}
            )
            response.raise_for_status()
            data = response.json()
            
            items = []
            for f in data.get("files", []):
                items.append({
                    "name": f["filepath"].split("/")[-1],
                    "path": f["filepath"],
                    "type": "file",
                    "modified": f.get("updated_at")
                })
            for subdir in data.get("subdirectories", []):
                full_path = f"{path.rstrip('/')}/{subdir}" if path != "/" else f"/{subdir}"
                items.append({
                    "name": subdir,
                    "path": full_path,
                    "type": "directory"
                })
            
            return {"items": items}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/read")
async def read_file(path: str):
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.get(
                f"{WORKSPACE_URL}/file",
                params={"path": path}
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "application/octet-stream")
            if content_type.startswith("text/") or "json" in content_type:
                return {"content": response.text, "content_type": content_type}
            else:
                import base64
                return {"content": base64.b64encode(response.content).decode(), "content_type": content_type, "is_binary": True}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/pptx-slides")
async def get_pptx_slides(path: str):
    async with httpx.AsyncClient(timeout=1200.0) as client:
        try:
            response = await client.get(
                f"{WORKSPACE_URL}/file/pptx-slides",
                params={"path": path}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/files/write")
async def write_file(request: dict):
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.post(
                f"{WORKSPACE_URL}/write",
                json={"filepath": request.get("path"), "content": request.get("content")}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...), path: str = Form("/")):
    async with httpx.AsyncClient(timeout=2400.0) as client:
        try:
            content = await file.read()
            files = {"file": (file.filename, content, file.content_type or "application/octet-stream")}
            directory = path if path else "/"
            response = await client.post(
                f"{WORKSPACE_URL}/upload",
                files=files,
                data={"directory": directory}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            raise HTTPException(status_code=e.response.status_code, detail=detail)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Upload timed out - file may be too large or server is busy")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.delete("/files")
async def delete_file(path: str):
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.request(
                "DELETE",
                f"{WORKSPACE_URL}/files",
                json={"paths": [path]}
            )
            response.raise_for_status()
            return {"success": True}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/directories")
async def create_directory(request: dict):
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.post(
                f"{WORKSPACE_URL}/directory",
                json={"path": request.get("path")}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/files/copy")
async def copy_file(request: dict):
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.post(
                f"{WORKSPACE_URL}/copy",
                json={"src_paths": [request.get("source")], "dest_dir": request.get("destination")}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/files/move")
async def move_file(request: dict):
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.post(
                f"{WORKSPACE_URL}/move",
                json={"src_paths": [request.get("source")], "dest_dir": request.get("destination")}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/chats")
async def list_chats():
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.get(f"{CHATSTORE_URL}/chats")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/chats")
async def create_chat(request: dict):
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.post(
                f"{CHATSTORE_URL}/chats",
                json=request
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/chats/{chat_id}")
async def get_chat(chat_id: int):
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.get(f"{CHATSTORE_URL}/chats/{chat_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: int):
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.delete(f"{CHATSTORE_URL}/chats/{chat_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/chats/{chat_id}/messages")
async def get_chat_messages(chat_id: int):
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.get(f"{CHATSTORE_URL}/chats/{chat_id}/messages")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/chats/{chat_id}/messages")
async def add_chat_message(chat_id: int, request: dict):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{CHATSTORE_URL}/chats/{chat_id}/messages",
                json=request
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


class TTSRequest(BaseModel):
    text: str
    speed: float = 1.0


@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{VOICEIO_URL}/tts",
                json={"text": request.text, "speed": request.speed}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents")
async def list_agents():
    agents = []
    for name, url in AGENT_URLS.items():
        actions = list(AGENT_ACTIONS.get(name, {}).keys())
        agents.append({
            "name": name,
            "url": url,
            "actions": actions
        })
    return {"agents": agents}


@app.get("/health")
async def health_check():
    critical_healthy = True
    status = {}
    
    critical_agents = ["conversational", "taskplanner"]
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for agent in critical_agents:
            try:
                response = await client.get(f"{AGENT_URLS[agent]}/health")
                status[agent] = response.status_code == 200
                if response.status_code != 200:
                    critical_healthy = False
            except Exception:
                status[agent] = False
                critical_healthy = False
    
    return {
        "status": "healthy" if critical_healthy else "degraded",
        "service": "orchestrator-agent",
        "dependencies": status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8020)
