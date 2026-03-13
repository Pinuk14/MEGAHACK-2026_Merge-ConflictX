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
    # If True, connection errors fall back gracefully instead of raising
    allow_fallback: bool = True

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model=os.environ.get("OLLAMA_MODEL", "llama3.2"),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.2")),
            max_output_tokens=int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "2048")),
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
        prompt = self._build_summary_prompt(
            text, rule_based_clauses, rule_based_stakeholders, rule_based_topics
        )
        response = self._call_llm(prompt)
        if response is None:
            return {}
        return self._parse_json(response, ["short_summary", "key_points", "recommended_actions"])

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
        response = self._call_llm(prompt)
        if response is None:
            return {}

        return self._parse_json(response, ["verified_text", "is_valid", "notes"])

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
        prompt = self._build_clause_prompt(segments, rule_based_clauses)
        response = self._call_llm(prompt)
        if response is None:
            return []
        parsed = self._parse_json(response, ["clauses"])
        return parsed.get("clauses", [])

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
        prompt = self._build_stakeholder_prompt(segments, rule_based_stakeholders)
        response = self._call_llm(prompt)
        if response is None:
            return []
        parsed = self._parse_json(response, ["stakeholders"])
        return parsed.get("stakeholders", [])

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_summary_prompt(
        self,
        text: str,
        clauses: List[Dict[str, Any]],
        stakeholders: List[Dict[str, Any]],
        topics: List[Dict[str, Any]],
    ) -> str:
        truncated = textwrap.shorten(text, width=4000, placeholder=" [...]")
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

            TASK: Respond ONLY with a valid JSON object (no markdown, no extra text) with these keys:
            - "short_summary": A clear 3-5 sentence summary in plain English.
            - "key_points": A list of 4-6 bullet strings (the most important findings).
            - "recommended_actions": A list of 3-5 concrete actionable items for decision-makers.
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
    ) -> str:
        seg_text = "\n\n".join(
            f"[{s.get('label', '').upper()}] {s.get('text', '')}" for s in segments[:20]
        )
        seg_text = textwrap.shorten(seg_text, width=3500, placeholder=" [...]")
        clause_list = json.dumps(
            [{"clause_id": c.get("clause_id"), "clause_type": c.get("clause_type"),
              "text": c.get("text", "")[:250], "confidence": c.get("confidence")}
             for c in clauses[:15]],
            indent=2,
        )
        return textwrap.dedent(f"""
            You are a legal/policy expert reviewing detected clauses in a government document.

            DOCUMENT SEGMENTS:
            {seg_text}

            DETECTED CLAUSES (rule-based):
            {clause_list}

            TASK: For each clause:
            1. Confirm or correct the clause_type. Valid types: obligation, prohibition, permission,
               compliance, deadline, definition, penalty, governance, funding, other.
            2. Write a plain-English rationale explaining WHY this clause matters.
            3. Adjust the confidence score (0.0-1.0) based on your assessment.

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
    ) -> str:
        seg_text = "\n\n".join(
            f"[{s.get('label', '').upper()}] {s.get('text', '')}" for s in segments[:20]
        )
        seg_text = textwrap.shorten(seg_text, width=3500, placeholder=" [...]")
        sh_list = json.dumps(
            [{"stakeholder_name": s.get("stakeholder_name"), "role": s.get("role"),
              "impact_level": s.get("impact_level"), "evidence": (s.get("evidence") or [])[:2]}
             for s in stakeholders[:10]],
            indent=2,
        )
        return textwrap.dedent(f"""
            You are a policy analyst specialising in stakeholder impact assessment.

            DOCUMENT SEGMENTS:
            {seg_text}

            PRE-DETECTED STAKEHOLDERS (rule-based):
            {sh_list}

            TASK: For each stakeholder:
            1. Confirm or adjust the role. Valid: government, regulator, private_sector,
               civil_society, academia, public, international_body, other.
            2. Confirm or upgrade the impact_level: low / medium / high / critical.
            3. Write a rich 2-3 sentence impact_summary explaining HOW this stakeholder
               is affected and WHAT they must do or expect.

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

    def _call_llm(self, prompt: str) -> Optional[str]:
        """Send a prompt to Ollama. Returns raw text or None on failure/fallback."""
        if self._client is None:
            return None

        try:
            response = self._client.chat(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_output_tokens,
                },
            )
            return response.message.content
        except Exception as exc:
            logger.error(f"LLMService: Ollama call failed — {exc}")
            if self.config.allow_fallback:
                return None
            raise

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

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
