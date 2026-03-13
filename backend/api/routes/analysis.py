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
    LLMConfig,
    LLMService,
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
    use_llm_verification: bool = Field(default=True, description="Verify extracted text with Ollama before analysis")
    use_llm_enrichment: bool = Field(default=True, description="Use Ollama to enrich clauses, stakeholders, and summary")


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
        llm = LLMService(config=LLMConfig.from_env())
        self.llm_service: Optional[LLMService] = llm if llm.is_available else None

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Request text is empty")

        document_id = request.document_id or f"api-{uuid4().hex[:12]}"

        analysis_text = text
        llm_text_verified = False
        llm_clause_enriched = False
        llm_stakeholder_enriched = False
        llm_summary_enriched = False

        if request.use_llm_verification and self.llm_service is not None:
            try:
                verified = self.llm_service.verify_extracted_text(text)
                candidate = str(verified.get("verified_text", "")).strip() if verified else ""
                is_valid = bool(verified.get("is_valid", True)) if verified else False
                if is_valid and candidate:
                    analysis_text = candidate
                    llm_text_verified = True
            except Exception:
                pass

        segments = self.segmentation_service.segment_document(
            text=analysis_text,
            document_id=document_id,
            source_filename=request.source_filename,
        )
        clauses = self.clause_service.detect_from_segments(segments)
        stakeholders = self.stakeholder_service.extract_from_segments(segments)
        topics = self.topic_service.classify_from_segments(segments)

        if request.use_llm_enrichment and self.llm_service is not None:
            clauses, llm_clause_enriched = self._llm_enrich_clauses(segments, clauses)
            stakeholders, llm_stakeholder_enriched = self._llm_enrich_stakeholders(segments, stakeholders)
            executive_summary, llm_summary_enriched = self._llm_summarize(
                analysis_text,
                clauses,
                stakeholders,
                topics,
            )
        else:
            executive_summary = self.summary_service.summarize(
                text=analysis_text,
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
            "llm_available": self.llm_service is not None,
            "llm_text_verified": llm_text_verified,
            "llm_clause_enriched": llm_clause_enriched,
            "llm_stakeholder_enriched": llm_stakeholder_enriched,
            "llm_summary_enriched": llm_summary_enriched,
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

    def _llm_enrich_clauses(self, segments: Any, rule_clauses: Any):
        assert self.llm_service is not None
        try:
            raw = [c.model_dump() for c in rule_clauses]
            llm_result = self.llm_service.clarify_clauses(segments, raw)
            if not llm_result:
                return rule_clauses, False

            enriched = []
            for idx, lc in enumerate(llm_result, start=1):
                try:
                    from backend.app.schema import ClauseInsight, ClauseType

                    enriched.append(
                        ClauseInsight(
                            clause_id=str(lc.get("clause_id") or f"clause-{idx:04d}"),
                            clause_type=ClauseType(str(lc.get("clause_type", "other")).lower()),
                            text=(str(lc.get("text", ""))[:650]) or "—",
                            rationale=str(lc.get("rationale", "")),
                            confidence=float(lc.get("confidence", 0.5)),
                        )
                    )
                except Exception:
                    continue

            return (enriched, True) if enriched else (rule_clauses, False)
        except Exception:
            return rule_clauses, False

    def _llm_enrich_stakeholders(self, segments: Any, rule_stakeholders: Any):
        assert self.llm_service is not None
        try:
            raw = [s.model_dump() for s in rule_stakeholders]
            llm_result = self.llm_service.analyse_stakeholder_impacts(segments, raw)
            if not llm_result:
                return rule_stakeholders, False

            evidence_map = {s.stakeholder_name.lower(): list(s.evidence) for s in rule_stakeholders}
            enriched = []
            for ls in llm_result:
                try:
                    from backend.app.schema import ImpactLevel, StakeholderImpact, StakeholderRole

                    name = str(ls.get("stakeholder_name", "Unknown"))
                    enriched.append(
                        StakeholderImpact(
                            stakeholder_name=name,
                            role=StakeholderRole(str(ls.get("role", "other")).lower()),
                            impact_level=ImpactLevel(str(ls.get("impact_level", "medium")).lower()),
                            impact_summary=str(ls.get("impact_summary", "")),
                            evidence=evidence_map.get(name.lower(), []),
                        )
                    )
                except Exception:
                    continue

            return (enriched, True) if enriched else (rule_stakeholders, False)
        except Exception:
            return rule_stakeholders, False

    def _llm_summarize(self, content: str, clauses: Any, stakeholders: Any, topics: Any):
        assert self.llm_service is not None
        try:
            result = self.llm_service.summarize_document(
                text=content,
                rule_based_clauses=[c.model_dump() for c in clauses],
                rule_based_stakeholders=[s.model_dump() for s in stakeholders],
                rule_based_topics=[t.model_dump() for t in topics],
            )
            if result and result.get("short_summary"):
                from backend.app.schema import ExecutiveSummary

                return ExecutiveSummary(
                    short_summary=str(result["short_summary"]),
                    key_points=[str(p) for p in result.get("key_points", [])],
                    recommended_actions=[str(a) for a in result.get("recommended_actions", [])],
                ), True
        except Exception:
            pass

        return self.summary_service.summarize(
            text=content,
            clauses=clauses,
            stakeholders=stakeholders,
            topics=topics,
        ), False


_analyzer = _SingleDocumentAnalyzer()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_document(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze one document and return structured insights."""
    return _analyzer.analyze(request)
