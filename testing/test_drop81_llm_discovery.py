#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drop 81: Deterministic 1-File Digest & Single-Call LLM Discovery Unit Tests (U21)
=================================================================================
Verifies:
1. Deterministic 1-file digest generation (canonical SHA-256 hash invariance, pre-filters, top-3 similar councils).
2. Anti-hallucination ID-only LLM judgment (unknown IDs ignored, URLs resolved strictly from input digest, 3-stage validation).
3. Call budget enforcement (Daily 3 / Weekly 10 / Monthly 30) and SQLite llm_cache zero-cost cache hits.
4. Newly discovered council ("新着") classification persistence across SQLite DB & export, and protection against premature crawl reset.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ADMIN_DIR = BASE_DIR / "admin"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(ADMIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADMIN_DIR))

from admin.llm.digest import build_discovery_digest
from admin.llm.client import LLMClient
from admin.llm.discovery_judge import judge_discovery_digest

SCHEMA_PATH = ADMIN_DIR / "db" / "schema.sql"


def _init_empty_test_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()


class TestDrop81LlmDiscovery(unittest.TestCase):
    """Unit test suite for Drop 81 (Track [LLM-Assist] Phase 1)."""

    def test_01_deterministic_digest_generation(self):
        """Verify canonical SHA-256 digest invariance and 5-stage deterministic pre-filtering."""
        existing_councils = [
            {
                "id": "meti-ai_strategy_wg",
                "name": "AI産業戦略ワーキンググループ",
                "ministry": "METI",
                "officialUrl": "https://www.meti.go.jp/shingikai/mono_info_service/ai_strategy/index.html",
            },
            {
                "id": "fsa-fin_digital",
                "name": "金融デジタライゼーション検討会",
                "ministry": "FSA",
                "officialUrl": "https://www.fsa.go.jp/singi/digital/index.html",
            },
        ]
        rejected_names = {"却下済みテスト懇談会"}
        rejected_urls = {"https://www.meti.go.jp/press/2026/10/rejected_item.html"}

        raw_items_a = [
            # 1. Valid candidate 1 (METI)
            {
                "title": "「次世代半導体サプライチェーン強靱化検討会」（第1回）を開催します",
                "url": "https://www.meti.go.jp/press/2026/10/20261024001/20261024001.html",
                "date": "2026/10/24",
                "ministry": "METI",
            },
            # 2. Valid candidate 2 (FSA) - similar to fsa-fin_digital
            {
                "title": "「金融デジタル資産リスク管理ワーキング・グループ」の設置について",
                "url": "https://www.fsa.go.jp/news/r8/sonota/20261024_wg.html",
                "date": "2026-10-24",
                "ministry": "FSA",
            },
            # 3. Duplicate of candidate 1
            {
                "title": "「次世代半導体サプライチェーン強靱化検討会」（第1回）を開催します",
                "url": "https://www.meti.go.jp/press/2026/10/20261024001/20261024001.html",
                "date": "2026/10/24",
                "ministry": "METI",
            },
            # 4. Old item before cutoff_date
            {
                "title": "「旧世代エネルギー懇談会」の開催について",
                "url": "https://www.meti.go.jp/press/2026/09/20260901001.html",
                "date": "2026/09/01",
                "ministry": "METI",
            },
            # 5. Existing council session announcement
            {
                "title": "第5回 AI産業戦略ワーキンググループを開催します",
                "url": "https://www.meti.go.jp/shingikai/mono_info_service/ai_strategy/005.html",
                "date": "2026/10/24",
                "ministry": "METI",
            },
            # 6. Rejected council URL
            {
                "title": "却下済みテスト懇談会の開催について",
                "url": "https://www.meti.go.jp/press/2026/10/rejected_item.html",
                "date": "2026/10/24",
                "ministry": "METI",
            },
            # 7. Obvious non-council noise (Minister press conference)
            {
                "title": "経済産業大臣の閣議後記者会見の概要",
                "url": "https://www.meti.go.jp/speeches/kaiken/20261024.html",
                "date": "2026/10/24",
                "ministry": "METI",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_a = Path(tmpdir) / "digest_a.json"
            out_b = Path(tmpdir) / "digest_b.json"

            doc_a = build_discovery_digest(
                raw_items=raw_items_a,
                existing_councils=existing_councils,
                rejected_names=rejected_names,
                rejected_urls=rejected_urls,
                cutoff_date="2026-10-01",
                output_path=out_a,
                save_file=True,
            )
            # Reversed order must produce the exact same canonical hash and IDs
            doc_b = build_discovery_digest(
                raw_items=list(reversed(raw_items_a)),
                existing_councils=existing_councils,
                rejected_names=rejected_names,
                rejected_urls=rejected_urls,
                cutoff_date="2026-10-01",
                output_path=out_b,
                save_file=True,
            )

            self.assertEqual(doc_a["digest_hash"], doc_b["digest_hash"])
            self.assertTrue(out_a.exists())
            self.assertEqual(doc_a["stats"]["candidate_count"], 2)
            self.assertEqual(doc_a["stats"]["filtered_by_dup"], 1)
            self.assertEqual(doc_a["stats"]["filtered_by_date"], 1)
            self.assertEqual(doc_a["stats"]["filtered_by_existing"], 1)
            self.assertEqual(doc_a["stats"]["filtered_by_rejected"], 1)
            self.assertEqual(doc_a["stats"]["filtered_by_noise"], 1)

            # Sorted by ministry: FSA is N001, METI is N002
            self.assertEqual(doc_a["items"][0]["id"], "N001")
            self.assertEqual(doc_a["items"][0]["ministry"], "FSA")
            self.assertTrue(len(doc_a["items"][0]["similar_existing"]) >= 1)
            self.assertEqual(doc_a["items"][0]["similar_existing"][0]["id"], "fsa-fin_digital")
            self.assertEqual(doc_a["items"][1]["id"], "N002")
            self.assertEqual(doc_a["items"][1]["ministry"], "METI")

    def test_02_anti_hallucination_id_only_judgment(self):
        """Verify that judge_discovery_digest resolves URLs strictly from digest item_id and enforces 3-stage validation."""
        digest_doc = {
            "digest_hash": "testhash_02",
            "items": [
                {
                    "id": "N001",
                    "ministry": "METI",
                    "date": "2026-10-24",
                    "title": "「次世代半導体サプライチェーン強靱化検討会」（第1回）を開催します",
                    "url": "https://www.meti.go.jp/press/2026/10/20261024001/20261024001.html",
                    "similar_existing": [],
                },
                {
                    "id": "N002",
                    "ministry": "FSA",
                    "date": "2026-10-24",
                    "title": "「低確信度テスト検討会」について",
                    "url": "https://www.fsa.go.jp/news/r8/low_conf.html",
                    "similar_existing": [],
                },
                {
                    "id": "N003",
                    "ministry": "FSA",
                    "date": "2026-10-24",
                    "title": "「金融デジタライゼーション検討会」（第8回）の開催",
                    "url": "https://www.fsa.go.jp/singi/digital/008.html",
                    "similar_existing": [{"id": "fsa-fin_digital", "name": "金融デジタライゼーション検討会"}],
                },
                {
                    "id": "N004",
                    "ministry": "MOFA",
                    "date": "2026-10-24",
                    "title": "日米政府の戦略的投資に関する会合",
                    "url": "https://www.mofa.go.jp/mofaj/press/release/20261024.html",
                    "similar_existing": [],
                },
            ],
        }

        def mock_responder(prompt, meta):
            return {
                "decisions": [
                    {
                        "item_id": "N001",
                        "is_new_council": True,
                        "council_name": "第1回 次世代半導体サプライチェーン強靱化検討会",
                        "matches_existing_id": None,
                        "category": "STUDY_GROUP",
                        "confidence": 0.94,
                        "reason": "新規設置された検討会の第1回開催告知",
                    },
                    {
                        # Hallucinated unknown ID + injected fake URL field
                        "item_id": "N999",
                        "is_new_council": True,
                        "council_name": "架空ハルシネーション審議会",
                        "url": "https://evil.example.com/fake",
                        "confidence": 0.99,
                    },
                    {
                        # Low confidence (< 0.80)
                        "item_id": "N002",
                        "is_new_council": True,
                        "council_name": "低確信度テスト検討会",
                        "confidence": 0.65,
                    },
                    {
                        # Matches existing council
                        "item_id": "N003",
                        "is_new_council": True,
                        "council_name": "金融デジタライゼーション検討会",
                        "matches_existing_id": "fsa-fin_digital",
                        "confidence": 0.95,
                    },
                    {
                        # International noise caught by post-validator
                        "item_id": "N004",
                        "is_new_council": True,
                        "council_name": "日米政府の戦略的投資に関する会合",
                        "confidence": 0.91,
                    },
                ]
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test_pmhub.db"
            _init_empty_test_db(temp_db)
            client = LLMClient(schedule_tier="daily", db_path=temp_db, mock_responder=mock_responder)
            res = judge_discovery_digest(digest_doc, llm_client=client, min_confidence=0.80)

            self.assertEqual(res["status"], "ok")
            self.assertEqual(res["stats"]["ignored_unknown_id"], 1)
            self.assertEqual(res["stats"]["rejected_low_confidence"], 1)
            self.assertEqual(res["stats"]["rejected_existing_match"], 1)
            self.assertEqual(res["stats"]["rejected_noise"], 1)
            self.assertEqual(len(res["candidates"]), 1)

            cand = res["candidates"][0]
            self.assertEqual(cand["item_id"], "N001")
            # "第1回 " stripped by clean_council_name
            self.assertEqual(cand["name"], "次世代半導体サプライチェーン強靱化検討会")
            # Category alias mapped STUDY_GROUP -> STUDY
            self.assertEqual(cand["category"], "STUDY")
            # URL strictly resolved from input digest N001
            self.assertEqual(cand["url"], "https://www.meti.go.jp/press/2026/10/20261024001/20261024001.html")
            self.assertEqual(cand["discoverySource"], "llm")

    def test_03_budget_enforcement_and_sqlite_cache(self):
        """Verify Daily/Weekly/Monthly call budget limits and SQLite llm_cache hit behavior."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test_budget.db"
            _init_empty_test_db(temp_db)

            call_counter = {"count": 0}

            def mock_responder(prompt, meta):
                call_counter["count"] += 1
                return {"decisions": []}

            client = LLMClient(
                schedule_tier="daily",
                budget_config={"daily": 3, "weekly": 10, "monthly": 30},
                db_path=temp_db,
                mock_responder=mock_responder,
            )

            # Call 1 (uncached)
            r1 = client.generate_structured_json("prompt1", digest_hash="hash_1", purpose="discovery_digest")
            self.assertEqual(r1["status"], "ok")
            self.assertEqual(client.calls_made, 1)

            # Repeat Call 1 with same digest_hash -> served from SQLite llm_cache with 0 new calls
            r1_cached = client.generate_structured_json("prompt1", digest_hash="hash_1", purpose="discovery_digest")
            self.assertEqual(r1_cached["status"], "cached")
            self.assertEqual(client.calls_made, 1)
            self.assertEqual(client.cache_hits, 1)
            self.assertEqual(call_counter["count"], 1)

            # Call 2 & Call 3 (within daily budget of 3)
            r2 = client.generate_structured_json("prompt2", digest_hash="hash_2", purpose="discovery_digest")
            r3 = client.generate_structured_json("prompt3", digest_hash="hash_3", purpose="discovery_digest")
            self.assertEqual(r2["status"], "ok")
            self.assertEqual(r3["status"], "ok")
            self.assertEqual(client.calls_made, 3)

            # Call 4 (exceeds daily budget of 3)
            r4 = client.generate_structured_json("prompt4", digest_hash="hash_4", purpose="discovery_digest")
            self.assertEqual(r4["status"], "budget_exceeded")
            self.assertEqual(client.calls_made, 3)
            self.assertEqual(call_counter["count"], 3)

    def test_04_newly_discovered_council_persistence_and_crawl_protection(self):
        """Verify council is_newly_discovered persistence in DB and protection from immediate crawl reset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test_persist.db"
            _init_empty_test_db(temp_db)

            conn = sqlite3.connect(temp_db)
            with conn:
                # Council A: discovered BEFORE lastCrawlTime -> should be reset on next crawl
                conn.execute(
                    """
                    INSERT INTO councils (id, ministry, category, name, official_url, is_newly_discovered, discovered_at, discovery_source)
                    VALUES ('meti-old_new', 'METI', 'STUDY', '前回発見検討会', 'https://www.meti.go.jp/old', 1, '2026/10/20 10:00', 'rule');
                    """
                )
                # Council B: discovered AFTER lastCrawlTime -> must stay is_newly_discovered=1 during crawl reset
                conn.execute(
                    """
                    INSERT INTO councils (id, ministry, category, name, official_url, is_newly_discovered, discovered_at, discovery_source)
                    VALUES ('meti-fresh_llm', 'METI', 'STUDY', '今回LLM発見検討会', 'https://www.meti.go.jp/fresh', 1, '2026/10/24 15:30', 'llm');
                    """
                )

                prev_last_crawl = "2026/10/24 12:00"
                conn.execute(
                    "UPDATE councils SET is_newly_discovered = 0 WHERE is_newly_discovered = 1 AND (discovered_at IS NULL OR discovered_at = '' OR REPLACE(discovered_at, '-', '/') <= ?);",
                    (prev_last_crawl,),
                )

            cur = conn.cursor()
            row_old = cur.execute("SELECT is_newly_discovered, discovery_source FROM councils WHERE id = 'meti-old_new';").fetchone()
            row_fresh = cur.execute("SELECT is_newly_discovered, discovery_source FROM councils WHERE id = 'meti-fresh_llm';").fetchone()
            conn.close()

            self.assertEqual(row_old[0], 0, "Council discovered before prev_last_crawl should be reset")
            self.assertEqual(row_fresh[0], 1, "Council discovered after prev_last_crawl must remain 新着 (is_newly_discovered=1)")
            self.assertEqual(row_fresh[1], "llm")


if __name__ == "__main__":
    unittest.main()
