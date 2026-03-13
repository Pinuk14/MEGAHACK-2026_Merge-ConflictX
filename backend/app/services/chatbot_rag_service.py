from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
import json
import os

import faiss
import numpy as np

from backend.models.embedding_features import EmbeddingConfig, EmbeddingExtractor
from backend.preprocessing.chunker import ChunkingConfig, TextChunker


@dataclass
class ChatDocument:
    file_id: str
    title: str
    text: str


class ChatbotRAGService:
    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.base_dir = self.project_root / "infrastructure" / "storage" / "chatbot"
        self.collections_dir = self.base_dir / "collections"
        self.registry_path = self.base_dir / "collections_registry.json"
        self.collections_dir.mkdir(parents=True, exist_ok=True)

        self.embedding_model = os.environ.get("CHAT_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self._extractor_cache: Dict[str, EmbeddingExtractor] = {}
        self.default_history_turns = int(os.environ.get("CHAT_MEMORY_HISTORY_TURNS", "4"))
        self.default_memory_top_k = int(os.environ.get("CHAT_MEMORY_TOP_K", "3"))

    def list_collections(self) -> List[Dict[str, Any]]:
        if not self.registry_path.exists():
            return []
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            return []
        return []

    def create_collection(self, documents: List[ChatDocument], name: Optional[str] = None) -> Dict[str, Any]:
        if not documents:
            raise ValueError("At least one document is required to create a collection.")

        collection_id = f"kb_{uuid4().hex[:10]}"
        collection_name = (name or collection_id).strip() or collection_id
        collection_dir = self.collections_dir / collection_id
        collection_dir.mkdir(parents=True, exist_ok=True)

        return self._persist_collection(
            collection_id=collection_id,
            collection_name=collection_name,
            collection_dir=collection_dir,
            documents=documents,
            append=False,
        )

    def add_documents(self, collection_id: str, documents: List[ChatDocument]) -> Dict[str, Any]:
        if not documents:
            raise ValueError("At least one document is required to append.")

        collection_dir = self.collections_dir / collection_id
        if not collection_dir.exists():
            raise FileNotFoundError(f"Collection '{collection_id}' not found.")

        meta = self._read_json(collection_dir / "metadata.json", default={})
        collection_name = str(meta.get("name") or collection_id)

        return self._persist_collection(
            collection_id=collection_id,
            collection_name=collection_name,
            collection_dir=collection_dir,
            documents=documents,
            append=True,
        )

    def answer_question(
        self,
        collection_id: str,
        question: str,
        top_k: int = 5,
        session_id: Optional[str] = None,
        history_turns: Optional[int] = None,
        memory_top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not question.strip():
            raise ValueError("Question cannot be empty.")

        collection_dir = self.collections_dir / collection_id
        if not collection_dir.exists():
            raise FileNotFoundError(f"Collection '{collection_id}' not found.")

        metadata = self._read_json(collection_dir / "metadata.json", default={})
        chunks: List[Dict[str, Any]] = self._read_json(collection_dir / "chunks.json", default=[])
        if not chunks:
            raise ValueError("Collection has no chunks to query.")

        resolved_session_id = self._resolve_session_id(session_id)
        history_turn_limit = max(1, min(int(history_turns or self.default_history_turns), 10))
        memory_k = max(0, min(int(memory_top_k or self.default_memory_top_k), 10))
        session_turns = self._load_session_turns(collection_dir, resolved_session_id)

        index_path = collection_dir / "index.faiss"
        if not index_path.exists():
            raise ValueError("Collection index is missing.")
        index = faiss.read_index(str(index_path))

        model_name = str(metadata.get("embedding_model") or self.embedding_model)
        extractor = self._get_extractor(model_name)
        query_embedding = extractor.encode([question], show_progress=False)
        if query_embedding.size == 0:
            raise ValueError("Failed to embed the question.")

        k = max(1, min(top_k, len(chunks)))
        distances, indices = index.search(query_embedding.astype("float32"), k)

        retrieved: List[Dict[str, Any]] = []
        for rank, idx in enumerate(indices[0].tolist()):
            if idx < 0 or idx >= len(chunks):
                continue
            distance = float(distances[0][rank])
            chunk = chunks[idx]
            retrieved.append(
                {
                    "rank": rank + 1,
                    "score": 1.0 / (1.0 + max(distance, 0.0)),
                    "chunk": chunk,
                }
            )

        if not retrieved:
            raise ValueError("No relevant context could be retrieved for this question.")

        recent_history = session_turns[-history_turn_limit:] if history_turn_limit > 0 else []
        long_term_memories = self._search_session_memories(
            collection_dir=collection_dir,
            session_id=resolved_session_id,
            question=question,
            top_k=memory_k,
        )

        prompt = self._build_qa_prompt(
            question=question,
            retrieved=retrieved,
            recent_history=recent_history,
            long_term_memories=long_term_memories,
        )
        llm_result = self._ask_llm(prompt=prompt)

        self._append_session_turn(
            collection_dir=collection_dir,
            session_id=resolved_session_id,
            user_question=question,
            assistant_answer=llm_result["answer"],
        )

        citations = [
            {
                "document_title": str(item["chunk"].get("document_title", "Untitled")),
                "chunk_index": int(item["chunk"].get("chunk_index", 0)),
                "score": round(float(item["score"]), 4),
                "excerpt": str(item["chunk"].get("text", ""))[:260],
            }
            for item in retrieved
        ]

        return {
            "collection_id": collection_id,
            "session_id": resolved_session_id,
            "question": question,
            "answer": llm_result["answer"],
            "model": llm_result["model"],
            "llm_fallback": llm_result["fallback"],
            "memory": {
                "history_turns_used": len(recent_history),
                "long_term_memories_used": len(long_term_memories),
            },
            "citations": citations,
        }

    def _persist_collection(
        self,
        collection_id: str,
        collection_name: str,
        collection_dir: Path,
        documents: List[ChatDocument],
        append: bool,
    ) -> Dict[str, Any]:
        existing_docs: List[Dict[str, Any]] = []
        existing_chunks: List[Dict[str, Any]] = []
        if append:
            existing_docs = self._read_json(collection_dir / "documents.json", default=[])
            existing_chunks = self._read_json(collection_dir / "chunks.json", default=[])

        new_documents = [
            {
                "file_id": doc.file_id,
                "title": doc.title,
                "char_count": len(doc.text),
                "created_at": datetime.utcnow().isoformat(),
            }
            for doc in documents
        ]
        all_documents = existing_docs + new_documents

        chunker = TextChunker(
            ChunkingConfig(
                chunk_size=700,
                chunk_overlap=80,
                min_chunk_size=80,
                max_chunk_size=1200,
                sentence_aware=True,
            )
        )

        generated_chunks: List[Dict[str, Any]] = []
        for doc in documents:
            doc_id = doc.file_id or f"doc_{uuid4().hex[:8]}"
            chunks = chunker.chunk_text(
                text=doc.text,
                document_id=doc_id,
                document_title=doc.title,
                source="upload",
                extra_metadata={"file_id": doc.file_id},
            )
            generated_chunks.extend([c.to_dict() for c in chunks])

        all_chunks = existing_chunks + generated_chunks
        if not all_chunks:
            raise ValueError("No chunkable text found in uploaded documents.")

        extractor = self._get_extractor(self.embedding_model)
        texts = [str(chunk.get("text", "")) for chunk in all_chunks]
        embeddings = extractor.encode(texts, show_progress=False)
        if embeddings.size == 0:
            raise ValueError("Embedding generation failed.")

        index = faiss.IndexFlatL2(int(embeddings.shape[1]))
        index.add(embeddings.astype("float32"))

        np.save(collection_dir / "embeddings.npy", embeddings.astype("float32"))
        faiss.write_index(index, str(collection_dir / "index.faiss"))

        with open(collection_dir / "documents.json", "w", encoding="utf-8") as f:
            json.dump(all_documents, f, indent=2, ensure_ascii=False)
        with open(collection_dir / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, indent=2, ensure_ascii=False)

        metadata = {
            "collection_id": collection_id,
            "name": collection_name,
            "embedding_model": self.embedding_model,
            "document_count": len(all_documents),
            "chunk_count": len(all_chunks),
            "updated_at": datetime.utcnow().isoformat(),
            "created_at": self._read_json(collection_dir / "metadata.json", default={}).get("created_at")
            or datetime.utcnow().isoformat(),
        }
        with open(collection_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        self._upsert_registry(metadata)
        return metadata

    def _upsert_registry(self, item: Dict[str, Any]) -> None:
        existing = self.list_collections()
        existing = [x for x in existing if str(x.get("collection_id")) != str(item.get("collection_id"))]
        existing.append(item)
        existing.sort(key=lambda x: str(x.get("updated_at", "")), reverse=True)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    def _get_extractor(self, model_name: str) -> EmbeddingExtractor:
        if model_name in self._extractor_cache:
            return self._extractor_cache[model_name]
        extractor = EmbeddingExtractor(
            EmbeddingConfig(
                model_name=model_name,
                show_progress=False,
                batch_size=32,
                normalize=True,
            )
        )
        self._extractor_cache[model_name] = extractor
        return extractor

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    @staticmethod
    def _build_qa_prompt(
        question: str,
        retrieved: List[Dict[str, Any]],
        recent_history: List[Dict[str, Any]],
        long_term_memories: List[Dict[str, Any]],
    ) -> str:
        context_lines: List[str] = []
        for item in retrieved:
            chunk = item["chunk"]
            title = str(chunk.get("document_title", "Untitled"))
            chunk_idx = int(chunk.get("chunk_index", 0))
            text = str(chunk.get("text", "")).strip()
            context_lines.append(f"[Source: {title} | chunk {chunk_idx}]\n{text}")

        context_block = "\n\n".join(context_lines)

        conversation_lines: List[str] = []
        for turn in recent_history:
            user_text = str(turn.get("user", "")).strip()
            assistant_text = str(turn.get("assistant", "")).strip()
            if user_text:
                conversation_lines.append(f"User: {user_text}")
            if assistant_text:
                conversation_lines.append(f"Bot: {assistant_text}")
        conversation_block = "\n".join(conversation_lines) if conversation_lines else "User: (no previous conversation)"

        memory_lines: List[str] = []
        for idx, item in enumerate(long_term_memories, start=1):
            memory_lines.append(f"[{idx}] {str(item.get('text', '')).strip()}")
        memory_block = "\n".join(memory_lines) if memory_lines else "(none)"

        return (
            "You are a retrieval-augmented assistant. "
            "Use the uploaded document context as the primary source of truth, and use conversation memory only to resolve references. "
            "If the answer is not present in uploaded data, say you cannot find it in the uploaded data. "
            "Give a concise answer and include 2-4 evidence bullets quoting key phrases from the source context.\n\n"
            "Previous conversation:\n"
            f"{conversation_block}\n\n"
            "Relevant long-term memory from this session:\n"
            f"{memory_block}\n\n"
            "Current question:\n"
            f"{question.strip()}\n\n"
            "Context from uploaded documents:\n"
            f"{context_block}\n"
        )

    def _resolve_session_id(self, session_id: Optional[str]) -> str:
        cleaned = str(session_id or "").strip()
        if cleaned:
            return cleaned
        return f"sess_{uuid4().hex[:12]}"

    def _sessions_dir(self, collection_dir: Path) -> Path:
        path = collection_dir / "sessions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _session_dir(self, collection_dir: Path, session_id: str) -> Path:
        path = self._sessions_dir(collection_dir) / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _load_session_turns(self, collection_dir: Path, session_id: str) -> List[Dict[str, Any]]:
        session_dir = self._session_dir(collection_dir, session_id)
        turns = self._read_json(session_dir / "history.json", default=[])
        return turns if isinstance(turns, list) else []

    def _append_session_turn(
        self,
        collection_dir: Path,
        session_id: str,
        user_question: str,
        assistant_answer: str,
    ) -> None:
        session_dir = self._session_dir(collection_dir, session_id)
        history_path = session_dir / "history.json"
        turns = self._read_json(history_path, default=[])
        if not isinstance(turns, list):
            turns = []
        turns.append(
            {
                "turn_id": f"turn_{uuid4().hex[:10]}",
                "timestamp": datetime.utcnow().isoformat(),
                "user": user_question.strip(),
                "assistant": assistant_answer.strip(),
            }
        )
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(turns, f, indent=2, ensure_ascii=False)
        self._rebuild_session_memory_index(session_dir=session_dir, turns=turns)

    def _rebuild_session_memory_index(self, session_dir: Path, turns: List[Dict[str, Any]]) -> None:
        memory_records: List[Dict[str, Any]] = []
        memory_texts: List[str] = []

        for turn in turns:
            user_text = str(turn.get("user", "")).strip()
            assistant_text = str(turn.get("assistant", "")).strip()
            if not user_text and not assistant_text:
                continue

            memory_text = f"User asked: {user_text}\nAssistant answered: {assistant_text}".strip()
            memory_records.append(
                {
                    "turn_id": str(turn.get("turn_id", "")),
                    "timestamp": str(turn.get("timestamp", "")),
                    "text": memory_text,
                }
            )
            memory_texts.append(memory_text)

        with open(session_dir / "memory_records.json", "w", encoding="utf-8") as f:
            json.dump(memory_records, f, indent=2, ensure_ascii=False)

        if not memory_texts:
            memory_index_path = session_dir / "memory_index.faiss"
            if memory_index_path.exists():
                memory_index_path.unlink()
            return

        extractor = self._get_extractor(self.embedding_model)
        memory_embeddings = extractor.encode(memory_texts, show_progress=False)
        if memory_embeddings.size == 0:
            return

        memory_index = faiss.IndexFlatL2(int(memory_embeddings.shape[1]))
        memory_index.add(memory_embeddings.astype("float32"))
        faiss.write_index(memory_index, str(session_dir / "memory_index.faiss"))

    def _search_session_memories(
        self,
        collection_dir: Path,
        session_id: str,
        question: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        if top_k <= 0:
            return []

        session_dir = self._session_dir(collection_dir, session_id)
        memory_index_path = session_dir / "memory_index.faiss"
        memory_records: List[Dict[str, Any]] = self._read_json(session_dir / "memory_records.json", default=[])

        if not memory_index_path.exists() or not memory_records:
            return []

        try:
            memory_index = faiss.read_index(str(memory_index_path))
        except Exception:
            return []

        extractor = self._get_extractor(self.embedding_model)
        query_embedding = extractor.encode([question], show_progress=False)
        if query_embedding.size == 0:
            return []

        k = max(1, min(top_k, len(memory_records)))
        distances, indices = memory_index.search(query_embedding.astype("float32"), k)

        hits: List[Dict[str, Any]] = []
        seen_indices = set()
        for rank, idx in enumerate(indices[0].tolist()):
            if idx < 0 or idx >= len(memory_records) or idx in seen_indices:
                continue
            seen_indices.add(idx)
            record = memory_records[idx]
            distance = float(distances[0][rank])
            hits.append(
                {
                    "rank": rank + 1,
                    "score": 1.0 / (1.0 + max(distance, 0.0)),
                    "text": str(record.get("text", "")),
                    "turn_id": str(record.get("turn_id", "")),
                }
            )
        return hits

    @staticmethod
    def _ask_llm(prompt: str) -> Dict[str, Any]:
        model = os.environ.get("OLLAMA_MODEL", "mistral:latest")
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        try:
            import ollama  # type: ignore

            client = ollama.Client(host=host)
            response = client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": float(os.environ.get("CHAT_LLM_TEMPERATURE", "0.2")),
                    "num_predict": int(os.environ.get("CHAT_LLM_MAX_TOKENS", "600")),
                },
            )
            text = (getattr(response, "message", None).content if getattr(response, "message", None) else "") or ""
            cleaned = str(text).strip()
            if cleaned:
                return {"answer": cleaned, "model": model, "fallback": False}
        except Exception:
            pass

        fallback_answer = (
            "I could not access the LLM right now, so this is a context-only fallback. "
            "Please ensure Ollama is running for higher-quality responses."
        )
        return {"answer": fallback_answer, "model": "fallback", "fallback": True}


_chatbot_service: Optional[ChatbotRAGService] = None


def get_chatbot_rag_service() -> ChatbotRAGService:
    global _chatbot_service
    if _chatbot_service is None:
        _chatbot_service = ChatbotRAGService()
    return _chatbot_service
