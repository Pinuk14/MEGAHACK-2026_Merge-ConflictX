from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.schema import DocumentInsight, InsightBatch
from backend.app.services import (
    ClauseDetectionService,
    SemanticSegmentationService,
    StakeholderExtractionService,
    SummarizationService,
    TopicClassificationService,
)
from backend.app.pipelines.output_storage import InsightOutputStorage, InsightStorageConfig


@dataclass
class InsightPipelineConfig:
    """Configuration for insight orchestration pipeline."""

    project_root: Optional[Path] = None
    merged_input_path: Path = field(
        default_factory=lambda: Path("infrastructure/storage/cleaned_documents/merged_multimodal.json")
    )
    outputs_dir: Path = field(default_factory=lambda: Path("infrastructure/storage/outputs"))
    write_per_document_files: bool = True


@dataclass
class InsightPipelineResult:
    """Execution result and output metadata for insight pipeline run."""

    documents_processed: int
    insights_generated: int
    output_batch_file: str
    output_document_files: List[str]
    generated_at: str


class InsightPipeline:
    """
    Orchestrates semantic segmentation -> clause detection -> stakeholder extraction
    -> topic classification -> executive summarization.

    Step 7 scope: orchestration only.
    """

    def __init__(self, config: Optional[InsightPipelineConfig] = None) -> None:
        self.config = config or InsightPipelineConfig()
        self.project_root = Path(self.config.project_root) if self.config.project_root else Path(__file__).resolve().parents[3]

        self.segmentation_service = SemanticSegmentationService()
        self.clause_service = ClauseDetectionService()
        self.stakeholder_service = StakeholderExtractionService()
        self.topic_service = TopicClassificationService()
        self.summary_service = SummarizationService()
        self.output_storage = InsightOutputStorage(
            project_root=self.project_root,
            config=InsightStorageConfig(
                outputs_dir=self.config.outputs_dir,
                write_per_document_files=self.config.write_per_document_files,
            ),
        )

    def run(self) -> InsightPipelineResult:
        """Run pipeline end-to-end and persist structured outputs."""
        records = self._load_merged_records()
        insights: List[DocumentInsight] = []

        for record in records:
            doc_id = str(record.get("id", "unknown"))
            source_filename = str(record.get("title") or record.get("source") or "unknown")
            content = str(record.get("content", "")).strip()

            if not content:
                continue

            segments = self.segmentation_service.segment_record(record)
            clauses = self.clause_service.detect_from_segments(segments)
            stakeholders = self.stakeholder_service.extract_from_segments(segments)
            topics = self.topic_service.classify_from_segments(segments)
            executive_summary = self.summary_service.summarize(
                text=content,
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
        )

    def _load_merged_records(self) -> List[Dict[str, Any]]:
        merged_path = self.project_root / self.config.merged_input_path
        if not merged_path.exists():
            raise FileNotFoundError(f"Merged input not found: {merged_path}")

        with open(merged_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Merged input JSON must be a list of records.")

        return data

