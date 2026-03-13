from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.pipelines import InsightOutputStorage, InsightStorageConfig
from backend.app.schema import DocumentInsight, InsightBatch
from backend.app.services import (
    ClauseDetectionService,
    SemanticSegmentationService,
    StakeholderExtractionService,
    SummarizationService,
    TopicClassificationService,
)
from backend.app.services.scrape_memory_service import ScrapeMemoryService
from backend.app.services.website_knowledge_service import WebsiteKnowledgeService

router = APIRouter(tags=["analysis"])


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=20, description="Raw policy/research text to analyze")
    document_id: Optional[str] = Field(default=None, description="Optional stable document id")
    source_filename: Optional[str] = Field(default=None, description="Optional source filename")
    persist_output: bool = Field(default=True, description="Persist JSON insight artifacts to outputs directory")
    attachments: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional attachments (base64 or link info)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional page metadata (author, published_time, url, etc.)")
    full_html: Optional[str] = Field(default=None, description="Optional full page HTML from extension scrape")


class AnalyzeResponse(BaseModel):
    insight: DocumentInsight
    metrics: Dict[str, Any]
    storage: Optional[Dict[str, Any]] = None


class _SingleDocumentAnalyzer:
    def __init__(self) -> None:
        self.segmentation_service = SemanticSegmentationService()
        self.clause_service = ClauseDetectionService()
        self.stakeholder_service = StakeholderExtractionService()
        self.topic_service = TopicClassificationService()
        self.summary_service = SummarizationService()
        self.memory_service = ScrapeMemoryService(project_root=Path(__file__).resolve().parents[3])
        self.website_knowledge_service = WebsiteKnowledgeService(project_root=Path(__file__).resolve().parents[3])

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Request text is empty")

        document_id = request.document_id or f"api-{uuid4().hex[:12]}"

        segments = self.segmentation_service.segment_document(
            text=text,
            document_id=document_id,
            source_filename=request.source_filename,
        )
        clauses = self.clause_service.detect_from_segments(segments)
        stakeholders = self.stakeholder_service.extract_from_segments(segments)
        topics = self.topic_service.classify_from_segments(segments)
        executive_summary = self.summary_service.summarize(
            text=text,
            clauses=clauses,
            stakeholders=stakeholders,
            topics=topics,
        )

        insight = DocumentInsight(
            document_id=document_id,
            source_filename=request.source_filename,
            executive_summary=executive_summary,
            clauses=clauses,
            stakeholders=stakeholders,
            topics=topics,
        )

        metrics = {
            "segments": len(segments),
            "clauses": len(clauses),
            "stakeholders": len(stakeholders),
            "topics": len(topics),
        }

        storage_info: Optional[Dict[str, Any]] = None
        memory_info: Optional[Dict[str, Any]] = None
        website_knowledge_info: Optional[Dict[str, Any]] = None

        # Persist scrape memory keyed by URL hash whenever URL metadata exists.
        page_url = (request.metadata or {}).get("url") if isinstance(request.metadata, dict) else None
        if page_url:
            scraped_payload = {
                "url": page_url,
                "text": request.text,
                "full_html": request.full_html,
                "metadata": request.metadata,
                "attachments": request.attachments,
                "source_filename": request.source_filename,
            }
            memory_ctx = self.memory_service.memory_context(page_url, scraped_payload)
            write = self.memory_service.remember_scrape(page_url, scraped_payload)
            memory_info = {
                "found_previous": memory_ctx.get("found_previous"),
                "content_changed": memory_ctx.get("content_changed"),
                "saved": write.get("saved"),
                "url_hash": write.get("url_hash"),
                "content_hash": write.get("content_hash"),
                "path": write.get("path"),
            }

            existing = self.website_knowledge_service.lookup(page_url)
            knowledge_write = self.website_knowledge_service.upsert(
                page_url,
                {
                    "summary": executive_summary.short_summary if hasattr(executive_summary, "short_summary") else None,
                    "metadata": request.metadata,
                    "signals": {
                        "text_length": len(text),
                        "clauses": len(clauses),
                        "stakeholders": len(stakeholders),
                        "topics": len(topics),
                    },
                },
            )
            website_knowledge_info = {
                "found_existing": existing.get("found"),
                "domain": knowledge_write.get("domain") or existing.get("domain"),
                "saved": knowledge_write.get("saved"),
                "path": knowledge_write.get("path"),
                "page_count": knowledge_write.get("page_count") or existing.get("page_count"),
                "similar_pages": existing.get("similar_pages") or [],
            }

        if request.persist_output:
            project_root = Path(__file__).resolve().parents[3]
            storage = InsightOutputStorage(project_root=project_root, config=InsightStorageConfig())
            batch_path, per_doc_paths = storage.save(InsightBatch(items=[insight]))
            storage_info = {
                "batch_file": str(batch_path),
                "document_files": [str(p) for p in per_doc_paths],
            }
            if memory_info:
                storage_info["memory"] = memory_info
            if website_knowledge_info:
                storage_info["website_knowledge"] = website_knowledge_info

        return AnalyzeResponse(insight=insight, metrics=metrics, storage=storage_info)


_analyzer = _SingleDocumentAnalyzer()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_document(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze one document and return structured insights."""
    return _analyzer.analyze(request)


@router.get("/website_knowledge")
def get_website_knowledge(url: str) -> Dict[str, Any]:
    """Return cached website intelligence for a URL/domain."""
    return _analyzer.website_knowledge_service.lookup(url)
