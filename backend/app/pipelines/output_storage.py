from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import List, Tuple

from backend.app.schema import InsightBatch


@dataclass
class InsightStorageConfig:
    """Configuration for persisting insight outputs."""

    outputs_dir: Path = Path("infrastructure/storage/outputs")
    write_per_document_files: bool = True


class InsightOutputStorage:
    """Persists insight analysis JSON artifacts under outputs/insights/."""

    def __init__(self, project_root: Path, config: InsightStorageConfig) -> None:
        self.project_root = project_root
        self.config = config

    def save(self, batch: InsightBatch) -> Tuple[Path, List[Path]]:
        output_root = self.project_root / self.config.outputs_dir
        insights_dir = output_root / "insights"
        insights_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        batch_path = insights_dir / f"insight_batch_{timestamp}.json"

        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump(batch.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

        per_doc_paths: List[Path] = []
        if self.config.write_per_document_files:
            for item in batch.items:
                safe_doc = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in item.document_id)
                item_path = insights_dir / f"insight_{safe_doc}.json"
                with open(item_path, "w", encoding="utf-8") as f:
                    json.dump(item.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
                per_doc_paths.append(item_path)

        return batch_path, per_doc_paths
