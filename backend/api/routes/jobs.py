"""Job lifecycle management routes."""
from fastapi import APIRouter, HTTPException
from backend.api.models import JobDetailResponse, JobStatus
from backend.api.job_manager import get_job_manager
from datetime import datetime

router = APIRouter(prefix="/jobs", tags=["jobs"])
job_manager = get_job_manager()


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job_status(job_id: str) -> JobDetailResponse:
    """
    Get job status and details.
    Returns { job_id, status, current_step, elapsed_seconds, created_at, completed_at }
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found"
        )
    
    # Calculate elapsed seconds
    if job.completed_at:
        elapsed = int((job.completed_at - job.created_at).total_seconds())
    else:
        elapsed = int((datetime.now() - job.created_at).total_seconds())
    
    return JobDetailResponse(
        job_id=job.job_id,
        status=job.status,
        current_step=job.current_step,
        elapsed_seconds=elapsed,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.delete("/{job_id}")
def abort_job(job_id: str) -> dict:
    """
    Abort a running job.
    Returns { status: "aborted" }
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found"
        )
    
    if job.status == JobStatus.DONE or job.status == JobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail="Cannot abort a completed job"
        )
    
    job_manager.abort_job(job_id)
    
    return {"status": "aborted", "job_id": job_id}
