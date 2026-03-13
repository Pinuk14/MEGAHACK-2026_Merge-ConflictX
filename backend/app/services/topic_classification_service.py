from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Dict, List, Optional, Tuple

from backend.app.schema import TopicScore


@dataclass
class TopicClassificationConfig:
    """Configuration for lightweight topic classification."""

    max_topics: int = 4
    min_confidence: float = 0.12
    normalize_confidence: bool = True
    topic_keywords: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "governance_policy": [
                "policy",
                "governance",
                "authority",
                "regulator",
                "oversight",
                "ministry",
                "public authority",
            ],
            "compliance_enforcement": [
                "compliance",
                "enforcement",
                "audit",
                "violation",
                "penalty",
                "sanction",
                "inspection",
            ],
            "finance_funding": [
                "budget",
                "funding",
                "allocation",
                "appropriation",
                "grant",
                "finance",
                "cost",
            ],
            "public_service_delivery": [
                "citizen",
                "public",
                "service",
                "beneficiary",
                "access",
                "inclusion",
                "household",
            ],
            "data_privacy_security": [
                "data",
                "privacy",
                "security",
                "consent",
                "personal information",
                "disclosure",
                "retention",
            ],
            "implementation_timeline": [
                "timeline",
                "deadline",
                "effective date",
                "within",
                "phase",
                "milestone",
                "implementation",
            ],
        }
    )


class TopicClassificationService:
    """
    Keyword-driven topic classifier for policy/research/government documents.

    Returns ranked `TopicScore` objects with bounded confidence values.
    """

    _TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")

    def __init__(self, config: Optional[TopicClassificationConfig] = None) -> None:
        self.config = config or TopicClassificationConfig()

    def classify(self, text: str) -> List[TopicScore]:
        """Classify full document text into ranked topics."""
        normalized = (text or "").strip().lower()
        if not normalized:
            return []

        scores: List[Tuple[str, float]] = []
        token_counts = self._token_count_map(normalized)
        total_tokens = max(sum(token_counts.values()), 1)

        for topic, keywords in self.config.topic_keywords.items():
            score = self._score_topic(normalized, token_counts, total_tokens, keywords)
            if score >= self.config.min_confidence:
                scores.append((topic, score))

        if not scores:
            return [TopicScore(label="general_policy", confidence=0.5)]

        scores.sort(key=lambda x: x[1], reverse=True)
        scores = scores[: self.config.max_topics]

        if self.config.normalize_confidence:
            scores = self._normalize_scores(scores)

        return [TopicScore(label=label, confidence=round(conf, 4)) for label, conf in scores]

    def classify_from_segments(self, segments: List[dict]) -> List[TopicScore]:
        """Classify based on concatenated semantic segments."""
        text = "\n".join(str(seg.get("text", "")) for seg in segments if seg.get("text"))
        return self.classify(text)

    def _score_topic(
        self,
        text: str,
        token_counts: Dict[str, int],
        total_tokens: int,
        keywords: List[str],
    ) -> float:
        """Compute topic score using token and phrase evidence."""
        token_hits = 0
        phrase_hits = 0

        for kw in keywords:
            kw = kw.lower().strip()
            if " " in kw:
                phrase_hits += text.count(kw)
            else:
                token_hits += token_counts.get(kw, 0)

        token_signal = token_hits / max(total_tokens, 1)
        phrase_signal = min(phrase_hits * 0.18, 0.72)

        # smooth bounded score
        raw = (token_signal * 4.2) + phrase_signal
        bounded = 1.0 - math.exp(-raw)
        return min(max(bounded, 0.0), 0.99)

    def _token_count_map(self, text: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for token in self._TOKEN_RE.findall(text.lower()):
            counts[token] = counts.get(token, 0) + 1
        return counts

    @staticmethod
    def _normalize_scores(scores: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        total = sum(score for _, score in scores)
        if total <= 0:
            return scores
        return [(label, score / total) for label, score in scores]
