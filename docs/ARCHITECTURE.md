# ARCHITECTURE.md

## High-Level Overview

MEGAHACK-2026_Merge-ConflictX is a modular platform for multimodal document analysis, legal AI, and data processing. It integrates backend services, frontend interfaces, machine learning pipelines, and infrastructure for scalable document ingestion, cleaning, feature extraction, vector-based retrieval, validation, and export.

---

## Directory Map

```
backend/           # Core backend logic, APIs, models, pipelines, preprocessing, validation, vector store
frontend/          # React-based web application for user interaction and visualization
extension/         # Browser extension for scraping and integration
ml_workspace/      # Machine learning experiments, datasets, notebooks, and scripts
infrastructure/    # Logs and storage for processed and raw documents
scripts/           # Shell scripts for data ingestion and pipeline execution
docker/            # Dockerfiles and compose for containerized deployment
main.py            # Entry point for backend or orchestration
pyproject.toml     # Python project configuration
README.md          # Project overview and instructions
```

---

## Module Responsibilities & Key Files

### backend/

- **Responsibility:** Backend services, APIs, models, preprocessing, validation, vector store, orchestration.
- **Key Files/Folders:**
  - `api/` (API routes/controllers)
  - `models/` (ML models, embeddings, classifiers)
  - `preprocessing/` (Data cleaning, chunking, feature extraction)
  - `vector_store/` (Vector retrieval, FAISS integration)
  - `validation/` (Strict validation, error reporting)
  - `services/` (Business logic, summarization, classification)
  - `utils/` (Shared utilities)
  - `schemas/` (Output schemas)
  - `pipelines/` (Orchestration logic)
  - `requirements.txt` (Backend dependencies)
- **Interactions:**
  - API routes call services and models
  - Preprocessing modules feed data to models and vector store
  - Validation modules check outputs and generate reports
  - Vector store enables retrieval for chatbot and search

### frontend/

- **Responsibility:** User interface, dashboards, document viewer, analytics, upload, integration with backend APIs.
- **Key Files/Folders:**
  - `src/` (React components, pages, services)
  - `public/` (Static assets)
  - `package.json` (Frontend dependencies)
- **Interactions:**
  - Calls backend APIs for data processing and visualization
  - Handles export and integration formats

### extension/

- **Responsibility:** Browser scraping, integration with web sources, popup UI.
- **Key Files/Folders:**
  - `manifest.json` (Extension manifest)
  - `src/` (Service worker, content scripts, popup)
- **Interactions:**
  - Scrapes data and sends to backend

### ml_workspace/

- **Responsibility:** ML experiments, datasets, notebooks, training/evaluation scripts.
- **Key Files/Folders:**
  - `data/` (Labeled, processed, raw datasets)
  - `notebooks/` (Jupyter notebooks)
  - `scripts/` (ML scripts)
  - `requirements.txt` (ML dependencies)
- **Interactions:**
  - Provides models and embeddings to backend

### infrastructure/

- **Responsibility:** Storage and logs for documents and outputs.
- **Key Files/Folders:**
  - `logs/` (System logs)
  - `storage/` (Document storage: cleaned, embeddings, outputs, raw)
- **Interactions:**
  - Backend reads/writes processed and raw documents

### scripts/

- **Responsibility:** Shell scripts for data ingestion and pipeline execution.
- **Key Files/Folders:**
  - `ingest_data.sh`, `run_pipeline.sh`
- **Interactions:**
  - Used for batch jobs and automation

### docker/

- **Responsibility:** Containerization and orchestration.
- **Key Files/Folders:**
  - `backend.Dockerfile`, `frontend.Dockerfile`, `docker-compose.yml`
- **Interactions:**
  - Enables deployment of backend, frontend, and services

---

## Execution Flows

### Request Flow (API)

1. User interacts with frontend or extension
2. Frontend sends request to backend API (`backend/api/`)
3. API routes invoke services, models, preprocessing, and vector store
4. Validation modules check results
5. Response sent back to frontend for visualization/export

### Job Processing/Data Flow

- Data ingested via scripts or extension
- Preprocessing and cleaning modules process documents
- Features extracted and embeddings generated
- Stored in vector store and infrastructure storage
- Models and services perform analysis, classification, summarization
- Validation and error reporting modules generate reports

#### Parse → Clean → Chunk → Embed → Index

1. **Parse**: Raw documents are parsed by modality-specific cleaners (PDF, TXT, XML, WAV).
2. **Clean**: Normalized, de-noised content is persisted in infrastructure/storage/cleaned_documents.
3. **Chunk**: Text is segmented into overlapping chunks for downstream feature extraction.
4. **Embed**: Dense embeddings are generated using sentence-transformers (see backend/models/embedding_features.py).
5. **Index**: FAISS index is built and stored for similarity search (see backend/vector_store/faiss_integration.py).

---

## Entry Points

- `main.py` (Backend entry point)
- `backend/api/main.py` (API server)
- `backend/pipelines/orchestration.py` (Final pipeline runner)
- `frontend/src/index.jsx` (Frontend entry)
- `scripts/ingest_data.sh`, `scripts/run_pipeline.sh` (CLI batch jobs)
- `docker/docker-compose.yml` (Container orchestration)

---

## Major Services, Utilities, and Shared Libraries

- `backend/services/` (Summarization, topic classification, clause detection)
- `backend/utils/` (File handling, logging, model loading)
- `backend/models/` (Embeddings, classifiers, NER, segmentation)
- `backend/vector_store/` (FAISS integration, retrieval)
  - **FAISS Integration**: Handles creation, saving, loading, and querying of a FAISS index for efficient similarity search. The `FaissIndex` class provides methods for adding embeddings, searching, and managing the index.
- `backend/pipelines/orchestration.py`
  - **Final Pipeline**: Supports both local test-folder data and production upload-manifest data.
- `backend/api/routes/ingestion.py`
  - **Upload Endpoint**: `POST /ingestion/upload-texts` stores uploaded files and writes `infrastructure/storage/uploads/uploaded_documents.json` for production pipeline mode.

---

## Coding Conventions & Architectural Patterns

- Modular folder structure by responsibility
- API routes/controllers in `backend/api/routes/`
- Business logic in `backend/services/`
- Models and embeddings in `backend/models/`
- Preprocessing and cleaning in `backend/preprocessing/`
- Validation and error reporting in `backend/validation/`
- Vector store and retrieval in `backend/vector_store/`
- Use of interfaces/abstractions for pluggable modules (e.g., vector store)
- Consistent naming: snake_case for Python, camelCase for JS/React
- Separation of concerns: UI, API, business logic, storage

---

## Guidelines for AI Assistants (Copilot)

- **Business Logic:** Place in `backend/services/` for reusable, testable code
- **API Routes/Controllers:** Implement in `backend/api/routes/`
- **Database Access:** (If used) Should be in dedicated modules or services, not in routes/controllers
- **Naming Conventions:**
  - Python: snake_case for files, functions, variables; PascalCase for classes
  - JS/React: camelCase for functions/variables, PascalCase for components
- **Schema Definitions:** Use `backend/schemas/` for structured outputs
- **Model Code:** Place in `backend/models/`
- **Preprocessing:** Use `backend/preprocessing/` for data cleaning, chunking, feature extraction
- **Validation:** Use `backend/validation/` for error reporting and strict checks
- **Vector Store:** Use `backend/vector_store/` for retrieval and storage logic
- **Frontend Integration:** Use `frontend/src/services/api.js` for API calls

---

This file is intended to help developers and AI assistants quickly understand, navigate, and extend the project structure.
