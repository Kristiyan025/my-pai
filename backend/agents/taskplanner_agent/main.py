import os
import sys
from typing import Optional, List, Dict, Any
import json
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx

app = FastAPI(
    title="Task Planner Agent",
    description="Decomposes complex requests into actionable tasks",
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
DEFAULT_MODEL = os.getenv("PLANNER_MODEL", "llama3.2")


class Task(BaseModel):
    task_id: str
    description: str
    agent: str
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    priority: int = 1


class ExecutionPlan(BaseModel):
    plan_id: str
    user_request: str
    intent: str
    tasks: List[Task]
    parallel_groups: List[List[str]]  # Groups of task_ids that can run in parallel


class PlanRequest(BaseModel):
    user_message: str
    conversation_context: Optional[List[Dict[str, str]]] = None
    available_agents: Optional[List[str]] = None


class IntentAnalysis(BaseModel):
    primary_intent: str
    sub_intents: List[str]
    entities: Dict[str, Any]
    requires_agents: List[str]
    confidence: float


AGENT_CAPABILITIES = {
    "workspace": {
        "description": "File system operations in the user's workspace - list directory contents, read files, manage files, save images. Use this when users ask about directories, files, or their workspace contents. IMPORTANT: Use read_file to get file content before summarizing or analyzing any file.",
        "actions": {
            "list_files": "List files and subdirectories in a directory. Parameters: path (directory path like '/direc/hu' or '/'). Returns file names, types, and paths.",
            "read_file": "Read the content of a file. Parameters: path (file path). Returns file content. USE THIS FIRST when user asks about file contents, summaries, or analysis.",
            "write_file": "Write text content to a file. Parameters: path (file path), content (text content).",
            "save_image": "Save a base64-encoded image to a file. Parameters: path (file path including filename like /direc/horse.jpg), image_base64 (the base64 image data from websearch.download_image result), content_type (e.g., image/jpeg).",
            "copy_file": "Copy a file. Parameters: source (source path), destination (dest path).",
            "move_file": "Move a file. Parameters: source (source path), destination (dest path).",
            "delete_file": "Delete a file. Parameters: path (file path).",
            "create_directory": "Create a new directory. Parameters: path (directory path)."
        },
        "triggers": ["directory", "folder", "files in", "what's in", "list files", "workspace", "show me files", "contents of", "attached file", "uploaded file", "summarize", "summary of", "read the file", "file content", "what does the file", "analyze the file", "save to", "put it in", "save in"]
    },
    "chatstore": {
        "description": "Chat history management - create, read, list chats and messages",
        "actions": {
            "list_chats": "List all chats. No parameters.",
            "create_chat": "Create a new chat. Parameters: chat_name.",
            "get_chat": "Get a specific chat. Parameters: chat_id.",
            "add_message": "Add message to chat. Parameters: chat_id, message_text, user_role.",
            "get_messages": "Get messages from chat. Parameters: chat_id."
        },
        "triggers": ["chat history", "previous conversations", "old messages"]
    },
    "sdsa": {
        "description": "Semantic search across documents and chat history. Use for finding relevant content by meaning.",
        "actions": {
            "search_documents": "Search documents by semantic similarity. Parameters: query (search text), k (number of results, default 5).",
            "index_document": "Index a document for search. Parameters: filepath, content, file_type.",
            "search_messages": "Search chat messages. Parameters: query."
        },
        "triggers": ["search", "find", "look for", "relevant", "similar to"]
    },
    "websearch": {
        "description": "Web search, URL content fetching, and downloading content from the internet. Use this when users want to find information online, download images, or fetch web content.",
        "actions": {
            "search_web": "Search the web for text/links. Use for general web searches. Parameters: query, max_results.",
            "fetch_url": "Fetch content from a known URL. Parameters: url.",
            "search_and_fetch": "Search and fetch top results. Parameters: query, max_results.",
            "search_images": "ONLY for listing/browsing images without downloading. Returns URLs only. Parameters: query, max_results.",
            "download_image": "USE THIS to download any image from the internet. Searches and downloads image as base64 in one step. Parameters: query. Returns: image_base64, content_type, title, source_url. ALWAYS use this instead of search_images when user wants to download/save/display an image."
        },
        "triggers": ["search the web", "google", "look up online", "internet", "download from internet", "find online", "get from web", "image from internet", "download image", "fetch from url", "from the web", "find an image", "get a picture"]
    },
    "spotify": {
        "description": "Spotify music control - play, pause, search, volume",
        "actions": {
            "play_music": "Play music. Parameters: query (optional), uri (optional).",
            "pause_music": "Pause playback. No parameters.",
            "next_track": "Skip to next track. No parameters.",
            "previous_track": "Go to previous track. No parameters.",
            "search_music": "Search for music. Parameters: query.",
            "set_volume": "Set volume. Parameters: volume (0-100)."
        },
        "triggers": ["play music", "spotify", "song", "pause", "next track"]
    },
    "voiceio": {
        "description": "Speech-to-text and text-to-speech conversion",
        "actions": {
            "transcribe_audio": "Convert speech to text. Parameters: audio (base64).",
            "generate_speech": "Convert text to speech. Parameters: text, voice."
        },
        "triggers": ["transcribe", "speech", "voice", "audio"]
    },
    "filetransform": {
        "description": "File format conversion and image operations. Works with file paths directly.",
        "actions": {
            "convert_format": "Convert file format. Parameters: source_path (input file path like /0.jpg), target_format (e.g., png), output_path (optional, defaults to same name with new extension).",
            "resize_image": "Resize an image. Parameters: path, width, height.",
            "extract_text": "Extract text from file (OCR). Parameters: path."
        },
        "triggers": ["convert", "resize", "extract text", "ocr", "to png", "to jpg", "to pdf"]
    },
    "generaltask": {
        "description": "Math calculations, code execution, data analysis, unit conversion",
        "actions": {
            "evaluate_math": "Evaluate math expression. Parameters: expression.",
            "execute_code": "Execute code. Parameters: code, language.",
            "analyze_data": "Analyze data. Parameters: data, analysis_type.",
            "convert_units": "Convert units. Parameters: value, from_unit, to_unit.",
            "generate_random": "Generate random number. Parameters: min, max."
        },
        "triggers": ["calculate", "math", "code", "analyze", "convert units"]
    },
    "conversational": {
        "description": "LLM-based chat responses with RAG support. Use as final step to generate response.",
        "actions": {
            "generate_response": "Generate a response using context. Parameters: message, use_rag.",
            "summarize": "Summarize text. Parameters: text, max_length.",
            "extract_info": "Extract structured info. Parameters: text, extraction_type.",
            "translate": "Translate text. Parameters: text, target_language."
        },
        "triggers": []
    }
}


async def call_llm(messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": DEFAULT_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 2048
                }
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="LLM call failed")
        
        return response.json().get("message", {}).get("content", "")


def parse_json_from_llm(text: str) -> Any:
    # Try to find JSON in code blocks
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    matches = re.findall(code_block_pattern, text)
    
    if matches:
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    json_patterns = [
        r'\{[\s\S]*\}',  # Object
        r'\[[\s\S]*\]'   # Array
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
    
    return None


def extract_attached_file_paths(message: str) -> List[str]:
    file_paths = []
    # Match lines like "- /path/to/file.ext" after "[Attached files uploaded to workspace:"
    pattern = r'\[Attached files uploaded to workspace:([^\]]*)\]'
    matches = re.findall(pattern, message, re.IGNORECASE | re.DOTALL)
    
    for match in matches:
        # Extract individual file paths (lines starting with -)
        path_pattern = r'-\s*(/[^\n\r]+)'
        paths = re.findall(path_pattern, match)
        file_paths.extend([p.strip() for p in paths])
    
    return file_paths


def detect_agents_from_triggers(message: str) -> List[str]:
    message_lower = message.lower()
    detected = []
    
    for agent, info in AGENT_CAPABILITIES.items():
        triggers = info.get("triggers", [])
        for trigger in triggers:
            if trigger in message_lower:
                detected.append(agent)
                break
    
    if "/" in message or "directory" in message_lower or "folder" in message_lower:
        if "workspace" not in detected:
            detected.append("workspace")
    
    if "attached files uploaded to workspace" in message_lower or "[attached file" in message_lower:
        if "workspace" not in detected:
            detected.append("workspace")
    
    file_content_keywords = ["summary", "summarize", "analyze", "explain", "what is in", "content of", "read"]
    if any(kw in message_lower for kw in file_content_keywords) and "/" in message:
        if "workspace" not in detected:
            detected.append("workspace")
    
    return detected


async def analyze_intent(message: str, context: Optional[List[Dict]] = None) -> IntentAnalysis:
    pre_detected = detect_agents_from_triggers(message)
    
    agents_desc = "\n".join([
        f"- {name}: {info['description']}"
        for name, info in AGENT_CAPABILITIES.items()
    ])
    
    hint = ""
    if pre_detected:
        hint = f"\n\nHINT: The message likely involves these agents based on keywords: {pre_detected}"
    
    system_prompt = f"""You are an intent analyzer for an AI assistant system.
Analyze the user's message and determine:
1. The primary intent (what they want to accomplish)
2. Sub-intents (any secondary goals)
3. Entities mentioned (files, directories, paths, names, numbers, etc.)
4. Which agents would be needed to fulfill this request
5. Your confidence level (0-1)

Available agents:
{agents_desc}

IMPORTANT RULES:
- If user asks about directories, folders, or "what's in /path", use "workspace" agent
- If user mentions a path like /direc/hu or /some/path, extract it as "path" entity
- CRITICAL: If user asks for summary/analysis/explanation of a FILE, you MUST use "workspace" agent to READ the file content FIRST
- When you see "[Attached files uploaded to workspace:" followed by file paths, those are files the user just uploaded and wants to work with
- Always include "conversational" as the last agent to generate the final response
{hint}

Example: "What is in the directory /direc/hu?"
Response: {{"primary_intent": "list directory contents", "entities": {{"path": "/direc/hu"}}, "requires_agents": ["workspace", "conversational"]}}

Example: "Search for documents about AI"
Response: {{"primary_intent": "semantic search", "entities": {{"query": "AI"}}, "requires_agents": ["sdsa", "conversational"]}}

Example: "Make a summary of the attached file [Attached files uploaded to workspace: /uploads/example.pdf]"
Response: {{"primary_intent": "summarize file content", "entities": {{"file_path": "/uploads/example.pdf"}}, "requires_agents": ["workspace", "conversational"]}}

Example: "Explain what's in this file /docs/notes.txt"
Response: {{"primary_intent": "explain file content", "entities": {{"file_path": "/docs/notes.txt"}}, "requires_agents": ["workspace", "conversational"]}}

Example: "Download an image of a horse from the internet and save it to /images/"
Response: {{"primary_intent": "download image from web", "entities": {{"query": "horse image", "save_path": "/images/"}}, "requires_agents": ["websearch", "workspace", "conversational"]}}

Example: "Search the web for information about climate change"
Response: {{"primary_intent": "web search", "entities": {{"query": "climate change"}}, "requires_agents": ["websearch", "conversational"]}}

Respond ONLY with valid JSON in this format:
{{
    "primary_intent": "string describing main goal",
    "sub_intents": ["array of secondary goals"],
    "entities": {{"key": "value pairs of extracted entities"}},
    "requires_agents": ["list of agent names needed"],
    "confidence": 0.85
}}"""

    messages = [{"role": "system", "content": system_prompt}]
    
    if context:
        for ctx in context[-3:]:
            messages.append({"role": ctx.get("role", "user"), "content": ctx.get("content", "")})
    
    messages.append({"role": "user", "content": message})
    
    response = await call_llm(messages, temperature=0.1)
    
    parsed = parse_json_from_llm(response)
    
    if not parsed:
        agents = pre_detected + ["conversational"] if pre_detected else ["conversational"]
        return IntentAnalysis(
            primary_intent="general query",
            sub_intents=[],
            entities={},
            requires_agents=["conversational"],
            confidence=0.5
        )
    
    return IntentAnalysis(
        primary_intent=parsed.get("primary_intent", "unknown"),
        sub_intents=parsed.get("sub_intents", []),
        entities=parsed.get("entities", {}),
        requires_agents=parsed.get("requires_agents", ["conversational"]),
        confidence=parsed.get("confidence", 0.5)
    )


async def create_execution_plan(
    message: str,
    intent: IntentAnalysis,
    available_agents: Optional[List[str]] = None
) -> ExecutionPlan:
    import uuid
    
    if available_agents:
        agents_to_use = [a for a in intent.requires_agents if a in available_agents]
    else:
        agents_to_use = intent.requires_agents
    
    agents_info = []
    for agent in agents_to_use:
        if agent in AGENT_CAPABILITIES:
            info = AGENT_CAPABILITIES[agent]
            actions = info.get('actions', {})
            if isinstance(actions, dict):
                action_lines = [f"    - {name}: {desc}" for name, desc in actions.items()]
                agents_info.append(f"- {agent}:\n" + "\n".join(action_lines))
            else:
                agents_info.append(f"- {agent}:\n  Actions: {', '.join(actions)}")
    
    agents_desc = "\n".join(agents_info)
    
    system_prompt = f"""You are a task planner for an AI assistant system.
Create an execution plan to fulfill the user's request.

Available agents and their actions:
{agents_desc}

Create a list of tasks that:
1. Are specific and actionable
2. Use the correct agent and action
3. Include necessary parameters
4. Specify dependencies between tasks (task_id references)
5. Can be executed in parallel when possible
6. CRITICAL: If user wants to summarize/analyze/explain a FILE, you MUST read the file content FIRST using workspace.read_file
7. CRITICAL: To download/save/display an IMAGE from internet, ALWAYS use websearch.download_image (NOT search_images). download_image returns image_base64 and content_type directly.

EXAMPLES:

Example 1 - "What is in directory /docs?"
Intent: list directory contents
Entities: {{"path": "/docs"}}
Result:
{{
    "tasks": [
        {{"task_id": "t1", "description": "List files in /docs directory", "agent": "workspace", "action": "list_files", "parameters": {{"path": "/docs"}}, "depends_on": []}},
        {{"task_id": "t2", "description": "Format and present directory listing", "agent": "conversational", "action": "generate_response", "parameters": {{"message": "Describe the contents of /docs"}}, "depends_on": ["t1"]}}
    ]
}}

Example 2 - "Search for documents about machine learning"
Intent: semantic search
Entities: {{"query": "machine learning"}}
Result:
{{
    "tasks": [
        {{"task_id": "t1", "description": "Search for ML documents", "agent": "sdsa", "action": "search_documents", "parameters": {{"query": "machine learning"}}, "depends_on": []}},
        {{"task_id": "t2", "description": "Present search results", "agent": "conversational", "action": "generate_response", "parameters": {{}}, "depends_on": ["t1"]}}
    ]
}}

Example 3 - "Make a summary of the attached file [Attached files uploaded to workspace: /uploads/document.ppt]"
Intent: summarize file content
Entities: {{"file_path": "/uploads/document.ppt"}}
Result:
{{
    "tasks": [
        {{"task_id": "t1", "description": "Read the file content", "agent": "workspace", "action": "read_file", "parameters": {{"path": "/uploads/document.ppt"}}, "depends_on": []}},
        {{"task_id": "t2", "description": "Generate summary of file content", "agent": "conversational", "action": "generate_response", "parameters": {{"message": "Summarize the content of this file"}}, "depends_on": ["t1"]}}
    ]
}}
NOTE: The "path" parameter in read_file MUST use the EXACT file path from the user's entities, not a placeholder!

Example 4 - "Explain what's in /docs/notes.txt"
Intent: explain file content
Entities: {{"file_path": "/docs/notes.txt"}}
Result:
{{
    "tasks": [
        {{"task_id": "t1", "description": "Read the file content", "agent": "workspace", "action": "read_file", "parameters": {{"path": "/docs/notes.txt"}}, "depends_on": []}},
        {{"task_id": "t2", "description": "Explain the file content to user", "agent": "conversational", "action": "generate_response", "parameters": {{}}, "depends_on": ["t1"]}}
    ]
}}

Example 5 - "Download an image of a horse from the internet and put it in /direc/"
Intent: download image from web and save
Entities: {{"query": "horse", "save_path": "/direc/"}}
Result:
{{
    "tasks": [
        {{"task_id": "t1", "description": "Download a horse image from the web", "agent": "websearch", "action": "download_image", "parameters": {{"query": "horse"}}, "depends_on": []}},
        {{"task_id": "t2", "description": "Save the downloaded image to /direc/", "agent": "workspace", "action": "save_image", "parameters": {{"path": "/direc/horse.jpg", "image_base64": "${{t1.result.image_base64}}", "content_type": "${{t1.result.content_type}}"}}, "depends_on": ["t1"]}},
        {{"task_id": "t3", "description": "Confirm image was saved", "agent": "conversational", "action": "generate_response", "parameters": {{}}, "depends_on": ["t1", "t2"]}}
    ]
}}

Example 6 - "Search the web for information about machine learning"
Intent: web search
Entities: {{"query": "machine learning"}}
Result:
{{
    "tasks": [
        {{"task_id": "t1", "description": "Search the web for machine learning information", "agent": "websearch", "action": "search_web", "parameters": {{"query": "machine learning", "max_results": 5}}, "depends_on": []}},
        {{"task_id": "t2", "description": "Present search results to user", "agent": "conversational", "action": "generate_response", "parameters": {{}}, "depends_on": ["t1"]}}
    ]
}}

Respond ONLY with valid JSON in this format:
{{
    "tasks": [
        {{
            "task_id": "t1",
            "description": "what this task does",
            "agent": "agent_name",
            "action": "action_name",
            "parameters": {{"key": "value"}},
            "depends_on": []
        }},
        {{
            "task_id": "t2",
            "description": "next task",
            "agent": "another_agent",
            "action": "another_action",
            "parameters": {{}},
            "depends_on": ["t1"]
        }}
    ]
}}

User's intent: {intent.primary_intent}
Entities: {json.dumps(intent.entities)}

CRITICAL: When creating tasks, you MUST use the EXACT values from Entities above.
- If Entities contains {{"file_path": "/some/actual/file.ppt"}}, use "/some/actual/file.ppt" as the path parameter, NOT example paths!
- Do NOT copy paths from examples - use the REAL paths from Entities."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]
    
    response = await call_llm(messages, temperature=0.2)
    
    parsed = parse_json_from_llm(response)
    
    plan_id = str(uuid.uuid4())[:8]
    
    attached_files = extract_attached_file_paths(message)
    
    if not parsed or "tasks" not in parsed:
        return ExecutionPlan(
            plan_id=plan_id,
            user_request=message,
            intent=intent.primary_intent,
            tasks=[
                Task(
                    task_id="t1",
                    description="Generate conversational response",
                    agent="conversational",
                    action="generate_response",
                    parameters={"message": message}
                )
            ],
            parallel_groups=[["t1"]]
        )
    
    tasks = []
    attached_file_index = 0
    for t in parsed["tasks"]:
        params = t.get("parameters", {})
        
        if t.get("action") == "read_file" and "path" in params:
            path = params["path"]
            if "?" in path and attached_files and attached_file_index < len(attached_files):
                params["path"] = attached_files[attached_file_index]
                attached_file_index += 1
            elif path and attached_files:
                path_filename = path.split("/")[-1].split(".")[0] if "/" in path else path
                for actual_path in attached_files:
                    actual_filename = actual_path.split("/")[-1].split(".")[0] if "/" in actual_path else actual_path
                    if path.split(".")[-1] == actual_path.split(".")[-1]:
                        if "?" in path or len(path_filename) != len(actual_filename):
                            params["path"] = actual_path
                            break
        
        tasks.append(Task(
            task_id=t.get("task_id", f"t{len(tasks)+1}"),
            description=t.get("description", ""),
            agent=t.get("agent", "conversational"),
            action=t.get("action", "generate_response"),
            parameters=params,
            depends_on=t.get("depends_on", []),
            priority=t.get("priority", 1)
        ))
    
    # Calculate parallel groups
    parallel_groups = compute_parallel_groups(tasks)
    
    return ExecutionPlan(
        plan_id=plan_id,
        user_request=message,
        intent=intent.primary_intent,
        tasks=tasks,
        parallel_groups=parallel_groups
    )


def compute_parallel_groups(tasks: List[Task]) -> List[List[str]]:
    groups = []
    completed = set()
    remaining = {t.task_id: t for t in tasks}
    
    while remaining:
        current_group = []
        for task_id, task in list(remaining.items()):
            if all(dep in completed for dep in task.depends_on):
                current_group.append(task_id)
        
        if not current_group:
            current_group = list(remaining.keys())[:1]
        
        groups.append(current_group)
        
        for task_id in current_group:
            completed.add(task_id)
            del remaining[task_id]
    
    return groups


@app.post("/plan", response_model=ExecutionPlan)
async def create_plan(request: PlanRequest):
    # Analyze intent
    intent = await analyze_intent(
        request.user_message,
        request.conversation_context
    )
    
    # Create execution plan
    plan = await create_execution_plan(
        request.user_message,
        intent,
        request.available_agents
    )
    
    return plan


@app.post("/analyze-intent", response_model=IntentAnalysis)
async def analyze(request: PlanRequest):
    return await analyze_intent(
        request.user_message,
        request.conversation_context
    )


@app.get("/agents")
async def list_agents():
    return {
        "agents": [
            {
                "name": name,
                "description": info["description"],
                "actions": info["actions"]
            }
            for name, info in AGENT_CAPABILITIES.items()
        ]
    }


@app.post("/validate-plan")
async def validate_plan(plan: ExecutionPlan):
    errors = []
    warnings = []
    
    task_ids = {t.task_id for t in plan.tasks}
    
    for task in plan.tasks:
        if task.agent not in AGENT_CAPABILITIES:
            errors.append(f"Task {task.task_id}: Unknown agent '{task.agent}'")
        else:
            if task.action not in AGENT_CAPABILITIES[task.agent]["actions"]:
                errors.append(f"Task {task.task_id}: Unknown action '{task.action}' for agent '{task.agent}'")
        
        for dep in task.depends_on:
            if dep not in task_ids:
                errors.append(f"Task {task.task_id}: Unknown dependency '{dep}'")
    
    def has_cycle(task_id: str, visited: set, rec_stack: set) -> bool:
        visited.add(task_id)
        rec_stack.add(task_id)
        
        task = next((t for t in plan.tasks if t.task_id == task_id), None)
        if task:
            for dep in task.depends_on:
                if dep not in visited:
                    if has_cycle(dep, visited, rec_stack):
                        return True
                elif dep in rec_stack:
                    return True
        
        rec_stack.remove(task_id)
        return False
    
    for task in plan.tasks:
        if has_cycle(task.task_id, set(), set()):
            errors.append(f"Circular dependency detected involving task {task.task_id}")
            break
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


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
        "service": "taskplanner-agent",
        "ollama_connected": ollama_healthy
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8019)
