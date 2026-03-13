from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class ScrapeMemoryService:
    """Persistent scrape memory keyed by URL hash."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.base_dir = project_root / "infrastructure" / "storage" / "outputs" / "scrape_memory"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def hash_url(url: str) -> str:
        return hashlib.sha256((url or "").strip().encode("utf-8")).hexdigest()

    @staticmethod
    def hash_content(scraped: Dict[str, Any]) -> str:
        # Keep a stable canonical hash from payload JSON
        canonical = json.dumps(scraped or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _record_path(self, url_hash: str) -> Path:
        return self.base_dir / f"{url_hash}.json"

    def load(self, url: str) -> Optional[Dict[str, Any]]:
        if not url:
            return None
        path = self._record_path(self.hash_url(url))
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def remember_scrape(self, url: str, scraped: Dict[str, Any]) -> Dict[str, Any]:
        if not url:
            return {
                "saved": False,
                "reason": "missing_url",
                "found_previous": False,
                "content_changed": None,
            }

        url_hash = self.hash_url(url)
        content_hash = self.hash_content(scraped)
        path = self._record_path(url_hash)

        previous = self.load(url)
        previous_hash = (previous or {}).get("latest", {}).get("content_hash")
        found_previous = previous is not None
        content_changed = previous_hash != content_hash if found_previous else True

        record = {
            "url": url,
            "url_hash": url_hash,
            "created_at": (previous or {}).get("created_at") or self._now_iso(),
            "updated_at": self._now_iso(),
            "latest": {
                "content_hash": content_hash,
                "scraped": scraped,
            },
            "history": (previous or {}).get("history") or [],
        }

        record["history"].append(
            {
                "ts": self._now_iso(),
                "content_hash": content_hash,
            }
        )
        # Keep history bounded
        record["history"] = record["history"][-100:]

        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "saved": True,
            "path": str(path),
            "url_hash": url_hash,
            "content_hash": content_hash,
            "found_previous": found_previous,
            "content_changed": content_changed,
            "previous_content_hash": previous_hash,
        }

    def memory_context(self, url: Optional[str], current_scraped: Dict[str, Any]) -> Dict[str, Any]:
        if not url:
            return {
                "found_previous": False,
                "content_changed": None,
                "previous": None,
            }

        previous = self.load(url)
        if not previous:
            return {
                "found_previous": False,
                "content_changed": None,
                "previous": None,
            }

        current_hash = self.hash_content(current_scraped)
        previous_latest = previous.get("latest") or {}
        previous_hash = previous_latest.get("content_hash")

        return {
            "found_previous": True,
            "content_changed": previous_hash != current_hash,
            "previous": {
                "url_hash": previous.get("url_hash"),
                "updated_at": previous.get("updated_at"),
                "content_hash": previous_hash,
                "scraped": previous_latest.get("scraped"),
            },
        }
