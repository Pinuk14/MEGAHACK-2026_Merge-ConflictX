from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SemanticSegmentationConfig:
    """Configuration for document semantic segmentation."""

    min_segment_chars: int = 120
    max_segment_chars: int = 1800
    merge_similarity_threshold: float = 0.28


class SemanticSegmentationService:
    """
    Rule-based semantic segmentation for policy/research/government documents.

    This service creates semantically meaningful sections from raw text by:
    1) splitting into paragraph blocks with character offsets,
    2) classifying each block into a semantic label,
    3) merging neighboring blocks when they are semantically similar.
    """

    _SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

    # Headings commonly found in policy/research papers
    _HEADING_HINTS = {
        "executive summary",
        "introduction",
        "background",
        "scope",
        "objective",
        "objectives",
        "methodology",
        "findings",
        "analysis",
        "recommendation",
        "recommendations",
        "conclusion",
        "implementation",
        "governance",
        "compliance",
        "annex",
        "appendix",
    }

    # Lightweight topic cues used for segment labels
    _LABEL_KEYWORDS: Dict[str, set[str]] = {
        "obligation": {"shall", "must", "required", "requirement", "mandatory"},
        "prohibition": {"shall not", "must not", "prohibited", "forbidden", "ban"},
        "compliance": {"compliance", "audit", "enforcement", "penalty", "violation"},
        "funding": {"budget", "fund", "funding", "grant", "allocation", "finance"},
        "timeline": {"deadline", "timeline", "within", "no later than", "effective date"},
        "definition": {"means", "defined as", "for the purpose of", "definition"},
        "stakeholder_impact": {"agency", "ministry", "citizens", "industry", "stakeholder"},
    }

    def __init__(self, config: Optional[SemanticSegmentationConfig] = None) -> None:
        self.config = config or SemanticSegmentationConfig()

    def segment_document(
        self,
        text: str,
        document_id: str,
        source_filename: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Segment a single document text into semantic segments."""
        normalized = (text or "").strip()
        if not normalized:
            return []

        paragraph_blocks = self._split_paragraph_blocks(normalized)
        raw_segments: List[Dict[str, Any]] = []

        for i, (para_text, start_char, end_char) in enumerate(paragraph_blocks, start=1):
            label = self._classify_block(para_text)
            raw_segments.append(
                {
                    "segment_id": f"{document_id}-seg-{i:03d}",
                    "document_id": document_id,
                    "source_filename": source_filename,
                    "segment_index": i - 1,
                    "label": label,
                    "text": para_text,
                    "start_char": start_char,
                    "end_char": end_char,
                    "word_count": len(para_text.split()),
                    "sentence_count": len([s for s in self._SENTENCE_SPLIT_RE.split(para_text) if s.strip()]),
                }
            )

        merged_segments = self._merge_neighbor_segments(raw_segments)

        # Re-index after merge for deterministic ordering and IDs
        for idx, seg in enumerate(merged_segments, start=1):
            seg["segment_index"] = idx - 1
            seg["segment_id"] = f"{document_id}-seg-{idx:03d}"

        return merged_segments

    def segment_record(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Segment a cleaned/merged record from the existing pipeline."""
        text = str(record.get("content", ""))
        document_id = str(record.get("id", "unknown"))
        source_filename = record.get("title") or record.get("source")
        return self.segment_document(text=text, document_id=document_id, source_filename=source_filename)

    def segment_records(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Segment a batch of records and return segments + statistics."""
        all_segments: List[Dict[str, Any]] = []
        per_doc_counts: Dict[str, int] = {}

        for record in records:
            doc_id = str(record.get("id", "unknown"))
            segments = self.segment_record(record)
            per_doc_counts[doc_id] = len(segments)
            all_segments.extend(segments)

        stats = {
            "documents_processed": len(records),
            "segments_generated": len(all_segments),
            "avg_segments_per_document": (len(all_segments) / len(records)) if records else 0.0,
            "segments_per_document": per_doc_counts,
        }
        return all_segments, stats

    def _split_paragraph_blocks(self, text: str) -> List[Tuple[str, int, int]]:
        """Split document text by blank lines while preserving char offsets."""
        blocks: List[Tuple[str, int, int]] = []

        # Keep blocks including single-line headings; split on blank lines
        pattern = re.compile(r"\n\s*\n+")
        current = 0
        for m in pattern.finditer(text):
            chunk = text[current:m.start()].strip()
            if chunk:
                start_idx = text.find(chunk, current)
                end_idx = start_idx + len(chunk)
                blocks.append((chunk, start_idx, end_idx))
            current = m.end()

        tail = text[current:].strip()
        if tail:
            start_idx = text.find(tail, current)
            end_idx = start_idx + len(tail)
            blocks.append((tail, start_idx, end_idx))

        # Fallback: if no paragraph breaks, split by sentence windows
        if not blocks:
            sentences = [s.strip() for s in self._SENTENCE_SPLIT_RE.split(text) if s.strip()]
            if not sentences:
                return []

            buffer: List[str] = []
            cursor = 0
            for sentence in sentences:
                candidate = (" ".join(buffer + [sentence])).strip()
                if buffer and len(candidate) > self.config.max_segment_chars:
                    chunk = " ".join(buffer).strip()
                    start_idx = text.find(chunk, cursor)
                    end_idx = start_idx + len(chunk)
                    blocks.append((chunk, start_idx, end_idx))
                    cursor = end_idx
                    buffer = [sentence]
                else:
                    buffer.append(sentence)

            if buffer:
                chunk = " ".join(buffer).strip()
                start_idx = text.find(chunk, cursor)
                end_idx = start_idx + len(chunk)
                blocks.append((chunk, start_idx, end_idx))

        return blocks

    def _classify_block(self, block_text: str) -> str:
        """Assign a semantic label to a block using heading and keyword cues."""
        text = block_text.strip()
        lowered = text.lower()

        if self._looks_like_heading(text):
            return "heading"

        scores: Dict[str, int] = {}
        for label, keywords in self._LABEL_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in lowered)
            if score > 0:
                scores[label] = score

        if not scores:
            return "narrative"

        return max(scores.items(), key=lambda kv: kv[1])[0]

    def _looks_like_heading(self, text: str) -> bool:
        """Heuristic for detecting section headings."""
        normalized = text.strip().lower().strip(":")

        if normalized in self._HEADING_HINTS:
            return True

        # numbered headings: "1.", "2.3", "Section 4"
        numbered = re.match(r"^(section\s+)?\d+(\.\d+)*[\).:-]?\s+[a-z]", normalized)
        if numbered and len(text.split()) <= 14:
            return True

        # short title-cased lines are often headings
        if len(text) <= 100 and len(text.split()) <= 12 and text == text.title():
            return True

        return False

    def _merge_neighbor_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge adjacent segments when they share labels and lexical similarity."""
        if not segments:
            return []

        merged: List[Dict[str, Any]] = [segments[0].copy()]

        for current in segments[1:]:
            previous = merged[-1]

            can_merge = (
                previous["label"] == current["label"]
                and (len(previous["text"]) + len(current["text"])) <= self.config.max_segment_chars
                and self._jaccard_similarity(previous["text"], current["text"])
                >= self.config.merge_similarity_threshold
            )

            # Always merge very short fragments into previous when possible
            if not can_merge and len(current["text"]) < self.config.min_segment_chars:
                can_merge = (len(previous["text"]) + len(current["text"])) <= self.config.max_segment_chars

            if can_merge:
                previous["text"] = f"{previous['text']}\n\n{current['text']}"
                previous["end_char"] = current["end_char"]
                previous["word_count"] = len(previous["text"].split())
                previous["sentence_count"] = len(
                    [s for s in self._SENTENCE_SPLIT_RE.split(previous["text"]) if s.strip()]
                )
            else:
                merged.append(current.copy())

        return merged

    @staticmethod
    def _jaccard_similarity(a: str, b: str) -> float:
        """Compute lexical Jaccard similarity between token sets."""
        tokenize = lambda t: set(re.findall(r"[a-z0-9]+", t.lower()))
        set_a = tokenize(a)
        set_b = tokenize(b)

        if not set_a or not set_b:
            return 0.0

        inter = len(set_a & set_b)
        union = len(set_a | set_b)
        return inter / union if union else 0.0
