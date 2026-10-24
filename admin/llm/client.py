#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Budgeted & Cached LLM Client (admin/llm/client.py)
==================================================
Manages structured JSON calls to Gemini with:
1. Per-run call budget enforcement (Daily: 3, Weekly: 10, Monthly: 30)
2. SQLite llm_cache lookup/storage keyed by SHA-256 digest_hash
3. 429 Quota circuit breaker
4. Deterministic mock_responder injection for unit tests
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "pmhub.db"

DEFAULT_LLM_BUDGET: Dict[str, int] = {
    "daily": 3,
    "weekly": 10,
    "monthly": 30,
}


class LLMClient:
    """
    Budget-aware, cache-backed LLM client for discovery and crawl assistance.
    """

    def __init__(
        self,
        schedule_tier: str = "daily",
        budget_config: Optional[Dict[str, int]] = None,
        db_path: Path = DEFAULT_DB_PATH,
        mock_responder: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
    ):
        self.schedule_tier = (schedule_tier or "daily").lower()
        merged_budget = dict(DEFAULT_LLM_BUDGET)
        if isinstance(budget_config, dict):
            for k, v in budget_config.items():
                if k in merged_budget and isinstance(v, int) and v >= 0:
                    merged_budget[k] = v
        self.budget_config = merged_budget
        self.max_calls = self.budget_config.get(self.schedule_tier, DEFAULT_LLM_BUDGET["daily"])
        self.calls_made = 0
        self.cache_hits = 0
        self.quota_blocked = False
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.mock_responder = mock_responder

    def _ensure_cache_table(self) -> None:
        if not self.db_path or not self.db_path.parent.exists():
            return
        try:
            conn = sqlite3.connect(str(self.db_path))
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS llm_cache (
                        digest_hash TEXT PRIMARY KEY,
                        purpose TEXT NOT NULL,
                        response_json TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            conn.close()
        except Exception:
            pass

    def get_cached_response(self, digest_hash: str, purpose: str = "discovery") -> Optional[Dict[str, Any]]:
        """Return cached JSON response for digest_hash if present in llm_cache."""
        if not digest_hash or not self.db_path or not self.db_path.exists():
            return None
        try:
            self._ensure_cache_table()
            conn = sqlite3.connect(str(self.db_path))
            cur = conn.cursor()
            row = cur.execute(
                "SELECT response_json FROM llm_cache WHERE digest_hash = ? AND purpose = ?;",
                (digest_hash, purpose),
            ).fetchone()
            conn.close()
            if row and row[0]:
                return json.loads(row[0])
        except Exception as e:
            print(f"[WARN] LLM cache read error: {e}", file=sys.stderr)
        return None

    def save_cached_response(self, digest_hash: str, purpose: str, response_data: Dict[str, Any]) -> None:
        """Save structured JSON response to llm_cache."""
        if not digest_hash or not self.db_path:
            return
        try:
            self._ensure_cache_table()
            conn = sqlite3.connect(str(self.db_path))
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO llm_cache (digest_hash, purpose, response_json) VALUES (?, ?, ?);",
                    (digest_hash, purpose, json.dumps(response_data, ensure_ascii=False)),
                )
            conn.close()
        except Exception as e:
            print(f"[WARN] LLM cache write error: {e}", file=sys.stderr)

    def can_call(self) -> bool:
        """Return True if within call budget and not quota-blocked."""
        return (not self.quota_blocked) and (self.calls_made < self.max_calls)

    def generate_structured_json(
        self,
        prompt: str,
        digest_hash: str = "",
        purpose: str = "discovery",
        context_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a structured JSON LLM request with cache lookup and budget guard.
        Returns dict with keys:
          - status: 'ok' | 'cached' | 'budget_exceeded' | 'quota_blocked' | 'unavailable' | 'error'
          - data: parsed JSON dict (or empty dict)
        """
        # 1. Check cache first (does not consume call budget)
        if digest_hash:
            cached = self.get_cached_response(digest_hash, purpose=purpose)
            if isinstance(cached, dict):
                self.cache_hits += 1
                return {"status": "cached", "data": cached}

        # 2. Check circuit breaker and budget
        if self.quota_blocked:
            return {"status": "quota_blocked", "data": {}}
        if self.calls_made >= self.max_calls:
            return {"status": "budget_exceeded", "data": {}}

        # 3. Execute via mock_responder if injected (for deterministic testing)
        if self.mock_responder is not None:
            self.calls_made += 1
            try:
                resp_data = self.mock_responder(prompt, context_meta or {})
                if isinstance(resp_data, dict) and digest_hash:
                    self.save_cached_response(digest_hash, purpose, resp_data)
                return {"status": "ok", "data": resp_data if isinstance(resp_data, dict) else {}}
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    self.quota_blocked = True
                    return {"status": "quota_blocked", "data": {}, "error": str(e)}
                return {"status": "error", "data": {}, "error": str(e)}

        # 4. Execute via Gemini API
        try:
            from crawler import get_gemini_model
        except ImportError:
            from admin.crawler import get_gemini_model

        model = get_gemini_model()
        if not model:
            return {"status": "unavailable", "data": {}}

        self.calls_made += 1
        try:
            response = model.generate_content(prompt)
            raw_text = (response.text or "").strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                if digest_hash:
                    self.save_cached_response(digest_hash, purpose, parsed)
                return {"status": "ok", "data": parsed}
            return {"status": "error", "data": {}, "error": "Response is not a JSON object"}
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "resourceexhausted" in err_str.lower():
                self.quota_blocked = True
                print("[WARN] Gemini API 429 Quota Exceeded detected in LLMClient. Circuit breaker tripped.", file=sys.stderr)
                return {"status": "quota_blocked", "data": {}, "error": err_str}
            print(f"[WARN] LLMClient call failed: {e}", file=sys.stderr)
            return {"status": "error", "data": {}, "error": err_str}
