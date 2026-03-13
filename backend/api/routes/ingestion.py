from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import json

from fastapi import APIRouter, File, UploadFile, HTTPException
from backend.pipelines.orchestration import FinalPipeline, FinalPipelineConfig

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def _project_root() -> Path:
	return Path(__file__).resolve().parents[3]


@router.post("/upload-texts")
async def upload_text_documents(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
	"""
	Upload text files from website and persist a normalized upload manifest.
	"""
	if not files:
		raise HTTPException(status_code=400, detail="No files uploaded")

	root = _project_root()
	raw_txt_dir = root / "infrastructure" / "storage" / "raw_documents" / "txts"
	uploads_dir = root / "infrastructure" / "storage" / "uploads"
	manifest_path = uploads_dir / "uploaded_documents.json"

	raw_txt_dir.mkdir(parents=True, exist_ok=True)
	uploads_dir.mkdir(parents=True, exist_ok=True)

	records: List[Dict[str, Any]] = []

	for i, file in enumerate(files, start=1):
		content_bytes = await file.read()
		content = content_bytes.decode("utf-8", errors="ignore").strip()
		if not content:
			continue

		target_file = raw_txt_dir / file.filename
		target_file.write_text(content, encoding="utf-8")

		records.append(
			{
				"id": i,
				"source": "upload",
				"title": Path(file.filename).stem,
				"content": content,
				"metadata": {
					"char_count": len(content),
					"file_path": str(target_file.resolve()),
				},
			}
		)

	with open(manifest_path, "w", encoding="utf-8") as f:
		json.dump(records, f, indent=2, ensure_ascii=False)

	return {
		"uploaded": len(records),
		"manifest": str(manifest_path),
	}


@router.post("/upload-and-run")
async def upload_and_run_pipeline(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
	"""Upload files, write manifest, then run final pipeline in production mode."""
	upload_result = await upload_text_documents(files)

	result = FinalPipeline(
		FinalPipelineConfig(
			use_local_test_folder=False,
		)
	).run()

	return {
		"upload": upload_result,
		"pipeline_success": result.success,
		"stages_completed": result.stages_completed,
		"stages_failed": result.stages_failed,
		"errors": result.errors,
		"output_files": result.output_files,
	}
