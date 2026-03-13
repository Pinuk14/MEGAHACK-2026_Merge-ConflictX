from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional

from backend.app.schema import ClauseInsight, ExecutiveSummary, StakeholderImpact, TopicScore


@dataclass
class SummarizationConfig:
    """Configuration for extractive executive summarization."""

    max_sentences_in_short_summary: int = 3
    max_key_points: int = 5
    max_recommended_actions: int = 4


class SummarizationService:
    """
    Builds an executive summary from document text + extracted insights.

    Strategy:
    - sentence scoring for concise short summary
    - convert top clauses/topics/stakeholders into key points
    - infer action items from obligation/compliance clauses
    """

    _SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

    def __init__(self, config: Optional[SummarizationConfig] = None) -> None:
        self.config = config or SummarizationConfig()

    def summarize(
        self,
        text: str,
        clauses: List[ClauseInsight],
        stakeholders: List[StakeholderImpact],
        topics: List[TopicScore],
    ) -> ExecutiveSummary:
        """Generate a structured executive summary."""
        short_summary = self._build_short_summary(text, clauses, topics)
        key_points = self._build_key_points(clauses, stakeholders, topics)
        recommended_actions = self._build_recommended_actions(clauses, stakeholders)

        return ExecutiveSummary(
            short_summary=short_summary,
            key_points=key_points[: self.config.max_key_points],
            recommended_actions=recommended_actions[: self.config.max_recommended_actions],
        )

    def _build_short_summary(self, text: str, clauses: List[ClauseInsight], topics: List[TopicScore]) -> str:
        sentences = [s.strip() for s in self._SENTENCE_SPLIT_RE.split((text or "").strip()) if s.strip()]

        if not sentences:
            top_topic = topics[0].label if topics else "general policy"
            return (
                f"This document addresses {top_topic} and outlines obligations, governance, "
                "and implementation considerations for relevant stakeholders."
            )

        selected = self._rank_sentences(sentences, clauses, topics)[: self.config.max_sentences_in_short_summary]
        return " ".join(selected)

    def _rank_sentences(
        self,
        sentences: List[str],
        clauses: List[ClauseInsight],
        topics: List[TopicScore],
    ) -> List[str]:
        topic_terms = {t.label.replace("_", " ") for t in topics}
        clause_terms = {c.clause_type.value for c in clauses}

        scored = []
        for s in sentences:
            low = s.lower()
            score = 0.0
            score += min(len(s) / 280.0, 1.0) * 0.35
            score += 0.35 if any(term in low for term in clause_terms) else 0.0
            score += 0.25 if any(term in low for term in topic_terms) else 0.0
            if re.search(r"\b(shall|must|required|deadline|penalty|compliance)\b", low):
                score += 0.2
            scored.append((s, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored]

    def _build_key_points(
        self,
        clauses: List[ClauseInsight],
        stakeholders: List[StakeholderImpact],
        topics: List[TopicScore],
    ) -> List[str]:
        points: List[str] = []

        if topics:
            top = ", ".join(f"{t.label} ({round(t.confidence * 100)}%)" for t in topics[:3])
            points.append(f"Primary document themes: {top}.")

        top_clauses = sorted(clauses, key=lambda c: c.confidence, reverse=True)[:3]
        for c in top_clauses:
            snippet = c.text.strip()
            if len(snippet) > 160:
                snippet = f"{snippet[:157].rstrip()}..."
            points.append(f"{c.clause_type.value.capitalize()} clause identified: {snippet}")

        top_stakeholders = sorted(
            stakeholders,
            key=lambda s: {"low": 1, "medium": 2, "high": 3, "critical": 4}[s.impact_level.value],
            reverse=True,
        )[:2]
        for st in top_stakeholders:
            points.append(
                f"{st.stakeholder_name} is {st.impact_level.value}-impact with role {st.role.value}."
            )

        if not points:
            points.append("No high-signal clauses or stakeholder impacts were detected.")

        return points

    def _build_recommended_actions(
        self,
        clauses: List[ClauseInsight],
        stakeholders: List[StakeholderImpact],
    ) -> List[str]:
        actions: List[str] = []

        if any(c.clause_type.value in {"obligation", "compliance"} for c in clauses):
            actions.append("Create a compliance checklist mapped to all obligation and compliance clauses.")

        if any(c.clause_type.value == "deadline" for c in clauses):
            actions.append("Build an implementation timeline with owners for each deadline-related clause.")

        high_impact = [s for s in stakeholders if s.impact_level.value in {"high", "critical"}]
        if high_impact:
            names = ", ".join(sorted({s.stakeholder_name for s in high_impact})[:4])
            actions.append(f"Run targeted stakeholder consultations with: {names}.")

        if any(c.clause_type.value == "penalty" for c in clauses):
            actions.append("Perform legal-risk review for penalty and enforcement exposure.")

        if not actions:
            actions.append("Validate findings with domain experts before policy adoption.")

        return actions
