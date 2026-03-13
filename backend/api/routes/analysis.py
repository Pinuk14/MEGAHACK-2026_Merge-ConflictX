from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.pipelines import InsightOutputStorage, InsightStorageConfig
from backend.app.schema import DocumentInsight, ExecutiveSummary, InsightBatch
from backend.app.services import (
    ClauseDetectionService,
    SemanticSegmentationService,
    StakeholderExtractionService,
    TopicClassificationService,
)
from backend.app.services.ollama_service import OllamaService
from backend.app.services.scrape_memory_service import ScrapeMemoryService
from backend.app.services.website_knowledge_service import WebsiteKnowledgeService

router = APIRouter(tags=["analysis"])


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=20, description="Raw policy/research text to analyze")
    document_id: Optional[str] = Field(default=None, description="Optional stable document id")
    source_filename: Optional[str] = Field(default=None, description="Optional source filename")
    persist_output: bool = Field(default=True, description="Persist JSON insight artifacts to outputs directory")
    attachments: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional attachments (base64 or link info)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional page metadata (author, published_time, url, etc.)")
    main_html: Optional[str] = Field(default=None, description="Optional extracted primary content HTML")
    full_html: Optional[str] = Field(default=None, description="Optional full page HTML from extension scrape")


class AnalyzeResponse(BaseModel):
    insight: DocumentInsight
    metrics: Dict[str, Any]
    storage: Optional[Dict[str, Any]] = None


class _SingleDocumentAnalyzer:
    def __init__(self) -> None:
        self.segmentation_service = SemanticSegmentationService()
        self.clause_service = ClauseDetectionService()
        self.stakeholder_service = StakeholderExtractionService()
        self.topic_service = TopicClassificationService()
        self.ollama_service = OllamaService()
        self.memory_service = ScrapeMemoryService(project_root=Path(__file__).resolve().parents[3])
        self.website_knowledge_service = WebsiteKnowledgeService(project_root=Path(__file__).resolve().parents[3])

    @staticmethod
    def _coerce_summary_payload(candidate: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
        short_summary = str(candidate.get("short_summary") or "").strip()
        if len(short_summary) < 20:
            short_summary = str(fallback.get("short_summary") or "").strip()

        key_points = candidate.get("key_points") if isinstance(candidate.get("key_points"), list) else []
        key_points = [str(item).strip() for item in key_points if str(item).strip()][:6]
        if not key_points:
            fb = fallback.get("key_points") if isinstance(fallback.get("key_points"), list) else []
            key_points = [str(item).strip() for item in fb if str(item).strip()][:6]

        recommended_actions = candidate.get("recommended_actions") if isinstance(candidate.get("recommended_actions"), list) else []
        recommended_actions = [str(item).strip() for item in recommended_actions if str(item).strip()][:6]
        if not recommended_actions:
            fb = fallback.get("recommended_actions") if isinstance(fallback.get("recommended_actions"), list) else []
            recommended_actions = [str(item).strip() for item in fb if str(item).strip()][:6]

        return {
            "short_summary": short_summary,
            "key_points": key_points,
            "recommended_actions": recommended_actions,
        }

    @staticmethod
    def _strip_navigation_noise(text: str) -> str:
        if not text:
            return ""

        noise_patterns = [
            r"\bjump to content\b",
            r"\bmain menu\b",
            r"\bdonate\b",
            r"\bcreate account\b",
            r"\blog in\b",
            r"\bcontents\b",
            r"\bhelp with translations\b",
            r"\bparticipate now\b",
            r"\bnavigate_next\b",
            r"\btoggle .* subsection\b",
        ]

        lines = re.split(r"[\r\n]+", text)
        cleaned_lines: List[str] = []
        for line in lines:
            s = re.sub(r"\s+", " ", line).strip()
            if not s:
                continue
            low = s.lower()
            if any(re.search(p, low) for p in noise_patterns):
                continue
            cleaned_lines.append(s)

        return "\n".join(cleaned_lines)

    @staticmethod
    def _strip_ads_and_noise(html: str) -> str:
        """
        Aggressively remove common ad/sponsored/cookie/modal/banner fragments
        and script/style/iframe blocks from HTML before sending to the LLM.
        This is intentionally heuristic: we aim to remove elements whose
        class/id text or visible lines suggest advertising or UI chrome.
        """
        if not html:
            return ""

        # Remove script/style/noscript blocks and HTML comments
        cleaned = re.sub(r"(?is)<script.*?>.*?</script>", "", html)
        cleaned = re.sub(r"(?is)<style.*?>.*?</style>", "", cleaned)
        cleaned = re.sub(r"(?is)<!--.*?-->", "", cleaned)
        cleaned = re.sub(r"(?is)<noscript.*?>.*?</noscript>", "", cleaned)

        # Remove iframes and embeds
        cleaned = re.sub(r"(?is)<iframe.*?>.*?</iframe>", "", cleaned)
        cleaned = re.sub(r"(?is)<embed.*?>.*?</embed>", "", cleaned)

        # Remove elements whose class or id suggests ads/sponsored/promo/modal
        ad_indicator = r"(?:advert|ad-|\bad\b|sponsor|sponsored|promo|banner|paywall|cookie|subscribe|modal|popup|newsletter|related|you-might|recommended|sticky)"
        cleaned = re.sub(
            rf"(?is)<[^>]+(?:class|id)\s*=\s*['\"][^'\"]*{ad_indicator}[^'\"]*['\"][^>]*>.*?</[^>]+>",
            "",
            cleaned,
        )

        # Remove remaining solitary ad-like tags (div/spans) containing ad keywords
        cleaned = re.sub(rf"(?is)<(div|span|section)[^>]*>[^<]{{0,200}}?(?:Advertisement|Sponsored|Promoted|Subscribe|Sign up|You might also like|Related articles|Trending|Popular)[^<]{{0,200}}?</\1>", "", cleaned)

        # Remove inline banners and short lines indicating subscription or paywalls
        cleaned = re.sub(r"(?i)\b(Advertisement|Sponsored|Promoted|Subscribe|Sign up|Cookie settings|Accept cookies|Continue to site)\b", "", cleaned)

        # Collapse whitespace
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Finally filter navigation noise from visible text
        return _SingleDocumentAnalyzer._strip_navigation_noise(cleaned)

    @staticmethod
    def _naive_summary_fallback(text: str, full_html: str) -> Dict[str, Any]:
        source = (text or "").strip() or (full_html or "").strip()
        cleaned = _SingleDocumentAnalyzer._strip_navigation_noise(source)
        cleaned = re.sub(r"\s+", " ", cleaned)
        short = cleaned[:380].strip()
        if len(short) < 20:
            short = "Content loaded, but summary could not be confidently generated yet."

        sentence_chunks = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
        key_points = sentence_chunks[:2] if sentence_chunks else ["Primary content could not be extracted with high confidence."]

        return {
            "short_summary": short,
            "key_points": key_points,
            "recommended_actions": [
                "Refresh analysis if page content changes significantly.",
            ],
        }

    def _llm_html_grounded_summary(
        self,
        text: str,
        main_html: Optional[str],
        full_html: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        primary_html_text = str(main_html or "")
        full_html_text = str(full_html or "")

        # Aggressively strip ads and UI chrome from the HTML we send to the LLM
        cleaned_primary = self._strip_ads_and_noise(primary_html_text)
        cleaned_full = self._strip_ads_and_noise(full_html_text)
        fallback_summary = self._naive_summary_fallback(text, primary_html_text or full_html_text)
        if not full_html_text and not text:
            return fallback_summary

        generation_system = (
            "You are a strict webpage summarizer. Use ONLY the provided page content. "
            "Do not invent facts. Strip advertising, sponsored/promoted content, cookie banners, paywalls, popups, modal dialogs, and related-article lists. "
            "Return JSON with exactly: {\"short_summary\": string, \"key_points\": string[], \"recommended_actions\": string[]}."
        )

        # Prefer the cleaned primary HTML; include cleaned full HTML for context.
        generation_user = json.dumps(
            {
                "url": (metadata or {}).get("url") if isinstance(metadata, dict) else None,
                "title": (metadata or {}).get("title") if isinstance(metadata, dict) else None,
                "primary_html": cleaned_primary or cleaned_full or primary_html_text,
                "full_html": cleaned_full or full_html_text,
                "instruction": "Summarize only the article's main body and important metadata. Remove any ads, banners, navigation, footers, paywalls, promotional or related-item lists. Keep only factual content and extract key points and recommended actions when present.",
            },
            ensure_ascii=False,
        )

        draft = self.ollama_service.generate_json(system_prompt=generation_system, user_prompt=generation_user) or {}
        if not isinstance(draft, dict) or not draft:
            if cleaned_primary or primary_html_text:
                retry_user = json.dumps(
                    {
                        "url": (metadata or {}).get("url") if isinstance(metadata, dict) else None,
                        "title": (metadata or {}).get("title") if isinstance(metadata, dict) else None,
                        "primary_html": cleaned_primary or primary_html_text,
                        "instruction": "Summarize only the primary article body. Remove ads/cookie banners/paywalls and do not include navigation or related-item lists.",
                    },
                    ensure_ascii=False,
                )
                draft = self.ollama_service.generate_json(system_prompt=generation_system, user_prompt=retry_user) or {}
            if not isinstance(draft, dict) or not draft:
                return fallback_summary

        verify_system = (
            "You verify summary claims against webpage content. Remove or rewrite unsupported claims. "
            "Return ONLY JSON with keys short_summary, key_points, recommended_actions."
        )
        verify_user = json.dumps(
            {
                "source_primary_html": primary_html_text,
                "source_full_html": full_html_text,
                "draft_summary": draft,
                "rule": "Keep only claims supported by source content.",
            },
            ensure_ascii=False,
        )
        verified = self.ollama_service.generate_json(system_prompt=verify_system, user_prompt=verify_user)
        chosen = verified if isinstance(verified, dict) and verified else draft
        return self._coerce_summary_payload(chosen, fallback_summary)

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Request text is empty")

        document_id = request.document_id or f"api-{uuid4().hex[:12]}"

        segments = self.segmentation_service.segment_document(
            text=text,
            document_id=document_id,
            source_filename=request.source_filename,
        )
        clauses = self.clause_service.detect_from_segments(segments)
        stakeholders = self.stakeholder_service.extract_from_segments(segments)
        topics = self.topic_service.classify_from_segments(segments)
        grounded_summary = self._llm_html_grounded_summary(
            text=text,
            main_html=request.main_html,
            full_html=request.full_html,
            metadata=request.metadata,
        )
        executive_summary = ExecutiveSummary(
            short_summary=grounded_summary.get("short_summary") or "Content loaded, but summary is unavailable.",
            key_points=grounded_summary.get("key_points") or [],
            recommended_actions=grounded_summary.get("recommended_actions") or [],
        )

        insight = DocumentInsight(
            document_id=document_id,
            source_filename=request.source_filename,
            executive_summary=executive_summary,
            clauses=clauses,
            stakeholders=stakeholders,
            topics=topics,
        )

        metrics = {
            "segments": len(segments),
            "clauses": len(clauses),
            "stakeholders": len(stakeholders),
            "topics": len(topics),
        }

        storage_info: Optional[Dict[str, Any]] = None
        memory_info: Optional[Dict[str, Any]] = None
        website_knowledge_info: Optional[Dict[str, Any]] = None

        # Persist scrape memory keyed by URL hash whenever URL metadata exists.
        page_url = (request.metadata or {}).get("url") if isinstance(request.metadata, dict) else None
        if page_url:
            scraped_payload = {
                "url": page_url,
                "text": request.text,
                "full_html": request.full_html,
                "metadata": request.metadata,
                "attachments": request.attachments,
                "source_filename": request.source_filename,
            }
            memory_ctx = self.memory_service.memory_context(page_url, scraped_payload)
            write = self.memory_service.remember_scrape(page_url, scraped_payload)
            memory_info = {
                "found_previous": memory_ctx.get("found_previous"),
                "content_changed": memory_ctx.get("content_changed"),
                "saved": write.get("saved"),
                "url_hash": write.get("url_hash"),
                "content_hash": write.get("content_hash"),
                "path": write.get("path"),
            }

            existing = self.website_knowledge_service.lookup(page_url)
            knowledge_write = self.website_knowledge_service.upsert(
                page_url,
                {
                    "summary": executive_summary.short_summary if hasattr(executive_summary, "short_summary") else None,
                    "metadata": request.metadata,
                    "signals": {
                        "text_length": len(text),
                        "clauses": len(clauses),
                        "stakeholders": len(stakeholders),
                        "topics": len(topics),
                    },
                },
            )
            website_knowledge_info = {
                "found_existing": existing.get("found"),
                "domain": knowledge_write.get("domain") or existing.get("domain"),
                "saved": knowledge_write.get("saved"),
                "path": knowledge_write.get("path"),
                "page_count": knowledge_write.get("page_count") or existing.get("page_count"),
                "similar_pages": existing.get("similar_pages") or [],
            }

        if request.persist_output:
            project_root = Path(__file__).resolve().parents[3]
            storage = InsightOutputStorage(project_root=project_root, config=InsightStorageConfig())
            batch_path, per_doc_paths = storage.save(InsightBatch(items=[insight]))
            storage_info = {
                "batch_file": str(batch_path),
                "document_files": [str(p) for p in per_doc_paths],
            }
            if memory_info:
                storage_info["memory"] = memory_info
            if website_knowledge_info:
                storage_info["website_knowledge"] = website_knowledge_info

        return AnalyzeResponse(insight=insight, metrics=metrics, storage=storage_info)


_analyzer = _SingleDocumentAnalyzer()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_document(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze one document and return structured insights."""
    return _analyzer.analyze(request)


@router.get("/website_knowledge")
def get_website_knowledge(url: str) -> Dict[str, Any]:
    """Return cached website intelligence for a URL/domain."""
    return _analyzer.website_knowledge_service.lookup(url)
