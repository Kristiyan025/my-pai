"""
Centralized configuration for all My PAI services.
Uses environment variables with sensible defaults for local development.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class MySQLConfig:
    """MySQL database connection configuration."""
    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def connection_url(self) -> str:
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class MinIOConfig:
    """MinIO object storage configuration."""
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False


@dataclass
class ChromaConfig:
    """ChromaDB vector database configuration."""
    host: str
    port: int
    collection_name: str = "documents"

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass
class OllamaConfig:
    """Ollama LLM service configuration."""
    host: str
    port: int
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class Settings:
    """Application settings loaded from environment variables."""
    
    # Single user ID (hardcoded as per requirements)
    USER_ID: int = 1
    
    # Service URLs
    FILESYSTEM_SERVICE_URL: str = os.getenv("FILESYSTEM_SERVICE_URL", "http://filesystem-service:8001")
    DOCUMENTS_SERVICE_URL: str = os.getenv("DOCUMENTS_SERVICE_URL", "http://documents-service:8002")
    CHATMESSAGES_SERVICE_URL: str = os.getenv("CHATMESSAGES_SERVICE_URL", "http://chatmessages-service:8003")
    APIKEYS_SERVICE_URL: str = os.getenv("APIKEYS_SERVICE_URL", "http://apikeys-service:8004")
    VECTORDB_SERVICE_URL: str = os.getenv("VECTORDB_SERVICE_URL", "http://vectordb-service:8005")
    
    # Agent URLs
    WORKSPACE_AGENT_URL: str = os.getenv("WORKSPACE_AGENT_URL", "http://workspace-agent:8010")
    CHATSTORE_AGENT_URL: str = os.getenv("CHATSTORE_AGENT_URL", "http://chatstore-agent:8011")
    SDSA_AGENT_URL: str = os.getenv("SDSA_AGENT_URL", "http://sdsa-agent:8012")
    WEBSEARCH_AGENT_URL: str = os.getenv("WEBSEARCH_AGENT_URL", "http://websearch-agent:8013")
    SPOTIFY_AGENT_URL: str = os.getenv("SPOTIFY_AGENT_URL", "http://spotify-agent:8014")
    VOICEIO_AGENT_URL: str = os.getenv("VOICEIO_AGENT_URL", "http://voiceio-agent:8015")
    FILETRANSFORM_AGENT_URL: str = os.getenv("FILETRANSFORM_AGENT_URL", "http://filetransform-agent:8016")
    GENERALTASK_AGENT_URL: str = os.getenv("GENERALTASK_AGENT_URL", "http://generaltask-agent:8017")
    CONVERSATIONAL_AGENT_URL: str = os.getenv("CONVERSATIONAL_AGENT_URL", "http://conversational-agent:8018")
    TASKPLANNER_AGENT_URL: str = os.getenv("TASKPLANNER_AGENT_URL", "http://taskplanner-agent:8019")
    ORCHESTRATOR_AGENT_URL: str = os.getenv("ORCHESTRATOR_AGENT_URL", "http://orchestrator-agent:8020")
    
    # MySQL configurations for different services
    @staticmethod
    def get_filesystem_db() -> MySQLConfig:
        return MySQLConfig(
            host=os.getenv("FILESYSTEM_DB_HOST", "filesystem-mysql"),
            port=int(os.getenv("FILESYSTEM_DB_PORT", "3306")),
            user=os.getenv("FILESYSTEM_DB_USER", "root"),
            password=os.getenv("FILESYSTEM_DB_PASSWORD", "password"),
            database=os.getenv("FILESYSTEM_DB_NAME", "filesystem_db")
        )
    
    @staticmethod
    def get_chatmessages_db() -> MySQLConfig:
        return MySQLConfig(
            host=os.getenv("CHATMESSAGES_DB_HOST", "chatmessages-mysql"),
            port=int(os.getenv("CHATMESSAGES_DB_PORT", "3306")),
            user=os.getenv("CHATMESSAGES_DB_USER", "root"),
            password=os.getenv("CHATMESSAGES_DB_PASSWORD", "password"),
            database=os.getenv("CHATMESSAGES_DB_NAME", "chatmessages_db")
        )
    
    @staticmethod
    def get_apikeys_db() -> MySQLConfig:
        return MySQLConfig(
            host=os.getenv("APIKEYS_DB_HOST", "apikeys-mysql"),
            port=int(os.getenv("APIKEYS_DB_PORT", "3306")),
            user=os.getenv("APIKEYS_DB_USER", "root"),
            password=os.getenv("APIKEYS_DB_PASSWORD", "password"),
            database=os.getenv("APIKEYS_DB_NAME", "apikeys_db")
        )
    
    @staticmethod
    def get_minio() -> MinIOConfig:
        return MinIOConfig(
            endpoint=os.getenv("MINIO_ENDPOINT", "minio:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            bucket=os.getenv("MINIO_BUCKET", "documents"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
        )
    
    @staticmethod
    def get_chroma() -> ChromaConfig:
        return ChromaConfig(
            host=os.getenv("CHROMA_HOST", "chromadb"),
            port=int(os.getenv("CHROMA_PORT", "8000")),
            collection_name=os.getenv("CHROMA_COLLECTION", "documents")
        )
    
    @staticmethod
    def get_ollama() -> OllamaConfig:
        return OllamaConfig(
            host=os.getenv("OLLAMA_HOST", "ollama"),
            port=int(os.getenv("OLLAMA_PORT", "11434"))
        )


settings = Settings()
