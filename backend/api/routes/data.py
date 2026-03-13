"""Data endpoint routes for all panel information."""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from backend.api.models import (
    StatsResponse, StructureResponse, RadioResponse, TopicsResponse,
    ClausesResponse, RecommendationsResponse, InsightsResponse,
    StakeholdersResponse, RiskResponse,
    JobStatus,
    VelocityPoint, RadioComm, TopicBar, Clause, Recommendation,
    Insight, StakeholderGroup
)
from backend.api.job_manager import get_job_manager

router = APIRouter(prefix="/jobs", tags=["data"])
job_manager = get_job_manager()
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_persisted_insight_doc(job_id: str) -> dict | None:
    """Load per-job persisted insight artifact when in-memory cache is empty."""
    insight_path = PROJECT_ROOT / "infrastructure" / "storage" / "outputs" / "insights" / f"insight_{job_id}.json"
    if not insight_path.exists():
        return None

    try:
        with open(insight_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        return None


def _insights_from_persisted_doc(doc: dict) -> list[Insight]:
    """Convert persisted executive summary to frontend insight rows."""
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

    if not points:
        return []

    palette = ["#10b981", "#f59e0b", "#ef4444", "#06b6d4"]
    return [
        Insight(
            id=f"i{idx}",
            conf=f"{max(72, 96 - (idx * 6))}%",
            text=point,
            color=palette[(idx - 1) % len(palette)],
            shown_after_step="summarize" if idx <= 2 else "stakeholder",
        )
        for idx, point in enumerate(points[:6], start=1)
    ]


def _clauses_from_persisted_doc(doc: dict) -> list[Clause]:
    """Convert persisted clause artifacts into frontend clause rows."""
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

    output: list[Clause] = []
    for item in persisted_clauses[:12]:
        if not isinstance(item, dict):
            continue
        clause_type = str(item.get("clause_type") or "other").strip().lower()
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        output.append(
            Clause(
                label=clause_type.upper(),
                val=text[:72] + ("..." if len(text) > 72 else ""),
                color=clause_colors.get(clause_type, "#ec5b13"),
            )
        )
    return output


def _recommendations_from_persisted_doc(doc: dict) -> list[Recommendation]:
    """Convert persisted summary recommended actions into recommendation rows."""
    summary = doc.get("executive_summary") if isinstance(doc, dict) else None
    if not isinstance(summary, dict):
        return []

    actions = summary.get("recommended_actions")
    if not isinstance(actions, list):
        return []

    priority_cycle = ["IMMEDIATE", "STRATEGIC", "LONG-TERM"]
    recommendations: list[Recommendation] = []
    for idx, action in enumerate(actions[:6]):
        text = str(action).strip()
        if not text:
            continue
        recommendations.append(
            Recommendation(
                priority=priority_cycle[idx % len(priority_cycle)],
                text=text,
            )
        )
    return recommendations


def _check_job_exists(job_id: str):
    """Helper to check if job exists."""
    if not job_manager.get_job(job_id):
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found"
        )


def _is_done(job) -> bool:
    return job.status == JobStatus.DONE


def _derive_velocity_series(job) -> list[VelocityPoint]:
    progress_events = [
        e["data"]
        for e in job.events
        if e.get("type") == "step_progress" and isinstance(e.get("data"), dict)
    ]
    if not progress_events:
        return [VelocityPoint(t=0, val=0.0)]

    # Convert step progress to a monotonic runtime curve.
    points: list[VelocityPoint] = []
    for idx, data in enumerate(progress_events, start=1):
        step_index = int(data.get("step_index", 0))
        progress_pct = float(data.get("progress_pct", 0.0))
        value = max(0.0, (step_index * 10.0) + (progress_pct / 10.0))
        points.append(VelocityPoint(t=idx * 2, val=round(value, 2)))

    # Keep response compact for frontend rendering.
    return points[-25:]


@router.get("/{job_id}/stats", response_model=StatsResponse)
def get_job_stats(job_id: str) -> StatsResponse:
    """
    Get pit stop stats and velocity sparkline.
    Returns { tokens_processed, accuracy_pct, delta_pct, velocity_series }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached stats when available.
    if job.stats:
        return StatsResponse(**job.stats)

    # No synthetic/mock stats: derive only from current job state.
    return StatsResponse(
        tokens_processed=len((job.input_text or "").split()),
        accuracy_pct=0.0,
        delta_pct=0.0,
        velocity_series=_derive_velocity_series(job),
    )


@router.get("/{job_id}/structure", response_model=StructureResponse)
def get_job_structure(job_id: str) -> StructureResponse:
    """
    Get document structure (aero analysis).
    Returns { sections, citation_density, figures, tables }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached structure only; otherwise return empty state.
    if job.structure:
        return StructureResponse(**job.structure)

    return StructureResponse(
        sections=0,
        citation_density=0.0,
        figures=0,
        tables=0,
    )


@router.get("/{job_id}/radio", response_model=RadioResponse)
def get_job_radio(job_id: str) -> RadioResponse:
    """
    Get radio communications log.
    Returns { comms: [{ type, text, color, phase }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached comms only; otherwise no comms.
    if job.radio_comms:
        return RadioResponse(
            comms=[RadioComm(**c) for c in job.radio_comms]
        )

    return RadioResponse(comms=[])


@router.get("/{job_id}/topics", response_model=TopicsResponse)
def get_job_topics(job_id: str) -> TopicsResponse:
    """
    Get topic classification results.
    Returns { topics: [{ label, pct }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached topics only.
    if job.topics:
        return TopicsResponse(
            topics=[TopicBar(**t) for t in job.topics]
        )

    return TopicsResponse(topics=[])


@router.get("/{job_id}/clauses", response_model=ClausesResponse)
def get_job_clauses(job_id: str) -> ClausesResponse:
    """
    Get detected clauses (scrutineering).
    Returns { clauses: [{ label, val, color }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached clauses only.
    if job.clauses:
        return ClausesResponse(
            clauses=[Clause(**c) for c in job.clauses]
        )

    persisted_doc = _load_persisted_insight_doc(job_id)
    if persisted_doc:
        persisted_clauses = _clauses_from_persisted_doc(persisted_doc)
        if persisted_clauses:
            return ClausesResponse(clauses=persisted_clauses)

    return ClausesResponse(clauses=[])


@router.get("/{job_id}/recommendations", response_model=RecommendationsResponse)
def get_job_recommendations(job_id: str) -> RecommendationsResponse:
    """
    Get race strategy recommendations.
    Returns { recommendations: [{ priority, text }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached recommendations only.
    if job.recommendations:
        return RecommendationsResponse(
            recommendations=[Recommendation(**r) for r in job.recommendations]
        )

    persisted_doc = _load_persisted_insight_doc(job_id)
    if persisted_doc:
        persisted_recommendations = _recommendations_from_persisted_doc(persisted_doc)
        if persisted_recommendations:
            return RecommendationsResponse(recommendations=persisted_recommendations)

    return RecommendationsResponse(recommendations=[])


@router.get("/{job_id}/insights", response_model=InsightsResponse)
def get_job_insights(job_id: str) -> InsightsResponse:
    """
    Get race results insights.
    Returns { insights: [{ id, conf, text, color, shown_after_step }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached insights only.
    if job.insights:
        return InsightsResponse(
            insights=[Insight(**i) for i in job.insights]
        )

    persisted_doc = _load_persisted_insight_doc(job_id)
    if persisted_doc:
        persisted_insights = _insights_from_persisted_doc(persisted_doc)
        if persisted_insights:
            return InsightsResponse(insights=persisted_insights)

    return InsightsResponse(insights=[])


@router.get("/{job_id}/stakeholders", response_model=StakeholdersResponse)
def get_job_stakeholders(job_id: str) -> StakeholdersResponse:
    """
    Get stakeholder standings.
    Returns { groups: [{ rank, label, score, max_score }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached stakeholders only.
    if job.stakeholders:
        return StakeholdersResponse(
            groups=[StakeholderGroup(**s) for s in job.stakeholders]
        )

    return StakeholdersResponse(groups=[])


@router.get("/{job_id}/risk", response_model=RiskResponse)
def get_job_risk(job_id: str) -> RiskResponse:
    """
    Get risk metrics.
    Returns { risk_value, sentiment, volatility }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached risk only; otherwise explicit unknown state.
    if job.risk:
        return RiskResponse(**job.risk)

    return RiskResponse(
        risk_value=0.0,
        sentiment="unknown",
        volatility="unknown"
    )
