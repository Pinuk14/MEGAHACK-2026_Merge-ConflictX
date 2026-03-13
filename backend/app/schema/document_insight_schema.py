from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClauseType(str, Enum):
    """Canonical categories for policy/legal clause detection."""

    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"
    COMPLIANCE = "compliance"
    DEADLINE = "deadline"
    DEFINITION = "definition"
    PENALTY = "penalty"
    GOVERNANCE = "governance"
    FUNDING = "funding"
    OTHER = "other"


class StakeholderRole(str, Enum):
    """Supported stakeholder role classes."""

    GOVERNMENT = "government"
    REGULATOR = "regulator"
    PRIVATE_SECTOR = "private_sector"
    CIVIL_SOCIETY = "civil_society"
    ACADEMIA = "academia"
    PUBLIC = "public"
    INTERNATIONAL_BODY = "international_body"
    OTHER = "other"


class ImpactLevel(str, Enum):
    """Strength of impact for each stakeholder/topic relationship."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExecutiveSummary(BaseModel):
    """Human-readable top-level synthesis for decision makers."""

    model_config = ConfigDict(extra="forbid")

    short_summary: str = Field(
        ...,
        description="2-4 sentence concise summary of the document.",
        min_length=20,
    )
    key_points: List[str] = Field(
        default_factory=list,
        description="Bullet-like major points extracted from the report/policy.",
    )
    recommended_actions: List[str] = Field(
        default_factory=list,
        description="Actionable recommendations derived from the document.",
    )


class ClauseInsight(BaseModel):
    """Detected legal/policy clause with traceability to source text."""

    model_config = ConfigDict(extra="forbid")

    clause_id: str = Field(..., description="Unique ID for the detected clause.")
    clause_type: ClauseType = Field(..., description="Normalized clause category.")
    text: str = Field(..., description="Exact or near-exact clause text snippet.", min_length=10)
    rationale: Optional[str] = Field(
        default=None,
        description="Optional short explanation of why this clause is important.",
    )
    page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-based page number if source is paginated (e.g., PDF).",
    )
    segment_id: Optional[str] = Field(
        default=None,
        description="Semantic segment ID where this clause was found.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Detector confidence score in [0, 1].",
    )


class StakeholderImpact(BaseModel):
    """How a stakeholder is affected by the document or policy."""

    model_config = ConfigDict(extra="forbid")

    stakeholder_name: str = Field(..., min_length=2)
    role: StakeholderRole = Field(..., description="Normalized stakeholder role.")
    impact_level: ImpactLevel = Field(..., description="Impact severity level.")
    impact_summary: str = Field(
        ..., description="Short statement describing expected impact.", min_length=8
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="Supporting snippets from the source document.",
    )
    segment_ids: List[str] = Field(
        default_factory=list,
        description="Segment IDs linked to this stakeholder impact.",
    )


class TopicScore(BaseModel):
    """Topic classification output with probability-like confidence."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., min_length=2, description="Predicted topic label.")
    confidence: float = Field(..., ge=0.0, le=1.0)


class DocumentInsight(BaseModel):
    """Top-level structured insight record persisted to outputs/."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(..., description="Stable ID tied to ingestion/storage record.")
    source_filename: Optional[str] = Field(
        default=None,
        description="Original uploaded file name, if available.",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when insight record was generated.",
    )
    executive_summary: ExecutiveSummary
    clauses: List[ClauseInsight] = Field(default_factory=list)
    stakeholders: List[StakeholderImpact] = Field(default_factory=list)
    topics: List[TopicScore] = Field(default_factory=list)


class InsightBatch(BaseModel):
    """Container schema for one or many document insights."""

    model_config = ConfigDict(extra="forbid")

    items: List[DocumentInsight] = Field(default_factory=list)
