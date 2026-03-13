# ARCHITECTURE.md

## High-Level Overview

MEGAHACK-2026_Merge-ConflictX is a modular platform for multimodal document analysis, legal AI, and data processing. It integrates backend services, frontend interfaces, machine learning pipelines, and infrastructure for scalable document ingestion, cleaning, feature extraction, vector-based retrieval, validation, and export.

The platform now supports three connected backend analysis layers:

1. **Data Pipeline (Parse/Clean/Chunk/Embed/Index)**
2. **Insight Pipeline (Semantic Segmentation/Clause Detection/Stakeholder Extraction/Topic Classification/Summarization)**
3. **Chatbot RAG Layer (Dataset Collections + Session Memory + Long-term Conversational Retrieval)**

Combined end-to-end flow:

`raw_documents -> cleaned_documents -> embeddings + FAISS -> insight extraction -> outputs -> chatbot collections/sessions -> API -> frontend`

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
  - `app/schema/` (Structured document insight schemas)
  - `app/services/` (Insight services: segmentation, clause detection, stakeholders, topics, summarization)
  - `app/pipelines/` (Insight orchestration + output persistence)
  - `models/` (ML models, embeddings, classifiers)
  - `preprocessing/` (Data cleaning, chunking, feature extraction)
  - `vector_store/` (Vector retrieval, FAISS integration)
  - `validation/` (Strict validation, error reporting)
  - `services/` (Existing/legacy backend business logic)
  - `utils/` (Shared utilities)
  - `schemas/` (Output schemas)
  - `pipelines/` (Orchestration logic)
  - `requirements.txt` (Backend dependencies)
- **Interactions:**
  - API routes call services and models
  - Preprocessing modules feed data to models and vector store
  - Insight pipeline consumes cleaned/merged records and emits structured JSON insights
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
  - Includes mission-scoped chatbot UI with quick-question actions
  - Persists active mission/session/chat transcript in browser localStorage for refresh recovery
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
  - `storage/chatbot/collections/<collection_id>/` (RAG chunks, FAISS index, metadata)
  - `storage/chatbot/collections/<collection_id>/sessions/<session_id>/` (history + session memory index)
- **Interactions:**
  - Backend reads/writes processed and raw documents
  - Chatbot service persists collection indexes and conversational memory state

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
3. API routes invoke services, pipelines, models, preprocessing, and vector store
4. Validation modules check results
5. Response sent back to frontend for visualization/export

#### Insight Request Flow (`POST /analyze`)

1. Client submits document text to `POST /analyze`
2. API route optionally verifies/normalizes extracted text with Ollama (`LLMService.verify_extracted_text`) one document at a time
3. Semantic segmentation runs on verified text
4. Clause detection, stakeholder extraction, and topic classification run on segments
5. Summarization creates executive summary
6. Structured `DocumentInsight` is returned (and optionally persisted to `infrastructure/storage/outputs/insights`)

#### Chatbot Request Flow (Collection + Ask + Memory)

1. Frontend creates/reuses a chatbot collection from uploaded `file_ids` (`POST /chatbot/collections/from-files`).
2. Collection stores chunked content + embeddings + FAISS index in `infrastructure/storage/chatbot/collections/<collection_id>/`.
3. User asks a question (`POST /chatbot/ask`) with optional `session_id`.
4. Backend retrieves document context from collection index (RAG retrieval).
5. Backend retrieves short-term context (last N turns) and long-term session memories (semantic search over prior turns).
6. Prompt combines: previous conversation, long-term memory snippets, current question, and retrieved document context.
7. LLM generates answer; backend persists turn to session history and updates session memory index.
8. Frontend displays answer with citations and keeps session continuity across refreshes.

### Job Processing/Data Flow

- Data ingested via scripts or extension
- Preprocessing and cleaning modules process documents
- Features extracted and embeddings generated
- Stored in vector store and infrastructure storage
- Models and services perform analysis, classification, summarization
- Validation and error reporting modules generate reports

#### Insight Pipeline Flow (Step 1-8)

1. Load merged cleaned records from `infrastructure/storage/cleaned_documents/merged_multimodal.json`
2. For each document, optionally verify/normalize extracted text with Ollama
3. Semantic segmentation
4. Clause detection
5. Stakeholder extraction
6. Topic classification
7. Summarization
8. Orchestrate into `DocumentInsight` / `InsightBatch` and persist outputs under `infrastructure/storage/outputs/insights`

#### Parse → Clean → Chunk → Embed → Index

1. **Parse**: Raw documents are parsed by modality-specific cleaners (PDF, TXT, XML, WAV).

- PDF parsing now includes **OCR fallback** for scanned/non-selectable PDFs via `backend/cleaning/ocr_module.py` + EasyOCR.
- OCR fallback can be toggled at runtime with `PipelineConfig.use_pdf_ocr_fallback` or CLI flag `--disable-pdf-ocr`.

2. **Clean**: Normalized, de-noised content is persisted in infrastructure/storage/cleaned_documents.
3. **Chunk**: Text is segmented into overlapping chunks for downstream feature extraction.
4. **Embed**: Dense embeddings are generated using sentence-transformers (see backend/models/embedding_features.py).
5. **Index**: FAISS index is built and stored for similarity search (see backend/vector_store/faiss_integration.py).

---

## Entry Points

- `main.py` (Backend entry point)
- `backend/api/main.py` (API server)
- `backend/api/routes/analysis.py` (`POST /analyze` insight endpoint)
- `backend/api/routes/chatbot.py` (chatbot collection/session/Q&A endpoints)
- `backend/app/services/chatbot_rag_service.py` (chatbot RAG + conversation memory service)
- `backend/pipelines/orchestration.py` (Final pipeline runner)
- `backend/app/pipelines/insight_pipeline.py` (Insight pipeline runner)
- `frontend/src/index.jsx` (Frontend entry)
- `frontend/src/pages/Chatbot.jsx` (mission chatbot UI + quick prompts + session controls)
- `scripts/ingest_data.sh`, `scripts/run_pipeline.sh` (CLI batch jobs)
- `docker/docker-compose.yml` (Container orchestration)

---

## Major Services, Utilities, and Shared Libraries

- `backend/services/` (Summarization, topic classification, clause detection)
- `backend/app/schema/document_insight_schema.py`
  - **Document Insight Schema**: Pydantic contracts for `DocumentInsight`, `ClauseInsight`, `StakeholderImpact`, `TopicScore`, `ExecutiveSummary`, `InsightBatch`.
- `backend/app/services/`
  - **SemanticSegmentationService**: Splits document into semantic segments.
  - **ClauseDetectionService**: Detects policy/legal clauses from segments.
  - **StakeholderExtractionService**: Extracts stakeholder impact statements.
  - **TopicClassificationService**: Produces ranked topical labels.
  - **SummarizationService**: Builds executive summary, key points, recommendations.
  - **LLMService (Ollama)**: Verifies extracted text one-by-one before downstream analysis and enriches insight quality when enabled.
- `backend/app/pipelines/insight_pipeline.py`
  - **Insight Pipeline**: Orchestrates all insight services and generates per-document structured insights.
- `backend/app/pipelines/output_storage.py`
  - **Output Persistence**: Saves insight batch and per-document JSON outputs in `outputs/insights`.
- `backend/utils/` (File handling, logging, model loading)
- `backend/models/` (Embeddings, classifiers, NER, segmentation)
- `backend/cleaning/ocr_module.py`
  - **OCR Module**: EasyOCR-based extraction for scanned PDF pages when native text extraction is insufficient.
- `backend/vector_store/` (FAISS integration, retrieval)
  - **FAISS Integration**: Handles creation, saving, loading, and querying of a FAISS index for efficient similarity search. The `FaissIndex` class provides methods for adding embeddings, searching, and managing the index.
- `backend/pipelines/orchestration.py`
  - **Final Pipeline**: Supports both local test-folder data and production upload-manifest data.
- `backend/api/routes/ingestion.py`
  - **Upload Endpoint**: `POST /ingestion/upload-texts` stores uploaded files and writes `infrastructure/storage/uploads/uploaded_documents.json` for production pipeline mode.
- `backend/api/routes/analysis.py`
  - **Analyze Endpoint**: `POST /analyze` returns structured semantic insights and can persist them in outputs.
- `backend/app/services/chatbot_rag_service.py`
  - **Chatbot RAG Service**: Manages collection creation/appending, FAISS retrieval, LLM answering, session memory window, and long-term semantic memory retrieval.
- `backend/api/routes/chatbot.py`
  - **Chatbot Endpoints**:
    - `GET /chatbot/collections`
    - `POST /chatbot/collections/from-files`
    - `POST /chatbot/collections/{collection_id}/files`
    - `POST /chatbot/ask`
    - `DELETE /chatbot/collections/{collection_id}/sessions/{session_id}`
    - `DELETE /chatbot/collections/{collection_id}/sessions`
    - `DELETE /chatbot/sessions`
- `frontend/src/pages/Chatbot.jsx`
  - **Chat UX Layer**: Supports mission selection, predefined quick questions, new-session reset, single-chat delete, global history clear, and refresh-safe local state.

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
- **Insight Schema Definitions:** Use `backend/app/schema/` for document insight outputs
- **Model Code:** Place in `backend/models/`
- **Preprocessing:** Use `backend/preprocessing/` for data cleaning, chunking, feature extraction
- **Validation:** Use `backend/validation/` for error reporting and strict checks
- **Vector Store:** Use `backend/vector_store/` for retrieval and storage logic
- **Insight Services:** Use `backend/app/services/` for segmentation, clause detection, stakeholders, topics, summarization
- **Insight Orchestration:** Use `backend/app/pipelines/` for insight pipeline coordination and output persistence
- **Frontend Integration:** Use `frontend/src/services/api.js` for API calls

---

This file is intended to help developers and AI assistants quickly understand, navigate, and extend the project structure.
