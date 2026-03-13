from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Optional, Pattern, Tuple

from backend.app.schema import ClauseInsight, ClauseType


@dataclass
class ClauseDetectionConfig:
    """Configuration for clause detection in segmented policy text."""

    min_clause_chars: int = 30
    max_snippet_chars: int = 650
    min_confidence: float = 0.35


class ClauseDetectionService:
    """
    Detects legal/policy clauses from semantic segments.

    Inputs:
    - segments from semantic segmentation service

    Outputs:
    - validated `ClauseInsight` objects
    """

    _CLAUSE_RULES: Dict[ClauseType, List[Pattern[str]]] = {
        ClauseType.OBLIGATION: [
            re.compile(r"\b(shall|must|required to|is required to|mandatory)\b", re.I),
        ],
        ClauseType.PROHIBITION: [
            re.compile(r"\b(shall not|must not|prohibited|forbidden|no person shall)\b", re.I),
        ],
        ClauseType.PERMISSION: [
            re.compile(r"\b(may|is permitted to|authorized to|allowed to)\b", re.I),
        ],
        ClauseType.COMPLIANCE: [
            re.compile(r"\b(compliance|audit|inspection|enforcement|violation|breach)\b", re.I),
        ],
        ClauseType.DEADLINE: [
            re.compile(r"\b(within\s+\d+\s+(days|months|years)|no later than|deadline|effective date)\b", re.I),
        ],
        ClauseType.DEFINITION: [
            re.compile(r"\b(\"[a-z][^\"]+\"\s+means|defined as|for the purpose of this)\b", re.I),
        ],
        ClauseType.PENALTY: [
            re.compile(r"\b(penalty|fine|imprisonment|sanction|liable on conviction)\b", re.I),
        ],
        ClauseType.GOVERNANCE: [
            re.compile(r"\b(authority|oversight|governing body|ministry|agency|board)\b", re.I),
        ],
        ClauseType.FUNDING: [
            re.compile(r"\b(funding|budget|appropriation|grant|allocation|finance)\b", re.I),
        ],
    }

    _SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

    def __init__(self, config: Optional[ClauseDetectionConfig] = None) -> None:
        self.config = config or ClauseDetectionConfig()

    def detect_from_segments(self, segments: List[dict]) -> List[ClauseInsight]:
        """Detect clauses from a list of semantic segments."""
        insights: List[ClauseInsight] = []
        clause_count = 0

        for segment in segments:
            segment_id = str(segment.get("segment_id", ""))
            page_number = self._extract_page_number(segment)
            text = str(segment.get("text", "")).strip()
            if not text:
                continue

            for sentence in self._iter_candidate_sentences(text):
                clause_type, rule_hits = self._classify_sentence(sentence)
                if clause_type is None:
                    continue

                confidence = self._score_confidence(sentence=sentence, match_count=rule_hits)
                if confidence < self.config.min_confidence:
                    continue

                clause_count += 1
                insights.append(
                    ClauseInsight(
                        clause_id=f"clause-{clause_count:04d}",
                        clause_type=clause_type,
                        text=sentence[: self.config.max_snippet_chars],
                        rationale=self._build_rationale(clause_type, sentence),
                        page_number=page_number,
                        segment_id=segment_id or None,
                        confidence=confidence,
                    )
                )

        return insights

    def _iter_candidate_sentences(self, text: str):
        """Yield candidate sentence snippets for clause checks."""
        for raw in self._SENTENCE_SPLIT_RE.split(text):
            sentence = raw.strip()
            if len(sentence) < self.config.min_clause_chars:
                continue
            yield sentence

    def _classify_sentence(self, sentence: str) -> Tuple[Optional[ClauseType], int]:
        """Classify sentence into one clause type based on best rule hit count."""
        scored: List[Tuple[ClauseType, int]] = []

        for clause_type, patterns in self._CLAUSE_RULES.items():
            hits = sum(1 for p in patterns if p.search(sentence))
            if hits > 0:
                scored.append((clause_type, hits))

        if not scored:
            return None, 0

        # tie-break by deterministic enum order after max hit count
        scored.sort(key=lambda x: (-x[1], x[0].value))
        return scored[0]

    def _score_confidence(self, sentence: str, match_count: int) -> float:
        """Simple bounded confidence heuristic in [0, 1]."""
        length_bonus = min(len(sentence) / 220.0, 1.0) * 0.2
        hit_bonus = min(match_count * 0.22, 0.44)
        modal_bonus = 0.2 if re.search(r"\b(shall|must|shall not|must not)\b", sentence, re.I) else 0.0

        score = 0.25 + length_bonus + hit_bonus + modal_bonus
        return round(min(score, 0.99), 3)

    def _build_rationale(self, clause_type: ClauseType, sentence: str) -> str:
        """Create a short rationale for explainability."""
        if clause_type == ClauseType.OBLIGATION:
            return "Contains mandatory language indicating required action."
        if clause_type == ClauseType.PROHIBITION:
            return "Contains restrictive language that forbids an action."
        if clause_type == ClauseType.DEADLINE:
            return "Contains timing constraints or explicit implementation dates."
        if clause_type == ClauseType.COMPLIANCE:
            return "References compliance monitoring, enforcement, or violations."
        if clause_type == ClauseType.PENALTY:
            return "Specifies sanctions or punitive consequences."
        if clause_type == ClauseType.DEFINITION:
            return "Defines a legal/policy term used in the document."
        if clause_type == ClauseType.PERMISSION:
            return "Indicates a permitted or authorized action."
        if clause_type == ClauseType.GOVERNANCE:
            return "Mentions institutional authority or oversight responsibility."
        if clause_type == ClauseType.FUNDING:
            return "References budget, funding, or financial allocation."

        return f"Classified as {clause_type.value} based on policy-language patterns."

    @staticmethod
    def _extract_page_number(segment: dict) -> Optional[int]:
        """Best-effort extraction of page number from segment metadata."""
        candidates = [
            segment.get("page_number"),
            (segment.get("metadata") or {}).get("page_number") if isinstance(segment.get("metadata"), dict) else None,
        ]
        for c in candidates:
            if isinstance(c, int) and c >= 1:
                return c
        return None
