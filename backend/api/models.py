"""Pydantic models for job pipeline API responses."""
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# Status & Phase Enums
# ============================================================================

class JobStatus(str, Enum):
    """Job status states."""
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class PipelinePhase(str, Enum):
    """Pipeline step IDs."""
    INGEST = "ingest"
    TOKENIZE = "tokenize"
    CLASSIFY = "classify"
    SEGMENT = "segment"
    SUMMARIZE = "summarize"
    STAKEHOLDER = "stakeholder"
    STRUCTURE = "structure"


# ============================================================================
# SSE Event Models
# ============================================================================

class SubTask(BaseModel):
    """Sub-task within a pipeline step."""
    label: str
    pct: float


class Metric(BaseModel):
    """Metric displayed during step progress."""
    key: str
    val: str


class StepProgressEvent(BaseModel):
    """Fired ~10× per step during execution."""
    step_id: str
    step_index: int
    sector: str
    short: str
    label: str
    desc: str
    color: str
    progress_pct: float
    sub_task_index: int
    sub_tasks: List[SubTask]
    metrics: List[Metric]


class VerdictStats(BaseModel):
    """Stat line in verdict card."""
    k: str
    v: str


class Verdict(BaseModel):
    """Verdict data for step completion."""
    flash: str
    badge: str
    title: str
    sub: str
    alertLabel: str
    alertText: str
    actionLabel: str
    actionText: str
    riskIndex: str
    riskLabel: str
    economicVal: str
    economicLabel: str
    stats: List[VerdictStats]
    tags: List[str]


class StepCompleteEvent(BaseModel):
    """Fired once per step, triggers verdict card."""
    step_id: str
    verdict: Verdict


class PipelineDoneEvent(BaseModel):
    """Emitted when all steps finish."""
    confidence: float
    runtime_seconds: float


# ============================================================================
# Data Endpoint Models
# ============================================================================

class VelocityPoint(BaseModel):
    """Point in velocity sparkline."""
    t: int  # timestamp
    val: float


class StatsResponse(BaseModel):
    """GET /jobs/{id}/stats"""
    tokens_processed: int
    accuracy_pct: float
    delta_pct: float
    velocity_series: List[VelocityPoint]


class StructureResponse(BaseModel):
    """GET /jobs/{id}/structure"""
    sections: int
    citation_density: float
    figures: int
    tables: int


class RadioComm(BaseModel):
    """Single radio communication."""
    type: str  # "TX" or "RX"
    text: str
    color: str
    phase: str  # ingest, tokenize, classify, etc.


class RadioResponse(BaseModel):
    """GET /jobs/{id}/radio"""
    comms: List[RadioComm]


class TopicBar(BaseModel):
    """Single topic bar."""
    label: str
    pct: int


class TopicsResponse(BaseModel):
    """GET /jobs/{id}/topics"""
    topics: List[TopicBar]


class Clause(BaseModel):
    """Single clause."""
    label: str
    val: str
    color: str


class ClausesResponse(BaseModel):
    """GET /jobs/{id}/clauses"""
    clauses: List[Clause]


class Recommendation(BaseModel):
    """Single recommendation."""
    priority: str  # IMMEDIATE, STRATEGIC, LONG-TERM
    text: str


class RecommendationsResponse(BaseModel):
    """GET /jobs/{id}/recommendations"""
    recommendations: List[Recommendation]


class Insight(BaseModel):
    """Single insight."""
    id: str
    conf: str
    text: str
    color: str
    shown_after_step: str


class InsightsResponse(BaseModel):
    """GET /jobs/{id}/insights"""
    insights: List[Insight]


class StakeholderGroup(BaseModel):
    """Single stakeholder group."""
    rank: str
    label: str
    score: float
    max_score: float


class StakeholdersResponse(BaseModel):
    """GET /jobs/{id}/stakeholders"""
    groups: List[StakeholderGroup]


class RiskResponse(BaseModel):
    """GET /jobs/{id}/risk"""
    risk_value: float
    sentiment: str
    volatility: str


# ============================================================================
# Job Lifecycle Models
# ============================================================================

class JobDetailResponse(BaseModel):
    """GET /jobs/{id}"""
    job_id: str
    status: JobStatus
    current_step: Optional[str] = None
    elapsed_seconds: int
    created_at: datetime
    completed_at: Optional[datetime] = None


class UploadResponse(BaseModel):
    """POST /upload response."""
    file_id: str
    filename: str
    size_bytes: int


class UploadBatchResponse(BaseModel):
    """POST /upload-multiple response."""
    files: List[UploadResponse]


class RunRequest(BaseModel):
    """POST /run request body."""
    text: Optional[str] = Field(None, min_length=10)
    file_id: Optional[str] = None
    file_ids: Optional[List[str]] = None


class RunResponse(BaseModel):
    """POST /run response."""
    job_id: str
    status: str  # "queued"


class HealthResponse(BaseModel):
    """GET /health response."""
    status: str
    uptime_pct: float
    system_temp: str


class ReportResponse(BaseModel):
    """Report download metadata."""
    job_id: str
    format: str
    filename: str
