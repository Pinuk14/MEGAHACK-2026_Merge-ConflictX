"""Upload and job kickoff routes."""
from fastapi import APIRouter, File, UploadFile, HTTPException
from pathlib import Path
import json
from backend.api.models import UploadResponse, RunRequest, RunResponse
from backend.api.job_manager import get_job_manager

router = APIRouter(tags=["upload"])
job_manager = get_job_manager()


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
    
    # Validate file type
    if not (file.filename.endswith(".txt") or file.filename.endswith(".pdf")):
        raise HTTPException(
            status_code=400,
            detail="Only .txt and .pdf files are supported"
        )
    
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


@router.post("/run", response_model=RunResponse)
async def run_job(request: RunRequest) -> RunResponse:
    """
    Kickoff a new analysis job.
    Body: { text?: string, file_id?: string }
    Returns { job_id, status: "queued" }
    """
    
    # Validate input
    if not request.text and not request.file_id:
        raise HTTPException(
            status_code=400,
            detail="Either 'text' or 'file_id' must be provided"
        )
    
    # If file_id, load the text
    input_text = request.text
    if request.file_id:
        file_content = job_manager.get_uploaded_file(request.file_id)
        if file_content is None:
            raise HTTPException(
                status_code=404,
                detail=f"File with id '{request.file_id}' not found"
            )
        if not file_content.strip():
            raise HTTPException(
                status_code=400,
                detail="Uploaded file has no extractable text. Please upload a text-based PDF/TXT."
            )
        input_text = file_content
    
    # Validate minimum length
    if len(input_text.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Text must be at least 10 characters long"
        )
    
    # Create job
    job_id = job_manager.create_job(
        input_text=input_text,
        file_id=request.file_id
    )
    
    # TODO: Trigger background pipeline processing
    
    return RunResponse(
        job_id=job_id,
        status="queued"
    )
