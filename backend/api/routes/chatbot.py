from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.job_manager import get_job_manager
from backend.app.services.chatbot_rag_service import ChatDocument, get_chatbot_rag_service


router = APIRouter(prefix="/chatbot", tags=["chatbot"])
job_manager = get_job_manager()
chatbot_service = get_chatbot_rag_service()


class BuildCollectionRequest(BaseModel):
    file_ids: List[str] = Field(default_factory=list)
    name: Optional[str] = None


class AppendCollectionRequest(BaseModel):
    file_ids: List[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    collection_id: str
    question: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=15)
    session_id: Optional[str] = None
    history_turns: int = Field(default=4, ge=1, le=10)
    memory_top_k: int = Field(default=3, ge=0, le=10)


def _uploads_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "infrastructure" / "storage" / "uploads"


def _filename_for_file_id(file_id: str) -> str:
    uploads = _uploads_dir()
    for path in uploads.glob(f"{file_id}_*"):
        name = path.name
        return name[len(file_id) + 1 :] if name.startswith(f"{file_id}_") else name
    return file_id


def _resolve_documents(file_ids: List[str]) -> List[ChatDocument]:
    docs: List[ChatDocument] = []
    missing: List[str] = []

    for file_id in [str(fid).strip() for fid in file_ids if str(fid).strip()]:
        text = job_manager.get_uploaded_file(file_id)
        if text is None:
            missing.append(file_id)
            continue
        if not text.strip():
            continue
        docs.append(
            ChatDocument(
                file_id=file_id,
                title=_filename_for_file_id(file_id),
                text=text.strip(),
            )
        )

    if missing:
        raise HTTPException(status_code=404, detail=f"File(s) not found: {', '.join(missing)}")
    if not docs:
        raise HTTPException(status_code=400, detail="No extractable text found in provided file_ids")
    return docs


@router.get("/collections")
def list_chat_collections() -> Dict[str, Any]:
    return {"collections": chatbot_service.list_collections()}


@router.post("/collections/from-files")
def create_collection_from_files(request: BuildCollectionRequest) -> Dict[str, Any]:
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="file_ids cannot be empty")

    try:
        docs = _resolve_documents(request.file_ids)
        metadata = chatbot_service.create_collection(documents=docs, name=request.name)
        return {
            "message": "Collection created successfully",
            "collection": metadata,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {exc}")


@router.post("/collections/{collection_id}/files")
def append_files_to_collection(collection_id: str, request: AppendCollectionRequest) -> Dict[str, Any]:
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="file_ids cannot be empty")

    try:
        docs = _resolve_documents(request.file_ids)
        metadata = chatbot_service.add_documents(collection_id=collection_id, documents=docs)
        return {
            "message": "Documents added successfully",
            "collection": metadata,
        }
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to append documents: {exc}")


@router.delete("/collections/{collection_id}/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(collection_id: str, session_id: str):
    collection_dir = chatbot_service.collections_dir / collection_id
    session_dir = collection_dir / "sessions" / session_id
    if not session_dir.exists():
        return
    try:
        shutil.rmtree(session_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {exc}")


@router.delete("/collections/{collection_id}/sessions", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_chat_sessions(collection_id: str):
    collection_dir = chatbot_service.collections_dir / collection_id
    sessions_dir = collection_dir / "sessions"
    if not sessions_dir.exists():
        return
    try:
        shutil.rmtree(sessions_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete chat sessions: {exc}")


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_chat_sessions_global():
    collections = chatbot_service.list_collections()
    try:
        for item in collections:
            collection_id = str(item.get("collection_id", "")).strip()
            if not collection_id:
                continue
            sessions_dir = chatbot_service.collections_dir / collection_id / "sessions"
            if sessions_dir.exists():
                shutil.rmtree(sessions_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {exc}")


@router.post("/ask")
def ask_chatbot(request: AskRequest) -> Dict[str, Any]:
    try:
        result = chatbot_service.answer_question(
            collection_id=request.collection_id,
            question=request.question,
            top_k=request.top_k,
            session_id=request.session_id,
            history_turns=request.history_turns,
            memory_top_k=request.memory_top_k,
        )
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {exc}")
