from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Optional, Set, Tuple

from backend.app.schema import ImpactLevel, StakeholderImpact, StakeholderRole


@dataclass
class StakeholderExtractionConfig:
    """Configuration for stakeholder impact extraction."""

    max_evidence_per_stakeholder: int = 4
    min_impact_summary_chars: int = 20


class StakeholderExtractionService:
    """
    Extract stakeholders and impact statements from semantic segments.

    The service uses role dictionaries + impact cues and returns validated
    `StakeholderImpact` objects for downstream insight orchestration.
    """

    _ROLE_PATTERNS: Dict[StakeholderRole, List[re.Pattern[str]]] = {
        StakeholderRole.GOVERNMENT: [
            re.compile(r"\b(government|ministry|department|public authority|state)\b", re.I),
        ],
        StakeholderRole.REGULATOR: [
            re.compile(r"\b(regulator|regulatory authority|commission|oversight body)\b", re.I),
        ],
        StakeholderRole.PRIVATE_SECTOR: [
            re.compile(r"\b(company|companies|industry|business|operator|enterprise|vendor)\b", re.I),
        ],
        StakeholderRole.CIVIL_SOCIETY: [
            re.compile(r"\b(ngo|civil society|community organization|advocacy group)\b", re.I),
        ],
        StakeholderRole.ACADEMIA: [
            re.compile(r"\b(university|research institute|academic|scholar)\b", re.I),
        ],
        StakeholderRole.PUBLIC: [
            re.compile(r"\b(citizen|citizens|public|consumer|household|resident)\b", re.I),
        ],
        StakeholderRole.INTERNATIONAL_BODY: [
            re.compile(r"\b(united nations|world bank|imf|international agency|regional body)\b", re.I),
        ],
    }

    _IMPACT_CUES = {
        "critical": re.compile(r"\b(mandatory for all|severe|critical|immediate enforcement|criminal liability)\b", re.I),
        "high": re.compile(r"\b(shall|must|significant|major|strict|penalty|fine)\b", re.I),
        "medium": re.compile(r"\b(should|expected to|moderate|guideline|recommended)\b", re.I),
    }

    _SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

    def __init__(self, config: Optional[StakeholderExtractionConfig] = None) -> None:
        self.config = config or StakeholderExtractionConfig()

    def extract_from_segments(self, segments: List[dict]) -> List[StakeholderImpact]:
        """Extract stakeholder impacts from segmented text."""
        grouped: Dict[Tuple[str, StakeholderRole], Dict[str, object]] = {}

        for segment in segments:
            segment_id = str(segment.get("segment_id", ""))
            text = str(segment.get("text", "")).strip()
            if not text:
                continue

            for sentence in self._candidate_sentences(text):
                mentions = self._detect_mentions(sentence)
                if not mentions:
                    continue

                impact_level = self._classify_impact_level(sentence)
                for stakeholder_name, role in mentions:
                    key = (stakeholder_name.lower(), role)
                    bucket = grouped.setdefault(
                        key,
                        {
                            "stakeholder_name": stakeholder_name,
                            "role": role,
                            "impact_level": impact_level,
                            "evidence": set(),
                            "segment_ids": set(),
                            "impact_summaries": [],
                        },
                    )

                    # upgrade impact level if a stronger cue appears
                    bucket["impact_level"] = self._max_impact_level(bucket["impact_level"], impact_level)
                    evidence_set: Set[str] = bucket["evidence"]  # type: ignore[assignment]
                    evidence_set.add(sentence)

                    seg_set: Set[str] = bucket["segment_ids"]  # type: ignore[assignment]
                    if segment_id:
                        seg_set.add(segment_id)

                    summaries: List[str] = bucket["impact_summaries"]  # type: ignore[assignment]
                    summaries.append(self._build_impact_summary(stakeholder_name, role, sentence))

        impacts: List[StakeholderImpact] = []
        for data in grouped.values():
            evidence = list(data["evidence"])[: self.config.max_evidence_per_stakeholder]
            segment_ids = sorted(data["segment_ids"])
            summary = self._pick_best_summary(data["impact_summaries"])  # type: ignore[arg-type]

            impacts.append(
                StakeholderImpact(
                    stakeholder_name=str(data["stakeholder_name"]),
                    role=data["role"],  # type: ignore[arg-type]
                    impact_level=data["impact_level"],  # type: ignore[arg-type]
                    impact_summary=summary,
                    evidence=evidence,
                    segment_ids=segment_ids,
                )
            )

        impacts.sort(key=lambda x: (x.role.value, x.stakeholder_name.lower()))
        return impacts

    def _candidate_sentences(self, text: str):
        for raw in self._SENTENCE_SPLIT_RE.split(text):
            sentence = raw.strip()
            if len(sentence) >= self.config.min_impact_summary_chars:
                yield sentence

    def _detect_mentions(self, sentence: str) -> List[Tuple[str, StakeholderRole]]:
        """Return stakeholder mention tuples: (canonical_name, role)."""
        found: List[Tuple[str, StakeholderRole]] = []

        for role, patterns in self._ROLE_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(sentence)
                if match:
                    found.append((self._canonicalize_name(match.group(0), role), role))
                    break

        return found

    def _classify_impact_level(self, sentence: str) -> ImpactLevel:
        if self._IMPACT_CUES["critical"].search(sentence):
            return ImpactLevel.CRITICAL
        if self._IMPACT_CUES["high"].search(sentence):
            return ImpactLevel.HIGH
        if self._IMPACT_CUES["medium"].search(sentence):
            return ImpactLevel.MEDIUM
        return ImpactLevel.LOW

    @staticmethod
    def _max_impact_level(existing: ImpactLevel, new_level: ImpactLevel) -> ImpactLevel:
        ranking = {
            ImpactLevel.LOW: 1,
            ImpactLevel.MEDIUM: 2,
            ImpactLevel.HIGH: 3,
            ImpactLevel.CRITICAL: 4,
        }
        return new_level if ranking[new_level] > ranking[existing] else existing

    @staticmethod
    def _canonicalize_name(raw_mention: str, role: StakeholderRole) -> str:
        mention = raw_mention.strip().lower()
        normalized = {
            "government": "Government",
            "ministry": "Ministry",
            "department": "Department",
            "public authority": "Public Authority",
            "regulator": "Regulator",
            "regulatory authority": "Regulatory Authority",
            "commission": "Commission",
            "industry": "Industry",
            "companies": "Companies",
            "company": "Company",
            "business": "Businesses",
            "operator": "Operators",
            "citizens": "Citizens",
            "citizen": "Citizens",
            "public": "General Public",
            "consumer": "Consumers",
            "ngo": "NGOs",
            "civil society": "Civil Society",
            "university": "Universities",
            "research institute": "Research Institutes",
            "united nations": "United Nations",
        }
        return normalized.get(mention, raw_mention.strip().title())

    def _build_impact_summary(self, stakeholder_name: str, role: StakeholderRole, sentence: str) -> str:
        prefix = f"{stakeholder_name} ({role.value})"
        summarized = sentence.strip()
        if len(summarized) > 220:
            summarized = f"{summarized[:217].rstrip()}..."
        return f"{prefix} is affected as follows: {summarized}"

    def _pick_best_summary(self, summaries: List[str]) -> str:
        """Pick concise but information-rich summary candidate."""
        if not summaries:
            return "Impact inferred from policy language and stakeholder references."

        # Prefer medium-length summary for readability
        summaries = sorted(summaries, key=lambda s: abs(len(s) - 150))
        return summaries[0]
