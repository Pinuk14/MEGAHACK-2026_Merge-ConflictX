"""Upload and job kickoff routes."""
from fastapi import APIRouter, File, UploadFile, HTTPException
from pathlib import Path
import json
from typing import List
from backend.api.models import UploadResponse, UploadBatchResponse, RunRequest, RunResponse
from backend.api.job_manager import get_job_manager

router = APIRouter(tags=["upload"])
job_manager = get_job_manager()

SUPPORTED_EXTENSIONS = {
    ".txt",
    ".pdf",
    ".docx",
    ".xml",
    ".json",
    ".wav",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tiff",
    ".webp",
}


def _validate_supported_file(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {allowed}",
        )


def _append_uploaded_manifest(file_id: str, filename: str, size_bytes: int, content: str) -> None:
    """Append extracted uploaded content to orchestration manifest."""
    project_root = Path(__file__).resolve().parents[3]
    manifest_path = project_root / "infrastructure" / "storage" / "uploads" / "uploaded_documents.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    existing = loaded
        except Exception:
            existing = []

    # Keep latest copy for same file_id if re-uploaded.
    existing = [r for r in existing if str(r.get("id")) != str(file_id)]
    existing.append(
        {
            "id": file_id,
            "source": "upload",
            "title": filename,
            "content": content,
            "metadata": {
                "char_count": len(content),
                "size_bytes": size_bytes,
                "file_path": f"uploads/{file_id}_{filename}",
            },
        }
    )

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    """
    Upload a PDF or TXT file.
    Returns { file_id, filename, size_bytes }
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Read file content
    content = await file.read()
    
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    
    _validate_supported_file(file.filename)
    
    # Save file to storage and get file_id
    file_id = job_manager.save_uploaded_file(file.filename, content)

    # Prepare upload manifest record for orchestration upload mode.
    extracted_text = job_manager.get_uploaded_file(file_id) or ""
    _append_uploaded_manifest(
        file_id=file_id,
        filename=file.filename,
        size_bytes=len(content),
        content=extracted_text,
    )
    
    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        size_bytes=len(content),
    )


@router.post("/upload-multiple", response_model=UploadBatchResponse)
async def upload_multiple_files(files: List[UploadFile] = File(...)) -> UploadBatchResponse:
    """
    Upload multiple files in one request.
    Returns { files: [{ file_id, filename, size_bytes }] }
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploaded: List[UploadResponse] = []
    for file in files:
        if not file:
            continue

        content = await file.read()
        if not content:
            continue

        _validate_supported_file(file.filename)

        file_id = job_manager.save_uploaded_file(file.filename, content)
        extracted_text = job_manager.get_uploaded_file(file_id) or ""
        _append_uploaded_manifest(
            file_id=file_id,
            filename=file.filename,
            size_bytes=len(content),
            content=extracted_text,
        )
        uploaded.append(
            UploadResponse(
                file_id=file_id,
                filename=file.filename,
                size_bytes=len(content),
            )
        )

    if not uploaded:
        raise HTTPException(status_code=400, detail="All uploaded files were empty or invalid")

    return UploadBatchResponse(files=uploaded)


@router.post("/run", response_model=RunResponse)
async def run_job(request: RunRequest) -> RunResponse:
    """
    Kickoff a new analysis job.
    Body: { text?: string, file_id?: string }
    Returns { job_id, status: "queued" }
    """
    
    # Validate input
    file_ids = [fid for fid in (request.file_ids or []) if fid]
    if request.file_id:
        file_ids.insert(0, request.file_id)

    if not request.text and not file_ids:
        raise HTTPException(
            status_code=400,
            detail="Either 'text' or one of 'file_id'/'file_ids' must be provided"
        )
    
    # If file_id, load the text
    input_text = (request.text or "").strip()
    if file_ids:
        extracted_blocks: List[str] = []
        missing: List[str] = []
        for fid in file_ids:
            file_content = job_manager.get_uploaded_file(fid)
            if file_content is None:
                missing.append(fid)
                continue
            if file_content.strip():
                extracted_blocks.append(file_content.strip())

        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"File(s) not found: {', '.join(missing)}",
            )

        if not extracted_blocks and not input_text:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file(s) had no extractable text. Please upload supported files with readable content.",
            )

        combined_file_text = "\n\n".join(extracted_blocks)
        input_text = "\n\n".join([p for p in [input_text, combined_file_text] if p]).strip()
    
    # Validate minimum length
    if len(input_text.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Text must be at least 10 characters long"
        )
    
    # Create job
    job_id = job_manager.create_job(
        input_text=input_text,
        file_id=file_ids[0] if file_ids else request.file_id
    )
    
    # TODO: Trigger background pipeline processing
    
    return RunResponse(
        job_id=job_id,
        status="queued"
    )
