"""
Post-Cleaning Pipeline Module
=============================

Orchestrates the pipeline AFTER cleaning:
1. Merge cleaned multimodal outputs
2. Chunking for embeddings
3. Feature Extraction (TF-IDF + Embeddings)
4. Vector Store (Optional)

This module does NOT modify ingestion or validation modules.
"""

from __future__ import annotations

from pathlib import Path
import json
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.preprocessing.chunker import chunk_and_save, ChunkingConfig
from backend.models.tfidf_features import process_chunks_file as extract_tfidf
from backend.models.embedding_features import process_chunks_file as extract_embeddings


class PipelineStage(Enum):
    """Enumeration of pipeline stages."""
    CLEANING = "cleaning"
    MERGE = "merge"
    CHUNKING = "chunking"
    TFIDF_EXTRACTION = "tfidf_extraction"
    EMBEDDING_EXTRACTION = "embedding_extraction"
    VECTOR_STORE = "vector_store"


@dataclass
class PipelineConfig:
    """
    Configuration for the post-cleaning pipeline.
    """
    raw_dir: Path = field(default_factory=lambda: Path("infrastructure/storage/raw_documents"))
    processed_dir: Path = field(default_factory=lambda: Path("infrastructure/storage/cleaned_documents"))
    features_dir: Path = field(default_factory=lambda: Path("infrastructure/storage/embeddings"))
    vector_store_dir: Path = field(default_factory=lambda: Path("infrastructure/storage/vector_store"))

    skip_cleaning: bool = False
    skip_merge: bool = False
    skip_chunking: bool = False
    skip_tfidf: bool = False
    skip_embeddings: bool = False
    skip_vector_store: bool = True  # default True until FAISS adapter is ready

    chunk_size: int = 200  # Reduced chunk size for smaller documents
    chunk_overlap: int = 20  # Reduced overlap for better chunking

    embedding_model: str = "all-MiniLM-L6-v2"
    tfidf_max_features: int = 5000


@dataclass
class PipelineResult:
    """Results from pipeline execution."""
    success: bool
    stages_completed: List[str]
    stages_failed: List[str]
    output_files: Dict[str, str]
    statistics: Dict[str, Any]
    duration_seconds: float
    errors: List[str]


class PostCleaningPipeline:
    """
    Orchestrates the complete post-cleaning data pipeline.
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        project_root: Optional[Path] = None
    ) -> None:
        self.config = config or PipelineConfig()
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]

        # Resolve paths relative to project root
        self.raw_dir = self.project_root / self.config.raw_dir
        self.processed_dir = self.project_root / self.config.processed_dir
        self.features_dir = self.project_root / self.config.features_dir
        self.vector_store_dir = self.project_root / self.config.vector_store_dir

        self.outputs = {
            "merged": self.processed_dir / "merged_multimodal.json",
            "chunks": self.processed_dir / "chunks.json",
            "tfidf_dir": self.features_dir / "tfidf",
            "embeddings_dir": self.features_dir / "embeddings",
            "vector_store": self.vector_store_dir,
        }

        self._stages_completed: List[str] = []
        self._stages_failed: List[str] = []
        self._errors: List[str] = []
        self._statistics: Dict[str, Any] = {}

    def run_stage(
        self,
        stage: PipelineStage,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> bool:
        logger.info(f"\n{'='*50}")
        logger.info(f"STAGE: {stage.value}")
        logger.info(f"{'='*50}")

        try:
            result = func(*args, **kwargs)
            self._stages_completed.append(stage.value)

            if isinstance(result, dict):
                self._statistics[stage.value] = result

            logger.info(f"✅ Stage '{stage.value}' completed successfully")
            return True
        except Exception as e:
            error_msg = f"Stage '{stage.value}' failed: {str(e)}"
            self._errors.append(error_msg)
            self._stages_failed.append(stage.value)
            logger.error(f"❌ {error_msg}")
            return False

    def stage_cleaning(self) -> Dict[str, Any]:
        """Execute cleaning stage for all data types."""
        stats = {
            "pdfs_cleaned": 0,
            "txts_cleaned": 0,
            "xmls_cleaned": 0,
            "wavs_cleaned": 0,
        }

        self.processed_dir.mkdir(parents=True, exist_ok=True)

        try:
            from backend.cleaning.pdf_cleaner import clean_pdf_directory
            pdf_dir = self.raw_dir / "pdfs"
            pdf_output = self.processed_dir / "cleaned_pdfs.json"
            if pdf_dir.exists() and any(pdf_dir.glob("*.pdf")):
                clean_pdf_directory(str(pdf_dir), str(pdf_output))
                if pdf_output.exists():
                    with open(pdf_output, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    stats["pdfs_cleaned"] = len(records)
        except Exception as e:
            logger.warning(f"PDF cleaning skipped or failed: {e}")

        try:
            from backend.cleaning.text_cleaner import clean_txt_directory
            txt_dir = self.raw_dir / "txts"
            txt_output = self.processed_dir / "cleaned_txts.json"
            if txt_dir.exists() and any(txt_dir.glob("*.txt")):
                clean_txt_directory(str(txt_dir), str(txt_output))
                if txt_output.exists():
                    with open(txt_output, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    stats["txts_cleaned"] = len(records)
        except Exception as e:
            logger.warning(f"TXT cleaning skipped or failed: {e}")

        try:
            from backend.cleaning.xml_cleaner import clean_xml_directory
            xml_dir = self.raw_dir / "xmls"
            xml_output = self.processed_dir / "cleaned_xmls.json"
            if xml_dir.exists() and any(xml_dir.glob("*.xml")):
                clean_xml_directory(str(xml_dir), str(xml_output))
                if xml_output.exists():
                    with open(xml_output, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    stats["xmls_cleaned"] = len(records)
        except Exception as e:
            logger.warning(f"XML cleaning skipped or failed: {e}")

        try:
            from backend.cleaning.wav_cleaner import clean_wav_directory
            wav_dir = self.raw_dir / "wavs"
            wav_output = self.processed_dir / "cleaned_wavs.json"
            if wav_dir.exists() and any(wav_dir.glob("*.wav")):
                clean_wav_directory(str(wav_dir), str(wav_output))
                if wav_output.exists():
                    with open(wav_output, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    stats["wavs_cleaned"] = len(records)
        except Exception as e:
            logger.warning(f"WAV cleaning skipped or failed: {e}")

        return stats

    def stage_merge(self) -> Dict[str, Any]:
        """Merge cleaned outputs into a single JSON list."""
        cleaned_files = {
            "pdf": self.processed_dir / "cleaned_pdfs.json",
            "txt": self.processed_dir / "cleaned_txts.json",
            "xml": self.processed_dir / "cleaned_xmls.json",
            "audio": self.processed_dir / "cleaned_wavs.json",
        }

        merged: List[Dict[str, Any]] = []

        for source, path in cleaned_files.items():
            if not path.exists():
                continue
            with open(path, "r", encoding="utf-8") as f:
                records = json.load(f)
            for r in records:
                if "source" not in r:
                    r["source"] = source
                merged.append(r)

        if not merged:
            raise FileNotFoundError("No cleaned files found to merge.")

        self.outputs["merged"].parent.mkdir(parents=True, exist_ok=True)
        with open(self.outputs["merged"], "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)

        return {"records_merged": len(merged)}

    def stage_chunking(self) -> Dict[str, Any]:
        """Execute chunking stage."""
        if not self.outputs["merged"].exists():
            raise FileNotFoundError(f"Merged file not found: {self.outputs['merged']}")

        chunk_config = ChunkingConfig(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )

        _, stats = chunk_and_save(
            input_path=self.outputs["merged"],
            output_path=self.outputs["chunks"],
            config=chunk_config,
        )

        return stats

    def stage_tfidf(self) -> Dict[str, Any]:
        """Execute TF-IDF extraction stage."""
        from backend.models.tfidf_features import TFIDFConfig

        config = TFIDFConfig(max_features=self.config.tfidf_max_features)
        results = extract_tfidf(
            input_path=self.outputs["chunks"],
            output_dir=self.outputs["tfidf_dir"],
            config=config,
        )
        return results

    def stage_embeddings(self) -> Dict[str, Any]:
        """Execute embedding extraction stage."""
        from backend.models.embedding_features import EmbeddingConfig

        config = EmbeddingConfig(model_name=self.config.embedding_model)
        results = extract_embeddings(
            input_path=self.outputs["chunks"],
            output_dir=self.outputs["embeddings_dir"],
            config=config,
        )
        return results

    def stage_vector_store(self) -> Dict[str, Any]:
        """Execute vector store building stage."""
        try:
            from backend.vector_store.faiss_integration import build_vector_store_from_embeddings
        except Exception as e:
            raise ImportError("Vector store adapter not available") from e

        store = build_vector_store_from_embeddings(
            embeddings_dir=self.outputs["embeddings_dir"],
            chunks_path=self.outputs["chunks"],
            output_dir=self.outputs["vector_store"],
        )
        return {"vectors_indexed": getattr(store, "size", None)}

    def run(self, start_from: Optional[PipelineStage] = None) -> PipelineResult:
        """Run the pipeline."""
        start_time = time.time()

        stages = [
            (PipelineStage.CLEANING, self.stage_cleaning, not self.config.skip_cleaning),
            (PipelineStage.MERGE, self.stage_merge, not self.config.skip_merge),
            (PipelineStage.CHUNKING, self.stage_chunking, not self.config.skip_chunking),
            (PipelineStage.TFIDF_EXTRACTION, self.stage_tfidf, not self.config.skip_tfidf),
            (PipelineStage.EMBEDDING_EXTRACTION, self.stage_embeddings, not self.config.skip_embeddings),
            (PipelineStage.VECTOR_STORE, self.stage_vector_store, not self.config.skip_vector_store),
        ]

        start_idx = 0
        if start_from:
            for i, (stage, _, _) in enumerate(stages):
                if stage == start_from:
                    start_idx = i
                    break

        for stage, func, should_run in stages[start_idx:]:
            if not should_run:
                logger.info(f"⏭️ Skipping stage: {stage.value}")
                continue

            success = self.run_stage(stage, func)
            if not success and stage in [PipelineStage.CLEANING, PipelineStage.MERGE, PipelineStage.CHUNKING]:
                logger.error("Critical stage failed. Stopping pipeline.")
                break

        duration = time.time() - start_time

        output_files = {
            k: str(v) for k, v in self.outputs.items()
            if (v.exists() if isinstance(v, Path) else Path(v).exists())
        }

        return PipelineResult(
            success=len(self._stages_failed) == 0,
            stages_completed=self._stages_completed,
            stages_failed=self._stages_failed,
            output_files=output_files,
            statistics=self._statistics,
            duration_seconds=round(duration, 2),
            errors=self._errors,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run post-cleaning pipeline")
    parser.add_argument("--skip-cleaning", action="store_true")
    parser.add_argument("--skip-merge", action="store_true")
    parser.add_argument("--skip-chunking", action="store_true")
    parser.add_argument("--skip-tfidf", action="store_true")
    parser.add_argument("--skip-embeddings", action="store_true")
    parser.add_argument("--skip-vector-store", action="store_true")

    args = parser.parse_args()

    config = PipelineConfig(
        skip_cleaning=args.skip_cleaning,
        skip_merge=args.skip_merge,
        skip_chunking=args.skip_chunking,
        skip_tfidf=args.skip_tfidf,
        skip_embeddings=args.skip_embeddings,
        skip_vector_store=args.skip_vector_store,
    )

    pipeline = PostCleaningPipeline(config=config)
    result = pipeline.run()

    print(f"\n✅ Pipeline {'completed successfully' if result.success else 'completed with errors'}")
    print(f"⏱️ Duration: {result.duration_seconds}s")
    if result.errors:
        print("Errors:")
        for e in result.errors:
            print(f" - {e}")
