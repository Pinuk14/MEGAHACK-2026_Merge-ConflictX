from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.schema import (
    ClauseInsight,
    ClauseType,
    DocumentInsight,
    ExecutiveSummary,
    ImpactLevel,
    InsightBatch,
    StakeholderImpact,
    StakeholderRole,
)
from backend.app.services import (
    ClauseDetectionService,
    LLMConfig,
    LLMService,
    SemanticSegmentationService,
    StakeholderExtractionService,
    SummarizationService,
    TopicClassificationService,
)
from backend.app.pipelines.output_storage import InsightOutputStorage, InsightStorageConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class InsightPipelineConfig:
    """Configuration for the insight orchestration pipeline."""

    project_root: Optional[Path] = None
    merged_input_path: Path = field(
        default_factory=lambda: Path(
            "infrastructure/storage/cleaned_documents/merged_multimodal.json"
        )
    )
    outputs_dir: Path = field(default_factory=lambda: Path("infrastructure/storage/outputs"))
    write_per_document_files: bool = True

    # LLM settings (reads OLLAMA_HOST / OLLAMA_MODEL from env by default)
    use_llm: bool = True
    use_llm_text_verification: bool = True
    llm_config: Optional[LLMConfig] = None


@dataclass
class InsightPipelineResult:
    """Execution result and output metadata for an insight pipeline run."""

    documents_processed: int
    insights_generated: int
    output_batch_file: str
    output_document_files: List[str]
    generated_at: str
    llm_enriched: bool = False
    llm_verified_documents: int = 0


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class InsightPipeline:
    """
    Orchestrates:
      semantic segmentation → clause detection → stakeholder extraction
      → topic classification → [LLM enrichment] → executive summarization

    LLM enrichment runs when Ollama is reachable and `use_llm=True`.
    If Ollama is offline the pipeline falls back to rule-based results silently.
    """

    def __init__(self, config: Optional[InsightPipelineConfig] = None) -> None:
        self.config = config or InsightPipelineConfig()
        self.project_root = (
            Path(self.config.project_root)
            if self.config.project_root
            else Path(__file__).resolve().parents[3]
        )

        # Rule-based services (always active)
        self.segmentation_service = SemanticSegmentationService()
        self.clause_service = ClauseDetectionService()
        self.stakeholder_service = StakeholderExtractionService()
        self.topic_service = TopicClassificationService()
        self.summary_service = SummarizationService()

        # LLM service — only assigned when Ollama is actually reachable
        self.llm_service: Optional[LLMService] = None
        if self.config.use_llm:
            cfg = self.config.llm_config or LLMConfig.from_env()
            _svc = LLMService(config=cfg)
            if _svc.is_available:
                self.llm_service = _svc
                logger.info(
                    f"InsightPipeline: LLM enrichment ENABLED "
                    f"(model={cfg.model} @ {cfg.host})"
                )
            else:
                logger.info(
                    "InsightPipeline: Ollama not reachable — "
                    "running in rule-based fallback mode"
                )

        self.output_storage = InsightOutputStorage(
            project_root=self.project_root,
            config=InsightStorageConfig(
                outputs_dir=self.config.outputs_dir,
                write_per_document_files=self.config.write_per_document_files,
            ),
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> InsightPipelineResult:
        """Run the pipeline end-to-end and persist structured outputs."""
        records = self._load_merged_records()
        insights: List[DocumentInsight] = []
        llm_was_used = False
        llm_verified_documents = 0

        for record in records:
            doc_id = str(record.get("id", "unknown"))
            source_filename = str(
                record.get("title") or record.get("source") or "unknown"
            )
            content = str(record.get("content", "")).strip()

            if not content:
                continue

            logger.info(f"Processing: {source_filename} ({doc_id})")

            analysis_text = content
            if self.llm_service is not None and self.config.use_llm_text_verification:
                verified_text = self._llm_verify_text(content)
                if verified_text:
                    analysis_text = verified_text
                    llm_verified_documents += 1
                    llm_was_used = True

            # ── Step 1: Rule-based analysis ───────────────────────────────
            segments = self.segmentation_service.segment_document(
                text=analysis_text,
                document_id=doc_id,
                source_filename=source_filename,
            )
            clauses = self.clause_service.detect_from_segments(segments)
            stakeholders = self.stakeholder_service.extract_from_segments(segments)
            topics = self.topic_service.classify_from_segments(segments)

            # ── Step 2: LLM enrichment (best-effort) ──────────────────────
            if self.llm_service is not None:
                clauses, clauses_from_llm = self._llm_enrich_clauses(segments, clauses)
                stakeholders, stakeholders_from_llm = self._llm_enrich_stakeholders(segments, stakeholders)
                executive_summary, summary_from_llm = self._llm_summarize(
                    analysis_text, clauses, stakeholders, topics
                )
                llm_was_used = llm_was_used or clauses_from_llm or stakeholders_from_llm or summary_from_llm
            else:
                executive_summary = self.summary_service.summarize(
                    text=analysis_text,
                    clauses=clauses,
                    stakeholders=stakeholders,
                    topics=topics,
                )

            insights.append(
                DocumentInsight(
                    document_id=doc_id,
                    source_filename=source_filename,
                    generated_at=datetime.now(timezone.utc),
                    executive_summary=executive_summary,
                    clauses=clauses,
                    stakeholders=stakeholders,
                    topics=topics,
                )
            )

        batch = InsightBatch(items=insights)
        batch_file, per_doc_files = self.output_storage.save(batch)

        return InsightPipelineResult(
            documents_processed=len(records),
            insights_generated=len(insights),
            output_batch_file=str(batch_file),
            output_document_files=[str(p) for p in per_doc_files],
            generated_at=datetime.now(timezone.utc).isoformat(),
            llm_enriched=llm_was_used,
            llm_verified_documents=llm_verified_documents,
        )

    def _llm_verify_text(self, content: str) -> Optional[str]:
        """Verify extracted text via Ollama and return verified text when available."""
        assert self.llm_service is not None
        try:
            result = self.llm_service.verify_extracted_text(content)
            verified_text = str(result.get("verified_text", "")).strip() if result else ""
            is_valid = bool(result.get("is_valid", True)) if result else False

            if is_valid and verified_text:
                return verified_text
            return None
        except Exception as exc:
            logger.error(f"LLM text verification failed: {exc}. Using original extracted text.")
            return None

    # ------------------------------------------------------------------
    # LLM enrichment helpers
    # ------------------------------------------------------------------

    def _llm_enrich_clauses(
        self,
        segments: List[Dict[str, Any]],
        rule_clauses: List[ClauseInsight],
    ) -> tuple[List[ClauseInsight], bool]:
        """Ask the LLM to clarify and enrich the rule-based clauses."""
        assert self.llm_service is not None
        try:
            raw = [c.model_dump() for c in rule_clauses]
            llm_result = self.llm_service.clarify_clauses(segments, raw)

            if not llm_result:
                return rule_clauses, False

            enriched: List[ClauseInsight] = []
            for idx, lc in enumerate(llm_result, start=1):
                try:
                    enriched.append(
                        ClauseInsight(
                            clause_id=str(lc.get("clause_id") or f"clause-{idx:04d}"),
                            clause_type=ClauseType(
                                str(lc.get("clause_type", "other")).lower()
                            ),
                            text=(str(lc.get("text", ""))[:650]) or "—",
                            rationale=str(lc.get("rationale", "")),
                            confidence=float(lc.get("confidence", 0.5)),
                        )
                    )
                except Exception as exc:
                    logger.warning(f"Skipping malformed LLM clause #{idx}: {exc}")

            return (enriched, True) if enriched else (rule_clauses, False)

        except Exception as exc:
            logger.error(f"LLM clause enrichment failed: {exc}. Using rule-based clauses.")
            return rule_clauses, False

    def _llm_enrich_stakeholders(
        self,
        segments: List[Dict[str, Any]],
        rule_stakeholders: List[StakeholderImpact],
    ) -> tuple[List[StakeholderImpact], bool]:
        """Ask the LLM to deepen stakeholder impact analysis."""
        assert self.llm_service is not None
        try:
            raw = [s.model_dump() for s in rule_stakeholders]
            llm_result = self.llm_service.analyse_stakeholder_impacts(segments, raw)

            if not llm_result:
                return rule_stakeholders, False

            # Preserve evidence from rule-based pass
            evidence_map: Dict[str, List[str]] = {
                s.stakeholder_name.lower(): list(s.evidence) for s in rule_stakeholders
            }

            enriched: List[StakeholderImpact] = []
            for ls in llm_result:
                try:
                    name = str(ls.get("stakeholder_name", "Unknown"))
                    enriched.append(
                        StakeholderImpact(
                            stakeholder_name=name,
                            role=StakeholderRole(str(ls.get("role", "other")).lower()),
                            impact_level=ImpactLevel(
                                str(ls.get("impact_level", "medium")).lower()
                            ),
                            impact_summary=str(ls.get("impact_summary", "")),
                            evidence=evidence_map.get(name.lower(), []),
                        )
                    )
                except Exception as exc:
                    logger.warning(f"Skipping malformed LLM stakeholder: {exc}")

            return (enriched, True) if enriched else (rule_stakeholders, False)

        except Exception as exc:
            logger.error(
                f"LLM stakeholder enrichment failed: {exc}. "
                "Using rule-based stakeholders."
            )
            return rule_stakeholders, False

    def _llm_summarize(
        self,
        content: str,
        clauses: List[ClauseInsight],
        stakeholders: List[StakeholderImpact],
        topics: Any,
    ) -> tuple[ExecutiveSummary, bool]:
        """Generate an LLM-powered executive summary with rule-based fallback."""
        assert self.llm_service is not None
        rule_summary = self.summary_service.summarize(
            text=content,
            clauses=clauses,
            stakeholders=stakeholders,
            topics=topics,
        )
        try:
            result = self.llm_service.summarize_document(
                text=content,
                rule_based_clauses=[c.model_dump() for c in clauses],
                rule_based_stakeholders=[s.model_dump() for s in stakeholders],
                rule_based_topics=[t.model_dump() for t in topics],
            )

            if result and result.get("short_summary"):
                llm_summary = ExecutiveSummary(
                    short_summary=str(result["short_summary"]),
                    key_points=[str(p) for p in result.get("key_points", [])],
                    recommended_actions=[
                        str(a) for a in result.get("recommended_actions", [])
                    ],
                )
                return self._merge_executive_summaries(llm_summary, rule_summary), True
        except Exception as exc:
            logger.error(f"LLM summarization failed: {exc}. Using rule-based summary.")

        # Fallback
        return rule_summary, False

    @staticmethod
    def _merge_executive_summaries(
        llm_summary: ExecutiveSummary,
        rule_summary: ExecutiveSummary,
    ) -> ExecutiveSummary:
        """Merge LLM and rule-based summaries to keep outputs both fluent and informative."""
        short_summary = llm_summary.short_summary.strip() or rule_summary.short_summary.strip()
        if len(short_summary) < len(rule_summary.short_summary.strip()) * 0.6:
            short_summary = rule_summary.short_summary.strip()

        key_points = InsightPipeline._dedupe_items(
            [*llm_summary.key_points, *rule_summary.key_points]
        )[:6]
        actions = InsightPipeline._dedupe_items(
            [*llm_summary.recommended_actions, *rule_summary.recommended_actions]
        )[:5]

        return ExecutiveSummary(
            short_summary=short_summary,
            key_points=key_points,
            recommended_actions=actions,
        )

    @staticmethod
    def _dedupe_items(items: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for item in items:
            text = str(item).strip()
            key = " ".join(text.lower().split())
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(text)
        return out

    # ------------------------------------------------------------------
    # Data loader
    # ------------------------------------------------------------------

    def _load_merged_records(self) -> List[Dict[str, Any]]:
        merged_path = self.project_root / self.config.merged_input_path
        if not merged_path.exists():
            raise FileNotFoundError(f"Merged input not found: {merged_path}")

        with open(merged_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Merged input JSON must be a list of records.")

        return data

