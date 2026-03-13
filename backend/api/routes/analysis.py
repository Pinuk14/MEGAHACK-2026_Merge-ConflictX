from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
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

router = APIRouter(tags=["analysis"])


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=20, description="Raw policy/research text to analyze")
    document_id: Optional[str] = Field(default=None, description="Optional stable document id")
    source_filename: Optional[str] = Field(default=None, description="Optional source filename")
    persist_output: bool = Field(default=True, description="Persist JSON insight artifacts to outputs directory")


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
        if request.persist_output:
            project_root = Path(__file__).resolve().parents[3]
            storage = InsightOutputStorage(project_root=project_root, config=InsightStorageConfig())
            batch_path, per_doc_paths = storage.save(InsightBatch(items=[insight]))
            storage_info = {
                "batch_file": str(batch_path),
                "document_files": [str(p) for p in per_doc_paths],
            }

        return AnalyzeResponse(insight=insight, metrics=metrics, storage=storage_info)


_analyzer = _SingleDocumentAnalyzer()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_document(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze one document and return structured insights."""
    return _analyzer.analyze(request)
