from __future__ import annotations

"""
LLM Service — local Ollama backend
===================================
Enriches rule-based document analysis with a locally running Ollama model.

No API key required. Requires `ollama serve` to be running and a model to be
pulled (e.g. `ollama pull llama3.2`).

Environment Variables
---------------------
OLLAMA_HOST           : base URL of the Ollama server (default: http://localhost:11434)
OLLAMA_MODEL          : model name to use          (default: llama3.2)
LLM_TEMPERATURE       : float 0‑1                  (default: 0.2)
LLM_MAX_OUTPUT_TOKENS : max tokens in response     (default: 2048)
"""

import json
import logging
import os
import re
import textwrap
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """Runtime configuration for the LLM service."""

    host: str = "http://localhost:11434"
    model: str = "mistral:latest"
    temperature: float = 0.2
    max_output_tokens: int = 2048
    two_pass_parsing: bool = True
    strict_schema_enforcement: bool = True
    validator_model: str = ""
    validator_temperature: float = 0.0
    context_budget_chars: int = 4200
    max_prompt_examples: int = 2
    grounding_overlap_threshold: float = 0.35
    # If True, connection errors fall back gracefully instead of raising
    allow_fallback: bool = True

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model=os.environ.get("OLLAMA_MODEL", "mistral:latest"),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.2")),
            max_output_tokens=int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "2048")),
            two_pass_parsing=os.environ.get("LLM_TWO_PASS_PARSING", "true").lower() != "false",
            strict_schema_enforcement=os.environ.get("LLM_STRICT_SCHEMA", "true").lower() != "false",
            validator_model=os.environ.get("OLLAMA_VALIDATOR_MODEL", "").strip(),
            validator_temperature=float(os.environ.get("LLM_VALIDATOR_TEMPERATURE", "0.0")),
            context_budget_chars=int(os.environ.get("LLM_CONTEXT_BUDGET_CHARS", "4200")),
            max_prompt_examples=int(os.environ.get("LLM_MAX_PROMPT_EXAMPLES", "2")),
            grounding_overlap_threshold=float(os.environ.get("LLM_GROUNDING_OVERLAP", "0.35")),
        )


# ---------------------------------------------------------------------------
# Core LLM Client
# ---------------------------------------------------------------------------

class LLMService:
    """
    Wrapper around a local Ollama instance for document analysis tasks.

    All public methods return plain Python dicts/lists.  If Ollama is
    not reachable and `allow_fallback` is True (default), they return
    empty structures so callers can fall back to rule-based results.

    Usage
    -----
    >>> svc = LLMService()
    >>> if svc.is_available:
    ...     result = svc.summarize_document(text, clauses, stakeholders, topics)
    """

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig.from_env()
        self._prompt_failure_memory: Dict[str, List[str]] = {
            "executive summary": [],
            "clause enrichment": [],
            "stakeholder impact enrichment": [],
            "text verification": [],
        }
        self._validator_enabled = False
        self._client = self._build_client()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def summarize_document(
        self,
        text: str,
        rule_based_clauses: List[Dict[str, Any]],
        rule_based_stakeholders: List[Dict[str, Any]],
        rule_based_topics: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate a rich executive summary using the LLM.

        Returns a dict with keys:
          short_summary       : str
          key_points          : List[str]
          recommended_actions : List[str]
        """
        source_context = self._build_summary_context(
            text=text,
            clauses=rule_based_clauses,
            stakeholders=rule_based_stakeholders,
            topics=rule_based_topics,
        )
        prompt = self._build_summary_prompt(
            source_context,
            rule_based_clauses,
            rule_based_stakeholders,
            rule_based_topics,
            self._get_prompt_examples("executive summary"),
            self._get_recent_failures("executive summary"),
        )
        parsed = self._call_and_parse_json(
            prompt=prompt,
            expected_keys=["short_summary", "key_points", "recommended_actions"],
            task_name="executive summary",
            schema=self._summary_schema(),
            source_text=source_context,
        )
        if not parsed:
            return {}

        normalized = self._normalize_summary_payload(
            parsed=parsed,
            clauses=rule_based_clauses,
            stakeholders=rule_based_stakeholders,
            topics=rule_based_topics,
        )
        return self._apply_summary_grounding_heuristics(normalized, source_context)

    def verify_extracted_text(self, text: str) -> Dict[str, Any]:
        """
        Verify and normalize extracted document text before analysis.

        Returns a dict with keys:
          verified_text : str
          is_valid      : bool
          notes         : str
        """
        source_text = (text or "").strip()
        if not source_text:
            return {}

        prompt = self._build_text_verification_prompt(source_text)
        parsed = self._call_and_parse_json(
            prompt=prompt,
            expected_keys=["verified_text", "is_valid", "notes"],
            task_name="text verification",
            schema=self._text_verification_schema(),
            source_text=source_text,
        )
        if not parsed:
            return {}

        verified_text = str(parsed.get("verified_text", "")).strip()
        notes = str(parsed.get("notes", "")).strip() or "Text verification completed."
        is_valid_raw = parsed.get("is_valid", True)
        is_valid = bool(is_valid_raw)
        if isinstance(is_valid_raw, str):
            is_valid = is_valid_raw.strip().lower() in {"true", "yes", "1"}

        return {
            "verified_text": verified_text,
            "is_valid": is_valid,
            "notes": notes,
        }

    def clarify_clauses(
        self,
        segments: List[Dict[str, Any]],
        rule_based_clauses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Clarify and enrich detected clauses.

        Returns a list of dicts, each with:
          clause_id   : str
          clause_type : str
          text        : str
          rationale   : str  (enriched LLM explanation)
          confidence  : float
        """
        if not rule_based_clauses:
            return []
        selected_segments = self._select_relevant_segments(
            segments=segments,
            focus_terms=[str(c.get("clause_type", "")) for c in rule_based_clauses],
            max_segments=14,
        )
        source_context = "\n\n".join(
            f"[{s.get('label', '').upper()}] {s.get('text', '')}"
            for s in selected_segments
        )
        prompt = self._build_clause_prompt(
            selected_segments,
            rule_based_clauses,
            self._get_prompt_examples("clause enrichment"),
            self._get_recent_failures("clause enrichment"),
        )
        parsed = self._call_and_parse_json(
            prompt=prompt,
            expected_keys=["clauses"],
            task_name="clause enrichment",
            schema=self._clauses_schema(),
            source_text=source_context,
        )
        if not parsed:
            return []

        clauses = parsed.get("clauses", [])
        if not isinstance(clauses, list):
            return []

        normalized = [self._normalize_clause_payload(c) for c in clauses if isinstance(c, dict)]
        return self._apply_clause_grounding_heuristics(normalized, source_context)

    def analyse_stakeholder_impacts(
        self,
        segments: List[Dict[str, Any]],
        rule_based_stakeholders: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Deepen stakeholder impact analysis with the LLM.

        Returns a list of dicts, each with:
          stakeholder_name : str
          role             : str
          impact_level     : str  (low / medium / high / critical)
          impact_summary   : str  (LLM-generated rich description)
        """
        if not rule_based_stakeholders:
            return []
        focus_terms = [
            str(s.get("stakeholder_name", ""))
            for s in rule_based_stakeholders
            if isinstance(s, dict)
        ]
        selected_segments = self._select_relevant_segments(
            segments=segments,
            focus_terms=focus_terms,
            max_segments=14,
        )
        source_context = "\n\n".join(
            f"[{s.get('label', '').upper()}] {s.get('text', '')}"
            for s in selected_segments
        )
        prompt = self._build_stakeholder_prompt(
            selected_segments,
            rule_based_stakeholders,
            self._get_prompt_examples("stakeholder impact enrichment"),
            self._get_recent_failures("stakeholder impact enrichment"),
        )
        parsed = self._call_and_parse_json(
            prompt=prompt,
            expected_keys=["stakeholders"],
            task_name="stakeholder impact enrichment",
            schema=self._stakeholders_schema(),
            source_text=source_context,
        )
        if not parsed:
            return []

        stakeholders = parsed.get("stakeholders", [])
        if not isinstance(stakeholders, list):
            return []

        normalized = [
            self._normalize_stakeholder_payload(s)
            for s in stakeholders
            if isinstance(s, dict)
        ]
        return self._apply_stakeholder_grounding_heuristics(normalized, source_context)

    # ------------------------------------------------------------------
    # Post-processing normalizers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_summary_payload(
        parsed: Dict[str, Any],
        clauses: List[Dict[str, Any]],
        stakeholders: List[Dict[str, Any]],
        topics: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        short_summary = str(parsed.get("short_summary", "")).strip()
        if len(short_summary) < 40:
            top_topic = str((topics[0] or {}).get("label", "policy")) if topics else "policy"
            short_summary = (
                f"This document focuses on {top_topic} with actionable obligations, "
                "stakeholder impacts, and implementation considerations."
            )

        key_points = [str(p).strip() for p in parsed.get("key_points", []) if str(p).strip()]
        key_points = LLMService._dedupe_keep_order(key_points)

        if len(key_points) < 4:
            top_clause_types = [
                str(c.get("clause_type", "other"))
                for c in clauses[:3]
                if isinstance(c, dict)
            ]
            if top_clause_types:
                key_points.append(
                    "High-signal clause categories detected: "
                    + ", ".join(top_clause_types)
                    + "."
                )

            top_stakeholders = [
                str(s.get("stakeholder_name", "")).strip()
                for s in stakeholders[:3]
                if isinstance(s, dict)
            ]
            top_stakeholders = [s for s in top_stakeholders if s]
            if top_stakeholders:
                key_points.append(
                    "Key stakeholders affected: " + ", ".join(top_stakeholders) + "."
                )

            if topics:
                topic_labels = [
                    str(t.get("label", "")).strip()
                    for t in topics[:3]
                    if isinstance(t, dict)
                ]
                topic_labels = [t for t in topic_labels if t]
                if topic_labels:
                    key_points.append(
                        "Primary thematic areas: " + ", ".join(topic_labels) + "."
                    )

        key_points = LLMService._dedupe_keep_order(key_points)[:6]

        actions = [str(a).strip() for a in parsed.get("recommended_actions", []) if str(a).strip()]
        actions = LLMService._dedupe_keep_order(actions)

        if len(actions) < 3:
            if any(str(c.get("clause_type", "")).lower() in {"obligation", "compliance"} for c in clauses if isinstance(c, dict)):
                actions.append("Create an owner-mapped compliance checklist for obligations and compliance clauses.")
            if any(str(c.get("clause_type", "")).lower() == "deadline" for c in clauses if isinstance(c, dict)):
                actions.append("Build a dated implementation plan with milestones for all deadline-related clauses.")
            if any(str(s.get("impact_level", "")).lower() in {"high", "critical"} for s in stakeholders if isinstance(s, dict)):
                actions.append("Prioritize engagement with high-impact stakeholders before rollout.")

        actions = LLMService._dedupe_keep_order(actions)[:5]

        return {
            "short_summary": short_summary,
            "key_points": key_points,
            "recommended_actions": actions,
        }

    @staticmethod
    def _normalize_clause_payload(item: Dict[str, Any]) -> Dict[str, Any]:
        clause_type = str(item.get("clause_type", "other")).strip().lower() or "other"
        text = str(item.get("text", "")).strip()
        rationale = str(item.get("rationale", "")).strip()

        raw_conf = item.get("confidence", 0.5)
        try:
            confidence = float(raw_conf)
        except Exception:
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        if not rationale and text:
            rationale = f"This {clause_type} clause introduces material policy implications that require review."

        return {
            "clause_id": str(item.get("clause_id", "")).strip(),
            "clause_type": clause_type,
            "text": text,
            "rationale": rationale,
            "confidence": confidence,
        }

    @staticmethod
    def _normalize_stakeholder_payload(item: Dict[str, Any]) -> Dict[str, Any]:
        stakeholder_name = str(item.get("stakeholder_name", "Unknown")).strip() or "Unknown"
        role = str(item.get("role", "other")).strip().lower() or "other"
        impact_level = str(item.get("impact_level", "medium")).strip().lower() or "medium"
        impact_summary = str(item.get("impact_summary", "")).strip()

        if len(impact_summary) < 20:
            impact_summary = (
                f"{stakeholder_name} has {impact_level} expected impact and should "
                "align with the policy's compliance and implementation requirements."
            )

        return {
            "stakeholder_name": stakeholder_name,
            "role": role,
            "impact_level": impact_level,
            "impact_summary": impact_summary,
        }

    # ------------------------------------------------------------------
    # Context optimization and prompt refinement
    # ------------------------------------------------------------------

    def _build_summary_context(
        self,
        text: str,
        clauses: List[Dict[str, Any]],
        stakeholders: List[Dict[str, Any]],
        topics: List[Dict[str, Any]],
    ) -> str:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text or "") if p.strip()]
        if not paragraphs:
            paragraphs = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]

        focus_terms = set()
        for c in clauses[:10]:
            focus_terms.add(str(c.get("clause_type", "")).lower())
            for token in self._tokenize(str(c.get("text", "")))[:8]:
                focus_terms.add(token)
        for s in stakeholders[:8]:
            for token in self._tokenize(str(s.get("stakeholder_name", ""))):
                focus_terms.add(token)
        for t in topics[:6]:
            for token in self._tokenize(str(t.get("label", ""))):
                focus_terms.add(token)

        focus_terms = {t for t in focus_terms if t and len(t) > 2}
        if not paragraphs:
            return textwrap.shorten(text or "", width=self.config.context_budget_chars, placeholder=" [...]")

        scored: List[tuple[str, float]] = []
        for idx, paragraph in enumerate(paragraphs):
            low = paragraph.lower()
            hits = sum(1 for t in focus_terms if t in low)
            policy_cue = 1 if re.search(r"\b(shall|must|compliance|deadline|penalty|regulator|obligation)\b", low) else 0
            position_bonus = max(0.0, 1.0 - (idx / max(len(paragraphs), 1))) * 0.2
            score = hits + policy_cue + position_bonus
            scored.append((paragraph, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        selected: List[str] = []
        running = 0
        for para, _ in scored:
            block = para.strip()
            if not block:
                continue
            new_len = running + len(block) + 2
            if selected and new_len > self.config.context_budget_chars:
                continue
            selected.append(block)
            running = new_len
            if running >= self.config.context_budget_chars:
                break

        if not selected:
            selected = [textwrap.shorten(text or "", width=self.config.context_budget_chars, placeholder=" [...]")]

        return "\n\n".join(selected)

    def _select_relevant_segments(
        self,
        segments: List[Dict[str, Any]],
        focus_terms: List[str],
        max_segments: int,
    ) -> List[Dict[str, Any]]:
        terms = {tok for term in (focus_terms or []) for tok in self._tokenize(str(term)) if len(tok) > 2}
        if not segments:
            return []

        if not terms:
            return segments[:max_segments]

        ranked: List[tuple[Dict[str, Any], float]] = []
        for idx, segment in enumerate(segments):
            text = str(segment.get("text", "")).lower()
            if not text:
                continue
            hits = sum(1 for t in terms if t in text)
            cue_bonus = 1 if re.search(r"\b(shall|must|required|deadline|penalty|stakeholder|impact)\b", text) else 0
            confidence_bonus = float(segment.get("confidence", 0.0) or 0.0)
            score = hits + cue_bonus + confidence_bonus + max(0, 0.15 - idx * 0.005)
            ranked.append((segment, score))

        ranked.sort(key=lambda item: item[1], reverse=True)
        selected = [segment for segment, _ in ranked[:max_segments]]
        return selected or segments[:max_segments]

    def _get_prompt_examples(self, task_name: str) -> List[Dict[str, Any]]:
        base_examples: Dict[str, List[Dict[str, Any]]] = {
            "executive summary": [
                {
                    "input_hint": "Document includes compliance obligations, implementation dates, and affected regulators.",
                    "output_hint": {
                        "short_summary": "The policy establishes enforceable compliance obligations with phased implementation dates and regulator oversight.",
                        "key_points": [
                            "Compliance duties are mandatory and tied to audits.",
                            "Deadlines are phased across implementation periods.",
                            "Regulators and operators bear high implementation burden.",
                        ],
                        "recommended_actions": [
                            "Create a compliance timeline with accountable owners.",
                            "Engage regulators early on enforcement expectations.",
                            "Track evidence artifacts for upcoming audits.",
                        ],
                    },
                }
            ],
            "clause enrichment": [
                {
                    "input_hint": "Clause text: 'Operators shall submit quarterly reports within 30 days.'",
                    "output_hint": {
                        "clause_id": "clause-0001",
                        "clause_type": "deadline",
                        "text": "Operators shall submit quarterly reports within 30 days.",
                        "rationale": "The clause imposes a mandatory reporting requirement with a clear timeline.",
                        "confidence": 0.91,
                    },
                }
            ],
            "stakeholder impact enrichment": [
                {
                    "input_hint": "Stakeholder mention: 'Regulators must review filings and issue compliance notices.'",
                    "output_hint": {
                        "stakeholder_name": "Regulator",
                        "role": "regulator",
                        "impact_level": "high",
                        "impact_summary": "Regulators gain additional review and enforcement workload, requiring faster filing triage and compliance notice workflows.",
                    },
                }
            ],
        }
        examples = base_examples.get(task_name, [])
        return examples[: max(0, self.config.max_prompt_examples)]

    def _get_recent_failures(self, task_name: str) -> List[str]:
        recent = self._prompt_failure_memory.get(task_name, [])
        return recent[-3:]

    def _register_prompt_failure(self, task_name: str, reason: str) -> None:
        bucket = self._prompt_failure_memory.setdefault(task_name, [])
        bucket.append(reason.strip())
        if len(bucket) > 8:
            self._prompt_failure_memory[task_name] = bucket[-8:]

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_summary_prompt(
        self,
        text: str,
        clauses: List[Dict[str, Any]],
        stakeholders: List[Dict[str, Any]],
        topics: List[Dict[str, Any]],
        examples: List[Dict[str, Any]],
        failure_hints: List[str],
    ) -> str:
        truncated = textwrap.shorten(text, width=self.config.context_budget_chars, placeholder=" [...]")
        clause_hints = json.dumps(
            [{"type": c.get("clause_type"), "text": c.get("text", "")[:180]} for c in clauses[:8]],
            indent=2,
        )
        stakeholder_hints = json.dumps(
            [{"name": s.get("stakeholder_name"), "role": s.get("role"), "impact": s.get("impact_level")}
             for s in stakeholders[:6]],
            indent=2,
        )
        topic_hints = json.dumps(
            [{"label": t.get("label"), "confidence": t.get("confidence")} for t in topics[:4]],
            indent=2,
        )
        example_block = json.dumps(examples, indent=2) if examples else "[]"
        failure_block = "\n".join(f"- {f}" for f in failure_hints) if failure_hints else "- none"
        return textwrap.dedent(f"""
            You are an expert policy analyst. Analyse the following government/policy document
            and produce a structured executive summary.

            DOCUMENT TEXT:
            {truncated}

            PRE-DETECTED CLAUSES (rule-based):
            {clause_hints}

            PRE-DETECTED STAKEHOLDERS:
            {stakeholder_hints}

            TOPICS:
            {topic_hints}

            FEW-SHOT EXAMPLES (input style and output quality target):
            {example_block}

            KNOWN FAILURE MODES TO AVOID:
            {failure_block}

            TASK: Respond ONLY with a valid JSON object (no markdown, no extra text) with these keys:
            - "short_summary": A clear 3-5 sentence summary in plain English.
            - "key_points": A list of 4-6 bullet strings (the most important findings).
            - "recommended_actions": A list of 3-5 concrete actionable items for decision-makers.
            Additional constraints:
            - Every key point must be grounded in the provided context.
            - Every action should be operational and role-aware.
        """).strip()

    def _build_text_verification_prompt(self, text: str) -> str:
        truncated = textwrap.shorten(text, width=8000, placeholder=" [...]")
        return textwrap.dedent(f"""
            You are a document quality-verification assistant.

            INPUT TEXT:
            {truncated}

            TASK:
            1. Verify if the extracted text is usable for downstream policy analysis.
            2. Correct obvious extraction artifacts (broken words, repeated headers/footers,
               malformed spacing, OCR noise) without changing factual meaning.
            3. Keep original language and preserve legal/policy intent.

            Respond ONLY with a valid JSON object:
            {{
              "verified_text": "<cleaned and verified text>",
              "is_valid": true,
              "notes": "<short note on corrections performed>"
            }}
        """).strip()

    def _build_clause_prompt(
        self,
        segments: List[Dict[str, Any]],
        clauses: List[Dict[str, Any]],
        examples: List[Dict[str, Any]],
        failure_hints: List[str],
    ) -> str:
        seg_text = "\n\n".join(
            f"[{s.get('label', '').upper()}] {s.get('text', '')}" for s in segments
        )
        seg_text = textwrap.shorten(seg_text, width=self.config.context_budget_chars, placeholder=" [...]")
        clause_list = json.dumps(
            [{"clause_id": c.get("clause_id"), "clause_type": c.get("clause_type"),
              "text": c.get("text", "")[:250], "confidence": c.get("confidence")}
             for c in clauses[:15]],
            indent=2,
        )
        example_block = json.dumps(examples, indent=2) if examples else "[]"
        failure_block = "\n".join(f"- {f}" for f in failure_hints) if failure_hints else "- none"
        return textwrap.dedent(f"""
            You are a legal/policy expert reviewing detected clauses in a government document.

            DOCUMENT SEGMENTS:
            {seg_text}

            DETECTED CLAUSES (rule-based):
            {clause_list}

            FEW-SHOT EXAMPLES:
            {example_block}

            KNOWN FAILURE MODES TO AVOID:
            {failure_block}

            TASK: For each clause:
            1. Confirm or correct the clause_type. Valid types: obligation, prohibition, permission,
               compliance, deadline, definition, penalty, governance, funding, other.
            2. Write a plain-English rationale explaining WHY this clause matters.
            3. Adjust the confidence score (0.0-1.0) based on your assessment.
                4. Keep clause text grounded in or near-verbatim from provided segments.

            Respond ONLY with a valid JSON object (no markdown, no extra text):
            {{
              "clauses": [
                {{"clause_id": "<id>", "clause_type": "<type>", "text": "<text>",
                  "rationale": "<explanation>", "confidence": <float>}},
                ...
              ]
            }}
        """).strip()

    def _build_stakeholder_prompt(
        self,
        segments: List[Dict[str, Any]],
        stakeholders: List[Dict[str, Any]],
        examples: List[Dict[str, Any]],
        failure_hints: List[str],
    ) -> str:
        seg_text = "\n\n".join(
            f"[{s.get('label', '').upper()}] {s.get('text', '')}" for s in segments
        )
        seg_text = textwrap.shorten(seg_text, width=self.config.context_budget_chars, placeholder=" [...]")
        sh_list = json.dumps(
            [{"stakeholder_name": s.get("stakeholder_name"), "role": s.get("role"),
              "impact_level": s.get("impact_level"), "evidence": (s.get("evidence") or [])[:2]}
             for s in stakeholders[:10]],
            indent=2,
        )
        example_block = json.dumps(examples, indent=2) if examples else "[]"
        failure_block = "\n".join(f"- {f}" for f in failure_hints) if failure_hints else "- none"
        return textwrap.dedent(f"""
            You are a policy analyst specialising in stakeholder impact assessment.

            DOCUMENT SEGMENTS:
            {seg_text}

            PRE-DETECTED STAKEHOLDERS (rule-based):
            {sh_list}

            FEW-SHOT EXAMPLES:
            {example_block}

            KNOWN FAILURE MODES TO AVOID:
            {failure_block}

            TASK: For each stakeholder:
            1. Confirm or adjust the role. Valid: government, regulator, private_sector,
               civil_society, academia, public, international_body, other.
            2. Confirm or upgrade the impact_level: low / medium / high / critical.
            3. Write a rich 2-3 sentence impact_summary explaining HOW this stakeholder
               is affected and WHAT they must do or expect.
                4. Keep summaries grounded in document segments; avoid unsupported claims.

            Respond ONLY with a valid JSON object (no markdown, no extra text):
            {{
              "stakeholders": [
                {{"stakeholder_name": "<name>", "role": "<role>",
                  "impact_level": "<level>", "impact_summary": "<description>"}},
                ...
              ]
            }}
        """).strip()

    # ------------------------------------------------------------------
    # Ollama backend
    # ------------------------------------------------------------------

    def _build_client(self):
        """Build and health-check the Ollama client."""
        try:
            import ollama  # type: ignore

            client = ollama.Client(host=self.config.host)
            # Quick connectivity check — list models
            listed = client.list()
            available_model_names = self._extract_model_names(listed)

            if available_model_names and self.config.model not in available_model_names:
                msg = (
                    f"Configured model '{self.config.model}' is not installed in Ollama. "
                    f"Available: {sorted(available_model_names)}"
                )
                if self.config.allow_fallback:
                    logger.warning(f"LLMService: {msg}. Running in fallback mode.")
                    return None
                raise ValueError(msg)

            # Explicit model availability check (handles cases where list parsing is incomplete)
            try:
                if hasattr(client, "show"):
                    client.show(self.config.model)
            except Exception as exc:
                msg = f"Configured model '{self.config.model}' is not available: {exc}"
                if self.config.allow_fallback:
                    logger.warning(f"LLMService: {msg}. Running in fallback mode.")
                    return None
                raise ValueError(msg) from exc

            self._validator_enabled = False
            if self.config.validator_model and self.config.validator_model != self.config.model:
                try:
                    if hasattr(client, "show"):
                        client.show(self.config.validator_model)
                    self._validator_enabled = True
                except Exception as exc:
                    logger.warning(
                        f"LLMService: Validator model '{self.config.validator_model}' unavailable ({exc}); disabling ensemble validation."
                    )
                    self._validator_enabled = False

            logger.info(
                f"LLMService: Ollama connected at {self.config.host} "
                f"(model={self.config.model})"
            )
            return client
        except ImportError:
            msg = "ollama package not installed. Run: uv add ollama"
            if self.config.allow_fallback:
                logger.warning(f"LLMService: {msg}. Running in fallback mode.")
                return None
            raise
        except Exception as exc:
            msg = f"Ollama not reachable at {self.config.host}: {exc}"
            if self.config.allow_fallback:
                logger.warning(f"LLMService: {msg}. Running in fallback mode.")
                return None
            raise ConnectionError(msg) from exc

    def _call_llm(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Optional[str]:
        """Send a prompt to Ollama. Returns raw text or None on failure/fallback."""
        if self._client is None:
            return None

        try:
            fmt: Any = "json"
            if schema and self.config.strict_schema_enforcement:
                fmt = schema
            response = self._client.chat(
                model=model or self.config.model,
                messages=[{"role": "user", "content": prompt}],
                format=fmt,
                options={
                    "temperature": self.config.temperature if temperature is None else temperature,
                    "num_predict": self.config.max_output_tokens,
                },
            )
            return response.message.content
        except Exception as exc:
            if schema and self.config.strict_schema_enforcement:
                try:
                    response = self._client.chat(
                        model=model or self.config.model,
                        messages=[{"role": "user", "content": prompt}],
                        format="json",
                        options={
                            "temperature": self.config.temperature if temperature is None else temperature,
                            "num_predict": self.config.max_output_tokens,
                        },
                    )
                    return response.message.content
                except Exception:
                    pass
            logger.error(f"LLMService: Ollama call failed — {exc}")
            if self.config.allow_fallback:
                return None
            raise

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    def _call_and_parse_json(
        self,
        prompt: str,
        expected_keys: List[str],
        task_name: str,
        schema: Optional[Dict[str, Any]] = None,
        source_text: str = "",
    ) -> Dict[str, Any]:
        """
        2x parsing strategy:
        1) primary generation + parse
        2) optional repair pass that re-parses malformed/partial JSON
        """
        response = self._call_llm(prompt, schema=schema)
        if response is None:
            self._register_prompt_failure(task_name, "Primary generation failed or model unavailable.")
            return {}

        parsed = self._parse_json(response, expected_keys)
        best = parsed
        best_score = self._payload_score(parsed, expected_keys)

        if self._has_sufficient_payload(parsed, expected_keys):
            best = parsed
            best_score = self._payload_score(parsed, expected_keys)
        elif self.config.two_pass_parsing:
            repair_prompt = self._build_json_repair_prompt(
                task_name=task_name,
                raw_output=response,
                expected_keys=expected_keys,
            )
            repaired_response = self._call_llm(repair_prompt, schema=schema)
            if repaired_response is None:
                self._register_prompt_failure(task_name, "Repair pass failed to return output.")
            else:
                repaired = self._parse_json(repaired_response, expected_keys)
                repaired_score = self._payload_score(repaired, expected_keys)
                if repaired_score >= best_score:
                    best = repaired
                    best_score = repaired_score

        if self._validator_enabled and schema and source_text:
            validated = self._cross_check_with_validator_model(
                task_name=task_name,
                candidate=best,
                expected_keys=expected_keys,
                source_text=source_text,
                schema=schema,
            )
            validated_score = self._payload_score(validated, expected_keys)
            if validated_score >= best_score:
                best = validated
                best_score = validated_score

        if best_score == 0:
            self._register_prompt_failure(task_name, "JSON parsing produced empty payload.")
        elif best_score < (1 if len(expected_keys) == 1 else 2):
            self._register_prompt_failure(task_name, "Payload missing required keys or content depth.")

        return best

    def _cross_check_with_validator_model(
        self,
        task_name: str,
        candidate: Dict[str, Any],
        expected_keys: List[str],
        source_text: str,
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self._validator_enabled or self._client is None or not self.config.validator_model:
            return candidate

        candidate_json = json.dumps(candidate or {}, ensure_ascii=False)
        source_snippet = textwrap.shorten(source_text or "", width=2200, placeholder=" [...]")
        keys = ", ".join(expected_keys)

        prompt = textwrap.dedent(f"""
            You are a JSON quality validator for {task_name}.

            SOURCE CONTEXT:
            {source_snippet}

            CANDIDATE JSON:
            {candidate_json}

            TASK:
            - Validate and improve the candidate JSON.
            - Keep content grounded in SOURCE CONTEXT.
            - Ensure keys exist: {keys}
            - Return only one valid JSON object.
        """).strip()

        response = self._call_llm(
            prompt,
            schema=schema,
            model=self.config.validator_model,
            temperature=self.config.validator_temperature,
        )
        if response is None:
            return candidate

        parsed = self._parse_json(response, expected_keys)
        return parsed if parsed else candidate

    @staticmethod
    def _build_json_repair_prompt(task_name: str, raw_output: str, expected_keys: List[str]) -> str:
        keys = ", ".join(expected_keys)
        snippet = textwrap.shorten(raw_output or "", width=5000, placeholder=" [...]")
        return textwrap.dedent(f"""
            You are a strict JSON formatter for {task_name} output.

            ORIGINAL MODEL OUTPUT:
            {snippet}

            TASK:
            - Convert the original output into a single valid JSON object.
            - Keep only relevant information.
            - Ensure the object includes these top-level keys: {keys}
            - Return ONLY JSON (no markdown, no explanation).
        """).strip()

    @staticmethod
    def _summary_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "short_summary": {"type": "string"},
                "key_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "recommended_actions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
            },
            "required": ["short_summary", "key_points", "recommended_actions"],
            "additionalProperties": False,
        }

    @staticmethod
    def _clauses_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "clauses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "clause_id": {"type": "string"},
                            "clause_type": {"type": "string"},
                            "text": {"type": "string"},
                            "rationale": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                        "required": ["clause_id", "clause_type", "text", "rationale", "confidence"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["clauses"],
            "additionalProperties": False,
        }

    @staticmethod
    def _stakeholders_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "stakeholders": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stakeholder_name": {"type": "string"},
                            "role": {"type": "string"},
                            "impact_level": {"type": "string"},
                            "impact_summary": {"type": "string"},
                        },
                        "required": ["stakeholder_name", "role", "impact_level", "impact_summary"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["stakeholders"],
            "additionalProperties": False,
        }

    @staticmethod
    def _text_verification_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "verified_text": {"type": "string"},
                "is_valid": {"type": ["boolean", "string"]},
                "notes": {"type": "string"},
            },
            "required": ["verified_text", "is_valid", "notes"],
            "additionalProperties": False,
        }

    def _apply_summary_grounding_heuristics(
        self,
        payload: Dict[str, Any],
        source_text: str,
    ) -> Dict[str, Any]:
        source_tokens = set(self._tokenize(source_text))
        if not source_tokens:
            return payload

        original_points = [str(p).strip() for p in payload.get("key_points", []) if str(p).strip()]
        original_actions = [str(a).strip() for a in payload.get("recommended_actions", []) if str(a).strip()]

        key_points = []
        for point in payload.get("key_points", []):
            text = str(point).strip()
            if not text:
                continue
            overlap = self._token_overlap_ratio(text, source_tokens)
            if overlap >= self.config.grounding_overlap_threshold or re.search(r"\b(compliance|obligation|deadline|penalty|stakeholder|regulator)\b", text.lower()):
                key_points.append(text)

        actions = []
        for action in payload.get("recommended_actions", []):
            text = str(action).strip()
            if not text:
                continue
            overlap = self._token_overlap_ratio(text, source_tokens)
            if overlap >= (self.config.grounding_overlap_threshold * 0.8) or re.search(r"\b(checklist|timeline|consult|review|audit|implement)\b", text.lower()):
                actions.append(text)

        payload["key_points"] = self._dedupe_keep_order(key_points or original_points)[:6]
        payload["recommended_actions"] = self._dedupe_keep_order(actions or original_actions)[:5]
        return payload

    def _apply_clause_grounding_heuristics(
        self,
        clauses: List[Dict[str, Any]],
        source_text: str,
    ) -> List[Dict[str, Any]]:
        source_low = (source_text or "").lower()
        out: List[Dict[str, Any]] = []
        for clause in clauses:
            text = str(clause.get("text", "")).strip()
            if not text:
                continue
            overlap = self._token_overlap_ratio(text, set(self._tokenize(source_text)))
            appears = text.lower() in source_low
            if not appears and overlap < self.config.grounding_overlap_threshold:
                continue
            if not appears:
                clause["confidence"] = max(0.25, float(clause.get("confidence", 0.5)) * 0.75)
                clause["rationale"] = (
                    f"{str(clause.get('rationale', '')).strip()} Evidence appears inferred from related source wording."
                ).strip()
            out.append(clause)
        return out or clauses

    def _apply_stakeholder_grounding_heuristics(
        self,
        stakeholders: List[Dict[str, Any]],
        source_text: str,
    ) -> List[Dict[str, Any]]:
        source_low = (source_text or "").lower()
        out: List[Dict[str, Any]] = []
        for item in stakeholders:
            name = str(item.get("stakeholder_name", "")).strip()
            summary = str(item.get("impact_summary", "")).strip()
            if not name or not summary:
                continue

            name_grounded = name.lower() in source_low
            summary_overlap = self._token_overlap_ratio(summary, set(self._tokenize(source_text)))
            if not name_grounded and summary_overlap < self.config.grounding_overlap_threshold:
                continue

            out.append(item)
        return out or stakeholders

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-zA-Z][a-zA-Z_\-]{2,}", (text or "").lower())

    @staticmethod
    def _token_overlap_ratio(text: str, source_tokens: set[str]) -> float:
        if not source_tokens:
            return 0.0
        tokens = set(LLMService._tokenize(text))
        if not tokens:
            return 0.0
        overlap = tokens.intersection(source_tokens)
        return len(overlap) / max(len(tokens), 1)

    @staticmethod
    def _payload_score(parsed: Dict[str, Any], expected_keys: List[str]) -> int:
        if not isinstance(parsed, dict):
            return 0
        score = 0
        for key in expected_keys:
            if key not in parsed:
                continue
            value = parsed.get(key)
            if isinstance(value, str):
                if value.strip():
                    score += 1
            elif isinstance(value, list):
                if value:
                    score += 1
            elif isinstance(value, dict):
                if value:
                    score += 1
            elif value is not None:
                score += 1
        return score

    @staticmethod
    def _has_sufficient_payload(parsed: Dict[str, Any], expected_keys: List[str]) -> bool:
        if not parsed:
            return False
        # Require at least 2 non-empty keys for quality, unless only 1 key is expected.
        min_required = 1 if len(expected_keys) == 1 else 2
        return LLMService._payload_score(parsed, expected_keys) >= min_required

    @staticmethod
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        seen = set()
        result: List[str] = []
        for item in items:
            norm = re.sub(r"\s+", " ", item.strip().lower())
            if not norm or norm in seen:
                continue
            seen.add(norm)
            result.append(item.strip())
        return result

    @staticmethod
    def _parse_json(text: str, expected_keys: List[str]) -> Dict[str, Any]:
        """
        Robustly parse JSON from LLM output.
        Handles plain JSON, markdown fences, and minor trailing garbage.
        """
        if not text:
            return {}

        # Strip markdown fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Try to extract first JSON object
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        logger.warning(
            f"LLMService: Could not parse JSON (expected keys: {expected_keys}). "
            f"Snippet: {text[:200]!r}"
        )
        return {}

    @staticmethod
    def _extract_model_names(list_response: Any) -> set[str]:
        """Extract model names from `ollama.Client.list()` across response shapes."""
        names: set[str] = set()
        try:
            models = getattr(list_response, "models", None)
            if models is None and isinstance(list_response, dict):
                models = list_response.get("models", [])

            if not models:
                return names

            for item in models:
                name = None
                if isinstance(item, dict):
                    name = item.get("name")
                else:
                    name = getattr(item, "name", None)

                if name:
                    names.add(str(name).split(":")[0])
                    names.add(str(name))
        except Exception:
            return set()

        return names

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """True when the Ollama client is connected and reachable."""
        return self._client is not None
