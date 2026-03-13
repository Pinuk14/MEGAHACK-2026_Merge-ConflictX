"""Data endpoint routes for all panel information."""
from fastapi import APIRouter, HTTPException
from backend.api.models import (
    StatsResponse, StructureResponse, RadioResponse, TopicsResponse,
    ClausesResponse, RecommendationsResponse, InsightsResponse,
    StakeholdersResponse, RiskResponse,
    JobStatus,
    VelocityPoint, RadioComm, TopicBar, Clause, Recommendation, 
    Insight, StakeholderGroup, VerdictStats
)
from backend.api.job_manager import get_job_manager

router = APIRouter(prefix="/jobs", tags=["data"])
job_manager = get_job_manager()


def _check_job_exists(job_id: str):
    """Helper to check if job exists."""
    if not job_manager.get_job(job_id):
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found"
        )


def _is_done(job) -> bool:
    return job.status == JobStatus.DONE


@router.get("/{job_id}/stats", response_model=StatsResponse)
def get_job_stats(job_id: str) -> StatsResponse:
    """
    Get pit stop stats and velocity sparkline.
    Returns { tokens_processed, accuracy_pct, delta_pct, velocity_series }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached stats or defaults
    if job.stats:
        return StatsResponse(**job.stats)
    
    if _is_done(job):
        return StatsResponse(
            tokens_processed=len((job.input_text or "").split()),
            accuracy_pct=0.0,
            delta_pct=0.0,
            velocity_series=[VelocityPoint(t=0, val=0.0)],
        )

    return StatsResponse(
        tokens_processed=4_250_000,
        accuracy_pct=94.2,
        delta_pct=+12.3,
        velocity_series=[
            VelocityPoint(t=0, val=0.0),
            VelocityPoint(t=10, val=2.5),
            VelocityPoint(t=20, val=5.1),
            VelocityPoint(t=30, val=4.8),
            VelocityPoint(t=40, val=8.2),
            VelocityPoint(t=50, val=9.5),
        ]
    )


@router.get("/{job_id}/structure", response_model=StructureResponse)
def get_job_structure(job_id: str) -> StructureResponse:
    """
    Get document structure (aero analysis).
    Returns { sections, citation_density, figures, tables }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached structure or defaults
    if job.structure:
        return StructureResponse(**job.structure)
    
    if _is_done(job):
        return StructureResponse(
            sections=0,
            citation_density=0.0,
            figures=0,
            tables=0,
        )

    return StructureResponse(
        sections=12,
        citation_density=0.18,
        figures=3,
        tables=5,
    )


@router.get("/{job_id}/radio", response_model=RadioResponse)
def get_job_radio(job_id: str) -> RadioResponse:
    """
    Get radio communications log.
    Returns { comms: [{ type, text, color, phase }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached comms or defaults
    if job.radio_comms:
        return RadioResponse(
            comms=[RadioComm(**c) for c in job.radio_comms]
        )
    
    if _is_done(job):
        return RadioResponse(comms=[])

    return RadioResponse(
        comms=[
            RadioComm(type="TX", text="Initiating document ingest...", color="#6366f1", phase="ingest"),
            RadioComm(type="RX", text="256MB buffered", color="#10b981", phase="ingest"),
            RadioComm(type="TX", text="Tokenizing segments...", color="#6366f1", phase="tokenize"),
            RadioComm(type="RX", text="18,450 tokens extracted", color="#10b981", phase="tokenize"),
        ]
    )


@router.get("/{job_id}/topics", response_model=TopicsResponse)
def get_job_topics(job_id: str) -> TopicsResponse:
    """
    Get topic classification results.
    Returns { topics: [{ label, pct }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached topics or defaults
    if job.topics:
        return TopicsResponse(
            topics=[TopicBar(**t) for t in job.topics]
        )
    
    if _is_done(job):
        return TopicsResponse(topics=[])

    return TopicsResponse(
        topics=[
            TopicBar(label="GOVERNANCE", pct=88),
            TopicBar(label="LIABILITY", pct=65),
            TopicBar(label="SUSTAINABILITY", pct=42),
        ]
    )


@router.get("/{job_id}/clauses", response_model=ClausesResponse)
def get_job_clauses(job_id: str) -> ClausesResponse:
    """
    Get detected clauses (scrutineering).
    Returns { clauses: [{ label, val, color }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached clauses or defaults
    if job.clauses:
        return ClausesResponse(
            clauses=[Clause(**c) for c in job.clauses]
        )
    
    if _is_done(job):
        return ClausesResponse(clauses=[])

    return ClausesResponse(
        clauses=[
            Clause(label="Indemnification", val="Cross-party", color="#ef4444"),
            Clause(label="Warranty", val="12-month", color="#f97316"),
            Clause(label="IP Rights", val="Shared ownership", color="#eab308"),
        ]
    )


@router.get("/{job_id}/recommendations", response_model=RecommendationsResponse)
def get_job_recommendations(job_id: str) -> RecommendationsResponse:
    """
    Get race strategy recommendations.
    Returns { recommendations: [{ priority, text }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached recommendations or defaults
    if job.recommendations:
        return RecommendationsResponse(
            recommendations=[Recommendation(**r) for r in job.recommendations]
        )
    
    if _is_done(job):
        return RecommendationsResponse(recommendations=[])

    return RecommendationsResponse(
        recommendations=[
            Recommendation(priority="IMMEDIATE", text="Flag regulatory exposure in Section 2.1"),
            Recommendation(priority="STRATEGIC", text="Negotiate liability caps to 5M"),
            Recommendation(priority="LONG-TERM", text="Develop IP covenants for derivative works"),
        ]
    )


@router.get("/{job_id}/insights", response_model=InsightsResponse)
def get_job_insights(job_id: str) -> InsightsResponse:
    """
    Get race results insights.
    Returns { insights: [{ id, conf, text, color, shown_after_step }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached insights or defaults
    if job.insights:
        return InsightsResponse(
            insights=[Insight(**i) for i in job.insights]
        )
    
    if _is_done(job):
        return InsightsResponse(insights=[])

    return InsightsResponse(
        insights=[
            Insight(
                id="i1",
                conf="92%",
                text="Healthcare sector dominates document",
                color="#10b981",
                shown_after_step="segment"
            ),
            Insight(
                id="i2",
                conf="87%",
                text="High regulatory burden in jurisdiction",
                color="#f59e0b",
                shown_after_step="summarize"
            ),
            Insight(
                id="i3",
                conf="78%",
                text="Multiple stakeholder conflicts identified",
                color="#ef4444",
                shown_after_step="stakeholder"
            ),
        ]
    )


@router.get("/{job_id}/stakeholders", response_model=StakeholdersResponse)
def get_job_stakeholders(job_id: str) -> StakeholdersResponse:
    """
    Get stakeholder standings.
    Returns { groups: [{ rank, label, score, max_score }] }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached stakeholders or defaults
    if job.stakeholders:
        return StakeholdersResponse(
            groups=[StakeholderGroup(**s) for s in job.stakeholders]
        )
    
    if _is_done(job):
        return StakeholdersResponse(groups=[])

    return StakeholdersResponse(
        groups=[
            StakeholderGroup(rank="1st", label="Regulators", score=95, max_score=100),
            StakeholderGroup(rank="2nd", label="Customers", score=78, max_score=100),
            StakeholderGroup(rank="3rd", label="Partners", score=65, max_score=100),
        ]
    )


@router.get("/{job_id}/risk", response_model=RiskResponse)
def get_job_risk(job_id: str) -> RiskResponse:
    """
    Get risk metrics.
    Returns { risk_value, sentiment, volatility }
    """
    _check_job_exists(job_id)
    job = job_manager.get_job(job_id)
    
    # Return cached risk or defaults
    if job.risk:
        return RiskResponse(**job.risk)
    
    if _is_done(job):
        return RiskResponse(
            risk_value=0.0,
            sentiment="unknown",
            volatility="unknown"
        )

    return RiskResponse(
        risk_value=0.72,
        sentiment="cautious",
        volatility="high"
    )
