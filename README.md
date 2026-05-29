# My PAI - Personal AI Assistant

A comprehensive personal AI assistant with a ChatGPT-like interface, file workspace management, and multi-agent microservices architecture.

## Features

- **Chat Interface**: Natural language conversation with AI, markdown rendering, code highlighting
- **Workspace Management**: File browser, upload/download, preview with syntax highlighting
- **Semantic Search**: Query documents and chat history using vector embeddings (SDSA)
- **Voice I/O**: Speech-to-text (Whisper) and text-to-speech (Coqui TTS)
- **Web Search**: DuckDuckGo integration for real-time information
- **Spotify Integration**: Control playback, search tracks, manage playlists
- **File Transformations**: Convert between formats (Markdown→PDF, HTML→PDF, etc.)
- **General Tasks**: Math calculations, code execution, unit conversions

## Architecture

### Backend Microservices

**Services (Data Layer):**
| Service | Port | Description |
|---------|------|-------------|
| Filesystem Service | 8001 | MySQL file/directory metadata |
| Documents Service | 8002 | MinIO binary content storage |
| ChatMessages Service | 8003 | MySQL chat/message storage |
| APIKeys Service | 8004 | Spotify credentials storage |
| VectorDB Service | 8005 | ChromaDB vector embeddings |

**Agents (Application Layer):**
| Agent | Port | Description |
|-------|------|-------------|
| Workspace Agent | 8010 | File CRUD operations |
| ChatStore Agent | 8011 | Chat management |
| SDSA Agent | 8012 | Semantic Document Store (embeddings, search) |
| WebSearch Agent | 8013 | DuckDuckGo search, URL fetching |
| Spotify Agent | 8014 | Spotify API integration |
| VoiceIO Agent | 8015 | Speech-to-text, text-to-speech |
| FileTransform Agent | 8016 | Format conversions |
| GeneralTask Agent | 8017 | Math, code, unit conversion |
| Conversational Agent | 8018 | LLM chat with RAG |
| TaskPlanner Agent | 8019 | Intent analysis, execution planning |
| Orchestrator Agent | 8020 | Central coordinator (entry point) |

### Frontend

- **Next.js 14** with React 18, TypeScript
- **TailwindCSS** for styling
- **Axios** for API communication

### Infrastructure

- **MySQL 8**: Relational data storage
- **MinIO**: S3-compatible object storage
- **ChromaDB**: Vector database for embeddings
- **Ollama**: Local LLM inference (llama3.2)

## Quick Start

### Prerequisites

- Docker & Docker Compose
- NVIDIA GPU with CUDA drivers (for GPU acceleration)
- 16GB+ RAM recommended

### Local Development with Docker Compose

```bash
# Clone the repository
git clone <repository-url>
cd my-pai

# Start all services
docker-compose up -d

# Pull the LLM model (run once)
docker exec pai-ollama ollama pull llama3.2

# Access the application
# Frontend: http://localhost:3000
# Orchestrator API: http://localhost:8020
```

### Manual Development Setup

**Backend:**

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Start services (each in separate terminal)
cd services/filesystem_service && uvicorn main:app --port 8001 --reload
cd services/documents_service && uvicorn main:app --port 8002 --reload
cd services/chatmessages_service && uvicorn main:app --port 8003 --reload
cd services/apikeys_service && uvicorn main:app --port 8004 --reload
cd services/vectordb_service && uvicorn main:app --port 8005 --reload

# Start agents
cd agents/workspace_agent && uvicorn main:app --port 8010 --reload
cd agents/chatstore_agent && uvicorn main:app --port 8011 --reload
cd agents/sdsa_agent && uvicorn main:app --port 8012 --reload
cd agents/websearch_agent && uvicorn main:app --port 8013 --reload
cd agents/spotify_agent && uvicorn main:app --port 8014 --reload
cd agents/voiceio_agent && uvicorn main:app --port 8015 --reload
cd agents/filetransform_agent && uvicorn main:app --port 8016 --reload
cd agents/generaltask_agent && uvicorn main:app --port 8017 --reload
cd agents/conversational_agent && uvicorn main:app --port 8018 --reload
cd agents/taskplanner_agent && uvicorn main:app --port 8019 --reload
cd agents/orchestrator_agent && uvicorn main:app --port 8020 --reload
```

**Frontend:**

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Access: http://localhost:3000
```

### Kubernetes Deployment

```bash
# Apply manifests in order
kubectl apply -f kubernetes/01-infrastructure.yaml
kubectl apply -f kubernetes/02-services.yaml
kubectl apply -f kubernetes/03-agents.yaml
kubectl apply -f kubernetes/04-frontend.yaml

# Add to /etc/hosts for local testing
# 127.0.0.1 pai.local
```

## Configuration

### Environment Variables

| Variable           | Default                | Description          |
| ------------------ | ---------------------- | -------------------- |
| `MYSQL_HOST`       | localhost              | MySQL server host    |
| `MYSQL_PORT`       | 3306                   | MySQL server port    |
| `MYSQL_USER`       | pai_user               | MySQL username       |
| `MYSQL_PASSWORD`   | pai_password           | MySQL password       |
| `MYSQL_DATABASE`   | pai_db                 | MySQL database name  |
| `MINIO_HOST`       | localhost              | MinIO server host    |
| `MINIO_PORT`       | 9000                   | MinIO server port    |
| `MINIO_ACCESS_KEY` | minioadmin             | MinIO access key     |
| `MINIO_SECRET_KEY` | minioadmin             | MinIO secret key     |
| `CHROMADB_HOST`    | localhost              | ChromaDB server host |
| `CHROMADB_PORT`    | 8000                   | ChromaDB server port |
| `OLLAMA_URL`       | http://localhost:11434 | Ollama API URL       |

### Backend Configuration

Edit `backend/config.yaml` to customize service URLs and settings.

## API Reference

### Orchestrator Agent (Main Entry Point)

```http
POST /chat
Content-Type: application/json

{
  "chat_id": "optional-uuid",
  "message": "Your message here"
}
```

**Response:**

```json
{
  "chat_id": "uuid",
  "response": "AI response",
  "actions_taken": ["action1", "action2"]
}
```

### Workspace Agent

```http
# List files
GET /files?path=/

# Upload file
POST /files/upload
Content-Type: multipart/form-data
file: <binary>
path: /destination/path

# Download file
GET /files/download?path=/file.txt

# Delete file
DELETE /files?path=/file.txt
```

### SDSA Agent (Semantic Search)

```http
# Query documents
POST /query
Content-Type: application/json

{
  "query": "search text",
  "top_k": 10,
  "include_images": true
}
```

## Project Structure

```
my-pai/
├── backend/
│   ├── agents/                 # Application layer agents
│   │   ├── chatstore_agent/
│   │   ├── conversational_agent/
│   │   ├── filetransform_agent/
│   │   ├── generaltask_agent/
│   │   ├── orchestrator_agent/
│   │   ├── sdsa_agent/
│   │   ├── spotify_agent/
│   │   ├── taskplanner_agent/
│   │   ├── voiceio_agent/
│   │   ├── websearch_agent/
│   │   └── workspace_agent/
│   ├── services/               # Data layer services
│   │   ├── apikeys_service/
│   │   ├── chatmessages_service/
│   │   ├── documents_service/
│   │   ├── filesystem_service/
│   │   └── vectordb_service/
│   ├── shared/                 # Shared utilities
│   │   ├── config.py
│   │   ├── models.py
│   │   └── utils.py
│   ├── config.yaml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chat/
│   │   │   ├── Layout/
│   │   │   └── Workspace/
│   │   ├── lib/
│   │   │   └── api.ts
│   │   ├── pages/
│   │   │   ├── chat/
│   │   │   ├── workspace/
│   │   │   └── settings/
│   │   └── styles/
│   ├── package.json
│   └── tsconfig.json
├── kubernetes/
│   ├── 01-infrastructure.yaml
│   ├── 02-services.yaml
│   ├── 03-agents.yaml
│   └── 04-frontend.yaml
├── docker/
│   ├── Dockerfile.services
│   ├── Dockerfile.agents
│   └── Dockerfile.frontend
├── docker-compose.yaml
└── README.md
```

## GPU Memory Management

The system is designed for a single NVIDIA RTX 3070 (8GB VRAM). Models are lazy-loaded and unloaded after use to prevent memory exhaustion:

- **SDSA Agent**: Loads sentence-transformers, CLIP, LLaVA on demand
- **VoiceIO Agent**: Loads Whisper, Coqui TTS on demand
- **Conversational Agent**: Uses Ollama (manages its own memory)

## License

MIT License - See [LICENSE](LICENSE) for details.
