# ChatEpstein Setup Guide

A RAG (Retrieval-Augmented Generation) application for querying Jeffrey Epstein-related documents with citations. The system consists of a FastAPI backend and a Next.js frontend.

## Project Structure

```
JSearch/
├── chat/                   # FastAPI backend
│   ├── api.py             # FastAPI endpoints
│   └── chatbot.py         # RAG chain setup
├── frontend/              # Next.js frontend
│   └── chat-frontend/     # React/Next.js app
├── VectorStore/           # Vector database and ingestion scripts
├── s3/                    # S3 integration scripts
├── models/                # Model configurations
├── chroma_db/            # ChromaDB storage
└── requirements.txt       # Python dependencies
```

## Prerequisites

- Python 3.12+
- Node.js 16+ and npm
- AWS account (for S3)
- Pinecone account (for vector database)
- Groq API key (for LLM)

## Environment Variables

### Backend (.env in root directory)

Create a `.env` file in the root directory:

```bash
# AWS Configuration
AWS_BUCKET_NAME=your-bucket-name
AWS_REGION=us-east-2
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Groq API
GROQ_KEY=your-groq-api-key
MODEL_NAME=llama-3.1-8b-instant

# Pinecone
PINECONE_API_KEY=your-pinecone-api-key

# Database
DB_DIR=../chroma_db

# Server URLs
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# API Security
BACKEND_API_KEY=your-secure-api-key
```

### Frontend (.env.local in frontend/chat-frontend/)

Create a `.env.local` file in the `frontend/chat-frontend/` directory:

```bash
# FastAPI Backend URL
BACKEND_URL=http://localhost:8000
BACKEND_API_KEY=your-secure-api-key
```

## Installation

### 1. Backend Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Download spaCy language model (if needed)
python -m spacy download en_core_web_sm
```

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend/chat-frontend

# Install Node dependencies
npm install

# Return to root directory
cd ../..
```

## Running the Application

### Development Mode

#### Start Backend

```bash
# Activate virtual environment
source venv/bin/activate

# Run FastAPI server
cd chat
python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

#### Start Frontend

In a new terminal:

```bash
cd frontend/chat-frontend
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Production Mode

#### Backend

```bash
source venv/bin/activate
cd chat
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Frontend

```bash
cd frontend/chat-frontend
npm run build
npm start
```

## Vector Database Setup

### Ingesting Documents

The project includes scripts for ingesting different document types:

```bash
# Ingest PDF documents
python VectorStore/ingest_pdfs.py

# Ingest text documents
python VectorStore/ingest_text.py

# Ingest images with OCR
python VectorStore/ingest_images.py

# Run complete pipeline
python VectorStore/start_pipeline.py
```

### S3 Document Upload

To upload documents from S3:

```bash
python s3/DOJ/UploadDojFiles.py
```

## Key Features

- **RAG System**: Query documents with context-aware responses
- **Citation Support**: Responses include source citations
- **Rate Limiting**: API rate limiting to prevent abuse
- **Session Management**: Conversation history tracking
- **Vector Search**: Efficient similarity search using Pinecone
- **Multi-format Support**: PDF, text, and image (OCR) ingestion

## API Endpoints

### POST `/chat`

Query the RAG system with a message.

**Request:**
```json
{
  "message": "What do you know about Les Wexner?",
  "session_id": "user-123"
}
```

**Response:**
```json
{
  "response": "...",
  "sources": [...],
  "session_id": "user-123"
}
```

### GET `/health`

Check API health status.

## Development Stack

### Backend
- FastAPI - Web framework
- LangChain - RAG orchestration
- Pinecone - Vector database
- ChromaDB - Local vector storage
- Groq - LLM provider
- PyTorch (CPU) - ML framework
- Sentence Transformers - Embeddings

### Frontend
- Next.js 16 - React framework
- TypeScript - Type safety
- TailwindCSS - Styling
- React Markdown - Markdown rendering

## Troubleshooting

### Backend Issues

**Import errors:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

**Database connection issues:**
- Verify Pinecone API key is correct
- Check network connectivity
- Ensure ChromaDB directory exists

### Frontend Issues

**Connection refused:**
- Verify backend is running on port 8000
- Check `BACKEND_URL` in `.env.local`
- Ensure CORS is properly configured

**Build errors:**
```bash
# Clear Next.js cache
rm -rf .next
npm run build
```

## Deployment

The project includes configuration for Railway deployment:

- `Procfile` - Process configuration
- `nixpacks.toml` - Nixpacks build configuration

For deployment, ensure all environment variables are properly configured in your hosting platform.

## Security Notes

- Never commit `.env` files to version control
- Use strong API keys for production
- Implement proper authentication for production use
- Rate limiting is enabled by default
- CORS is configured for specific origins

## License

[Add your license information here]
