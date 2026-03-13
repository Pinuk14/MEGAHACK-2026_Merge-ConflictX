"""Report download routes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import json
import time
from pathlib import Path
from backend.api.job_manager import get_job_manager
from backend.api.models import JobStatus

router = APIRouter(prefix="/jobs", tags=["report"])
job_manager = get_job_manager()


@router.get("/{job_id}/report")
def download_report(job_id: str, format: str = "json"):
    """
    Download job report.
    Query params: format=json|pdf
    
    Returns:
    - format=json: application/json
    - format=pdf: application/pdf with attachment
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found"
        )
    
    if job.status != JobStatus.DONE:
        raise HTTPException(
            status_code=400,
            detail=f"Job is {job.status}, cannot download report yet"
        )
    
    # Format validation
    if format not in ("json", "pdf"):
        raise HTTPException(
            status_code=400,
            detail="format must be 'json' or 'pdf'"
        )
    
    # Generate or return reports
    if format == "json":
        # Return JSON report
        if job.report_json:
            return JSONResponse(content=job.report_json)
        
        # Generate default report from cached data
        report = {
            "job_id": job_id,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "elapsed_seconds": int((job.completed_at - job.created_at).total_seconds()) if job.completed_at else 0,
            "status": job.status.value,
            "summary": {
                "total_tokens": job.stats.get("tokens_processed", 0),
                "accuracy": job.stats.get("accuracy_pct", 0),
            },
            "structure": job.structure,
            "topics": job.topics,
            "clauses": job.clauses,
            "recommendations": job.recommendations,
            "insights": job.insights,
            "stakeholders": job.stakeholders,
            "risk": job.risk,
        }
        
        return JSONResponse(content=report)
    
    elif format == "pdf":
        # Return PDF report (or generate placeholder)
        if job.report_pdf:
            return FileResponse(
                path=None,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=report_{job_id}.pdf"
                }
            )
        
        # In production, generate actual PDF here
        # For now, return error
        raise HTTPException(
            status_code=501,
            detail="PDF generation not yet implemented"
        )
