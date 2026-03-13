from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class OllamaService:
    """Minimal Ollama client for JSON-only generations."""

    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.timeout_seconds = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
        self.max_retries = int(os.getenv("OLLAMA_MAX_RETRIES", "2"))

    @staticmethod
    def _extract_json_from_text(content: str) -> Optional[Dict[str, Any]]:
        # 1) direct JSON
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # 2) recover first JSON object block
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = content[start:end + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return None
        return None

    def generate_json(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": (
                f"SYSTEM:\n{system_prompt}\n\n"
                f"USER:\n{user_prompt}\n\n"
                "Return valid JSON only."
            ),
            "options": {
                "temperature": 0.1,
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    raw = resp.read().decode("utf-8", errors="ignore")
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
                if attempt >= self.max_retries:
                    # write debug log before returning
                    try:
                        self._write_debug_log(system_prompt, user_prompt, None, None)
                    except Exception:
                        pass
                    return None
                time.sleep(min(2.0, 0.4 * (2 ** attempt)))
                continue

            try:
                outer = json.loads(raw)
            except json.JSONDecodeError:
                if attempt >= self.max_retries:
                    try:
                        self._write_debug_log(system_prompt, user_prompt, raw, None)
                    except Exception:
                        pass
                    return None
                time.sleep(min(2.0, 0.4 * (2 ** attempt)))
                continue

            content = outer.get("response")
            if not isinstance(content, str) or not content.strip():
                if attempt >= self.max_retries:
                    return None
                time.sleep(min(2.0, 0.4 * (2 ** attempt)))
                continue

            parsed = self._extract_json_from_text(content)
            if parsed is not None:
                try:
                    self._write_debug_log(system_prompt, user_prompt, raw, parsed)
                except Exception:
                    pass
                return parsed

            if attempt >= self.max_retries:
                try:
                    self._write_debug_log(system_prompt, user_prompt, raw, None)
                except Exception:
                    pass
                return None
            time.sleep(min(2.0, 0.4 * (2 ** attempt)))

        return None

    def _write_debug_log(self, system_prompt: str, user_prompt: str, raw_response: Optional[str], parsed_json: Optional[Dict[str, Any]]):
        try:
            # Create a compact debug entry and append to a log file under project backend dir
            base = os.getcwd()
            log_dir = os.path.join(base, "backend")
            os.makedirs(log_dir, exist_ok=True)
            path = os.path.join(log_dir, "ollama_debug.log")
            entry = {
                "ts": int(time.time()),
                "model": self.model,
                "system_prompt_preview": (system_prompt or "")[:2000],
                "user_prompt_preview": (user_prompt or "")[:20000],
                "raw_response_preview": (raw_response or "")[:20000],
                "parsed_json": parsed_json or None,
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            # logging must not raise
            return
