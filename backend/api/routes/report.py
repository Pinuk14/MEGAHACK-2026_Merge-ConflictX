"""Report download routes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import json
from pathlib import Path
from backend.api.job_manager import get_job_manager
from backend.api.models import JobStatus

router = APIRouter(prefix="/jobs", tags=["report"])
job_manager = get_job_manager()
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_persisted_insight_doc(job_id: str) -> dict | None:
    """Load per-job persisted insight artifact if available."""
    insight_path = PROJECT_ROOT / "infrastructure" / "storage" / "outputs" / "insights" / f"insight_{job_id}.json"
    if not insight_path.exists():
        return None

    try:
        with open(insight_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        return None


def _derive_insights_from_doc(doc: dict) -> list[dict]:
    """Convert persisted summary into lightweight insight rows used by UI/report."""
    summary = doc.get("executive_summary") if isinstance(doc, dict) else None
    if not isinstance(summary, dict):
        return []

    points: list[str] = []
    short_summary = str(summary.get("short_summary") or "").strip()
    if short_summary:
        points.append(short_summary)

    key_points = summary.get("key_points")
    if isinstance(key_points, list):
        points.extend(str(p).strip() for p in key_points if str(p).strip())

    palette = ["#10b981", "#f59e0b", "#ef4444", "#06b6d4"]
    return [
        {
            "id": f"i{idx}",
            "conf": f"{max(72, 96 - (idx * 6))}%",
            "text": point,
            "color": palette[(idx - 1) % len(palette)],
            "shown_after_step": "summarize" if idx <= 2 else "stakeholder",
        }
        for idx, point in enumerate(points[:6], start=1)
    ]


def _derive_clauses_from_doc(doc: dict) -> list[dict]:
    """Convert persisted clause artifacts into report/frontend clause rows."""
    persisted_clauses = doc.get("clauses") if isinstance(doc, dict) else None
    if not isinstance(persisted_clauses, list):
        return []

    clause_colors = {
        "obligation": "#ef4444",
        "compliance": "#f97316",
        "deadline": "#eab308",
        "penalty": "#ef4444",
        "governance": "#ec5b13",
        "funding": "#facc15",
    }

    output: list[dict] = []
    for item in persisted_clauses[:12]:
        if not isinstance(item, dict):
            continue
        clause_type = str(item.get("clause_type") or "other").strip().lower()
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        output.append(
            {
                "label": clause_type.upper(),
                "val": text[:72] + ("..." if len(text) > 72 else ""),
                "color": clause_colors.get(clause_type, "#ec5b13"),
            }
        )
    return output


def _derive_recommendations_from_doc(doc: dict) -> list[dict]:
    """Convert persisted summary recommended actions into report recommendation rows."""
    summary = doc.get("executive_summary") if isinstance(doc, dict) else None
    if not isinstance(summary, dict):
        return []

    actions = summary.get("recommended_actions")
    if not isinstance(actions, list):
        return []

    priority_cycle = ["IMMEDIATE", "STRATEGIC", "LONG-TERM"]
    output: list[dict] = []
    for idx, action in enumerate(actions[:6]):
        text = str(action).strip()
        if not text:
            continue
        output.append(
            {
                "priority": priority_cycle[idx % len(priority_cycle)],
                "text": text,
            }
        )
    return output


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
        persisted_insight_doc = _load_persisted_insight_doc(job_id)
        report_insights = job.insights
        report_clauses = job.clauses
        report_recommendations = job.recommendations
        if not report_insights and persisted_insight_doc:
            report_insights = _derive_insights_from_doc(persisted_insight_doc)
        if not report_clauses and persisted_insight_doc:
            report_clauses = _derive_clauses_from_doc(persisted_insight_doc)
        if not report_recommendations and persisted_insight_doc:
            report_recommendations = _derive_recommendations_from_doc(persisted_insight_doc)

        # Return JSON report
        if job.report_json:
            existing_report = dict(job.report_json)
            if not existing_report.get("insights") and report_insights:
                existing_report["insights"] = report_insights
            if not existing_report.get("clauses") and report_clauses:
                existing_report["clauses"] = report_clauses
            if not existing_report.get("recommendations") and report_recommendations:
                existing_report["recommendations"] = report_recommendations
            if persisted_insight_doc and not existing_report.get("insight_artifact"):
                existing_report["insight_artifact"] = persisted_insight_doc
            return JSONResponse(content=existing_report)
        
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
            "clauses": report_clauses,
            "recommendations": report_recommendations,
            "insights": report_insights,
            "stakeholders": job.stakeholders,
            "risk": job.risk,
        }
        if persisted_insight_doc:
            report["insight_artifact"] = persisted_insight_doc
        
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
