from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse


class WebsiteKnowledgeService:
    """Shared website knowledge cache for cross-user acceleration."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.base_dir = project_root / "infrastructure" / "storage" / "outputs" / "website_knowledge"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize_domain(url: str) -> str:
        try:
            host = urlparse(url).hostname or ""
            return host.lower().replace("www.", "", 1)
        except Exception:
            return ""

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256((value or "").strip().encode("utf-8")).hexdigest()

    def _domain_path(self, domain: str) -> Path:
        return self.base_dir / f"{self._hash(domain)}.json"

    def _load_domain(self, domain: str) -> Dict[str, Any]:
        path = self._domain_path(domain)
        if not path.exists():
            return {
                "domain": domain,
                "domain_hash": self._hash(domain),
                "created_at": self._now_iso(),
                "updated_at": self._now_iso(),
                "pages": {},
            }
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {
                "domain": domain,
                "domain_hash": self._hash(domain),
                "created_at": self._now_iso(),
                "updated_at": self._now_iso(),
                "pages": {},
            }

    def _save_domain(self, domain: str, record: Dict[str, Any]) -> str:
        path = self._domain_path(domain)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def lookup(self, url: str) -> Dict[str, Any]:
        domain = self._normalize_domain(url)
        if not domain:
            return {"found": False, "reason": "invalid_url"}

        record = self._load_domain(domain)
        url_hash = self._hash(url)
        pages = record.get("pages") or {}
        exact = pages.get(url_hash)

        similar = []
        for _, page in pages.items():
            if not isinstance(page, dict):
                continue
            similar.append(
                {
                    "url": page.get("url"),
                    "last_seen": page.get("last_seen"),
                    "access_count": page.get("access_count", 0),
                    "summary": page.get("summary"),
                }
            )

        similar = sorted(similar, key=lambda item: item.get("last_seen") or "", reverse=True)[:5]

        return {
            "found": bool(exact),
            "domain": domain,
            "domain_hash": record.get("domain_hash"),
            "exact": exact,
            "similar_pages": similar,
            "page_count": len(pages),
        }

    def upsert(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        domain = self._normalize_domain(url)
        if not domain:
            return {"saved": False, "reason": "invalid_url"}

        record = self._load_domain(domain)
        pages = record.setdefault("pages", {})
        url_hash = self._hash(url)
        previous = pages.get(url_hash) or {}

        pages[url_hash] = {
            "url": url,
            "url_hash": url_hash,
            "first_seen": previous.get("first_seen") or self._now_iso(),
            "last_seen": self._now_iso(),
            "access_count": int(previous.get("access_count") or 0) + 1,
            "summary": payload.get("summary"),
            "metadata": payload.get("metadata") or {},
            "signals": payload.get("signals") or {},
        }

        record["updated_at"] = self._now_iso()
        path = self._save_domain(domain, record)

        return {
            "saved": True,
            "path": path,
            "domain": domain,
            "url_hash": url_hash,
            "page_count": len(record.get("pages") or {}),
        }
