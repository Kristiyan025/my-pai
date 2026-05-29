"""
Shared Pydantic models for API requests and responses across all services.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# ============== Enums ==============

class UserRole(str, Enum):
    """Role of the message sender."""
    USER = "user"
    SYSTEM = "system"


class FileType(str, Enum):
    """Supported file types."""
    # Images
    PNG = "png"
    JPEG = "jpeg"
    JPG = "jpg"
    WEBP = "webp"
    BMP = "bmp"
    GIF = "gif"
    # Documents
    PDF = "pdf"
    DOC = "doc"
    DOCX = "docx"
    PPTX = "pptx"
    # Notebooks
    IPYNB = "ipynb"
    # Markdown
    MD = "md"
    MDX = "mdx"
    # Code
    PY = "py"
    CPP = "cpp"
    H = "h"
    HPP = "hpp"
    JAVA = "java"
    R = "r"
    JS = "js"
    TS = "ts"
    HTML = "html"
    CSS = "css"
    JSON = "json"
    YAML = "yaml"
    YML = "yml"
    XML = "xml"
    # Text
    TXT = "txt"
    CSV = "csv"


class ChunkType(str, Enum):
    """Type of document chunk."""
    TEXT = "text"
    IMAGE = "image"


# ============== Chat Models ==============

class ChatCreate(BaseModel):
    """Request to create a new chat."""
    chat_name: str = Field(..., min_length=1, max_length=255)


class ChatResponse(BaseModel):
    """Response for a chat."""
    user_id: int
    chat_id: int
    chat_name: str


class ChatListResponse(BaseModel):
    """Response containing list of chats."""
    chats: List[ChatResponse]


class MessageCreate(BaseModel):
    """Request to add a message to a chat."""
    message_text: str
    user_role: UserRole = UserRole.USER


class MessageResponse(BaseModel):
    """Response for a message."""
    chat_id: int
    message_id: int
    created_at: datetime
    message_text: str
    user_role: UserRole


class MessagesListResponse(BaseModel):
    """Response containing list of messages."""
    messages: List[MessageResponse]


# ============== File System Models ==============

class FileRecord(BaseModel):
    """A file record in the filesystem."""
    user_id: int
    filepath: str
    uuid: str
    file_type: str
    created_at: datetime
    updated_at: datetime


class SubdirectoryRecord(BaseModel):
    """A subdirectory record."""
    user_id: int
    directory: str
    subdirectory: str
    created_at: datetime
    updated_at: datetime


class DirectoryListingResponse(BaseModel):
    """Response for directory listing."""
    files: List[FileRecord]
    subdirectories: List[str]


class FileCopyRequest(BaseModel):
    """Request to copy files."""
    src_paths: List[str]
    dest_dir: str


class FileMoveRequest(BaseModel):
    """Request to move files."""
    src_paths: List[str]
    dest_dir: str


class FileDeleteRequest(BaseModel):
    """Request to delete files."""
    paths: List[str]


class FileRenameRequest(BaseModel):
    """Request to rename a file or directory."""
    path: str
    new_name: str


class FileUploadResponse(BaseModel):
    """Response after uploading a file."""
    filepath: str
    uuid: str
    file_type: str


# ============== Document Service Models ==============

class DocumentUploadResponse(BaseModel):
    """Response after uploading a document to MinIO."""
    uuid: str
    size: int


class DocumentResponse(BaseModel):
    """Response containing document content."""
    uuid: str
    content: bytes
    content_type: str


# ============== Vector DB Models ==============

class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""
    user_id: int
    source_type: str  # "file" or "message"
    source_id: str  # filepath or message_id
    chunk_type: ChunkType
    chunk_index: int
    file_type: Optional[str] = None
    summary: Optional[str] = None
    extracted_text: Optional[str] = None
    caption: Optional[str] = None


class EmbeddingRecord(BaseModel):
    """An embedding record for the vector database."""
    chunk_id: str
    embedding: List[float]
    document: str  # Chunk content or "user::filepath" for images
    metadata: ChunkMetadata


class SimilarityQueryRequest(BaseModel):
    """Request to query similar documents."""
    embedding: List[float]
    k: int = 5


class SimilarityQueryResponse(BaseModel):
    """Response from similarity query."""
    results: List[Dict[str, Any]]


# ============== Web Search Models ==============

class WebSearchRequest(BaseModel):
    """Request for web search."""
    query: str
    max_results: int = Field(default=5, ge=1, le=20)
    language: Optional[str] = None
    region: Optional[str] = None
    allow_domains: Optional[List[str]] = None
    block_domains: Optional[List[str]] = None
    timeout_ms: Optional[int] = None


class WebSearchResult(BaseModel):
    """A single web search result."""
    url: str
    content: str


class WebSearchResponse(BaseModel):
    """Response from web search - list of [url, content] pairs."""
    results: List[List[str]]


# ============== Spotify Models ==============

class SpotifyKeyRequest(BaseModel):
    """Request to set Spotify API key."""
    user_id: int
    spotify_api_key: str


class SongFetchRequest(BaseModel):
    """Request to fetch a song."""
    user_id: int
    song_name: str


# ============== Voice IO Models ==============

class TranscriptionResponse(BaseModel):
    """Response from speech transcription."""
    transcript: str


class SynthesisRequest(BaseModel):
    """Request for text-to-speech synthesis."""
    text: str


class SpeakMessageRequest(BaseModel):
    """Request to speak a chat message."""
    user_id: int
    chat_id: int
    message_id: int


# ============== File Transform Models ==============

class ImageConvertRequest(BaseModel):
    """Request to convert image format."""
    input_format: str
    output_format: str


class PDFMergeRequest(BaseModel):
    """Request to merge PDFs."""
    pdf_uuids: List[str]


class PDFRotateRequest(BaseModel):
    """Request to rotate PDF pages."""
    pdf_uuid: str
    pages: List[int]
    direction: str  # "clockwise" or "counterclockwise"


class PDFSwapPagesRequest(BaseModel):
    """Request to swap PDF pages."""
    pdf_uuid: str
    page1: int
    page2: int


# ============== General Task Models ==============

class TaskExecuteRequest(BaseModel):
    """Request to execute a general task."""
    code: str
    args: Dict[str, Any] = {}


class TaskExecuteResponse(BaseModel):
    """Response from task execution."""
    result: Any
    error: Optional[str] = None


# ============== Conversational Agent Models ==============

class ConversationRequest(BaseModel):
    """Request for conversation generation."""
    prompt: str
    persona: Optional[Dict[str, Any]] = None


class ConversationResponse(BaseModel):
    """Response from conversation."""
    reply: str


# ============== Task Planner Models ==============

class PlanRequest(BaseModel):
    """Request to create execution plan."""
    user_id: int
    chat_id: int
    message_id: int


class PlanStep(BaseModel):
    """A single step in the execution plan."""
    step_id: int
    action: str
    agent: str
    params: Dict[str, Any]
    store_result: Optional[str] = None  # Variable name to store result


class ExecutionPlan(BaseModel):
    """The complete execution plan."""
    steps: List[PlanStep]
    validation_steps: List[PlanStep] = []


class PlanResponse(BaseModel):
    """Response containing the execution plan."""
    plan: ExecutionPlan


# ============== Orchestrator Models ==============

class OrchestrateRequest(BaseModel):
    """Request to orchestrate a message."""
    user_id: int
    chat_id: int
    message_text: str


class OrchestrateResponse(BaseModel):
    """Response from orchestration."""
    system_reply: str
    message_id: int


# ============== SDSA Models ==============

class DocumentIndexRequest(BaseModel):
    """Request to index a document."""
    user_id: int
    filepath: str
    content: bytes
    file_type: str


class MessageIndexRequest(BaseModel):
    """Request to index chat messages."""
    user_id: int
    chat_id: int
    message_id: int


class DocumentDeleteRequest(BaseModel):
    """Request to delete document embeddings."""
    user_id: int
    filepath: str
