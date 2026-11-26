#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic 1-File Digest & Single-Call LLM Discovery 単体テストスイート (test_llm_discovery.py)
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


class TestLlmDiscovery(unittest.TestCase):
    """LLM新着会議体自動発見エンジンの単体テスト"""

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
            {
                "title": "「次世代半導体サプライチェーン強靱化検討会」（第1回）を開催します",
                "url": "https://www.meti.go.jp/press/2026/10/20261024001/20261024001.html",
                "date": "2026/10/24",
                "ministry": "METI",
            },
            {
                "title": "「金融デジタル資産リスク管理ワーキング・グループ」の設置について",
                "url": "https://www.fsa.go.jp/news/r8/sonota/20261024_wg.html",
                "date": "2026-10-24",
                "ministry": "FSA",
            },
            {
                "title": "「次世代半導体サプライチェーン強靱化検討会」（第1回）を開催します",
                "url": "https://www.meti.go.jp/press/2026/10/20261024001/20261024001.html",
                "date": "2026/10/24",
                "ministry": "METI",
            },
            {
                "title": "「旧世代エネルギー懇談会」の開催について",
                "url": "https://www.meti.go.jp/press/2026/09/20260901001.html",
                "date": "2026/09/01",
                "ministry": "METI",
            },
            {
                "title": "第5回 AI産業戦略ワーキンググループを開催します",
                "url": "https://www.meti.go.jp/shingikai/mono_info_service/ai_strategy/005.html",
                "date": "2026/10/24",
                "ministry": "METI",
            },
            {
                "title": "却下済みテスト懇談会の開催について",
                "url": "https://www.meti.go.jp/press/2026/10/rejected_item.html",
                "date": "2026/10/24",
                "ministry": "METI",
            },
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
                        "item_id": "N999",
                        "is_new_council": True,
                        "council_name": "架空ハルシネーション審議会",
                        "url": "https://evil.example.com/fake",
                        "confidence": 0.99,
                    },
                    {
                        "item_id": "N002",
                        "is_new_council": True,
                        "council_name": "低確信度テスト検討会",
                        "confidence": 0.65,
                    },
                    {
                        "item_id": "N003",
                        "is_new_council": True,
                        "council_name": "金融デジタライゼーション検討会",
                        "matches_existing_id": "fsa-fin_digital",
                        "confidence": 0.95,
                    },
                    {
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
            self.assertEqual(cand["name"], "次世代半導体サプライチェーン強靱化検討会")
            self.assertEqual(cand["category"], "STUDY")
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

            r1 = client.generate_structured_json("prompt1", digest_hash="hash_1", purpose="discovery_digest")
            self.assertEqual(r1["status"], "ok")
            self.assertEqual(client.calls_made, 1)

            r1_cached = client.generate_structured_json("prompt1", digest_hash="hash_1", purpose="discovery_digest")
            self.assertEqual(r1_cached["status"], "cached")
            self.assertEqual(client.calls_made, 1)
            self.assertEqual(client.cache_hits, 1)
            self.assertEqual(call_counter["count"], 1)

            r2 = client.generate_structured_json("prompt2", digest_hash="hash_2", purpose="discovery_digest")
            r3 = client.generate_structured_json("prompt3", digest_hash="hash_3", purpose="discovery_digest")
            self.assertEqual(r2["status"], "ok")
            self.assertEqual(r3["status"], "ok")
            self.assertEqual(client.calls_made, 3)

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
                conn.execute(
                    """
                    INSERT INTO councils (id, ministry, category, name, official_url, is_newly_discovered, discovered_at, discovery_source)
                    VALUES ('meti-old_new', 'METI', 'STUDY', '前回発見検討会', 'https://www.meti.go.jp/old', 1, '2026/10/20 10:00', 'rule');
                    """
                )
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

    def test_compute_crawl_anomaly_score(self):
        """Drop 153: 抽出0件・PARTIAL・ページ内最新日付取りこぼし・汎用タイトルの異常スコア算出を検証"""
        from llm.crawl_fallback import compute_crawl_anomaly_score

        # 1. 抽出0件 failed -> +100
        res_zero = compute_crawl_anomaly_score(
            {"id": "c1"}, {"crawlResult": "failed", "totalExtractedMaterials": 0, "subpageMeetings": []}
        )
        self.assertGreaterEqual(res_zero["score"], 100)
        self.assertTrue(res_zero["needs_fallback"])
        self.assertIn("zero_extraction", res_zero["reasons"])

        # 2. 資料0件 PARTIAL -> +60
        res_nomat = compute_crawl_anomaly_score(
            {"id": "c2"}, {"crawlResult": "partial", "totalExtractedMaterials": 0, "subpageMeetings": [{"name": "第1回"}]}
        )
        self.assertGreaterEqual(res_nomat["score"], 60)
        self.assertTrue(res_nomat["needs_fallback"])
        self.assertIn("partial_no_materials", res_nomat["reasons"])

        # 3. ページ上部に既存最新日付より新しい日付があるのに未抽出 -> +45
        res_stale = compute_crawl_anomaly_score(
            {"id": "c3"},
            {"crawlResult": "success", "totalExtractedMaterials": 2, "extractedDates": ["2026/08/01"], "subpageMeetings": []},
            html="<div>最新開催: 令和8年11月20日</div>",
            existing_latest_date="2026/08/01",
        )
        self.assertTrue(res_stale["needs_fallback"])
        self.assertIn("stale_despite_newer_page_date", res_stale["reasons"])

        # 4. 正常会議体 -> 0 (補完不要)
        res_ok = compute_crawl_anomaly_score(
            {"id": "c4"},
            {"crawlResult": "success", "totalExtractedMaterials": 3, "extractedDates": ["2026/11/20"], "subpageMeetings": [{"name": "第5回 検討会"}]},
            html="<div>令和8年11月20日</div>",
            existing_latest_date="2026/11/20",
        )
        self.assertEqual(res_ok["score"], 0)
        self.assertFalse(res_ok["needs_fallback"])

    def test_build_compact_dom_snippet(self):
        """Drop 153: 不要UI除去・連番リンクID付与・文字数上限遵守を検証"""
        from llm.crawl_fallback import build_compact_dom_snippet

        html = """
        <html>
          <head><title>検討会トップ｜省庁</title><script>console.log(1)</script></head>
          <body>
            <header><a href="/home">ホーム</a></header>
            <nav><a href="/sitemap">サイトマップ</a></nav>
            <main>
              <h1>第10回 政策検討会</h1>
              <a href="/council/dai10/index.html">第10回議事次第</a>
              <a href="/council/dai10/siryou1.pdf">資料1 概要</a>
              <p>令和8年11月15日開催。</p>
            </main>
            <footer><a href="/privacy">プライバシー</a></footer>
          </body>
        </html>
        """
        snip = build_compact_dom_snippet(html, "https://example.go.jp/council/", max_chars=800)
        self.assertEqual(snip["title"], "検討会トップ｜省庁")
        self.assertIn("第10回 政策検討会", snip["headings"])
        link_texts = [l["text"] for l in snip["links"]]
        self.assertIn("第10回議事次第", link_texts)
        self.assertIn("資料1 概要", link_texts)
        self.assertNotIn("サイトマップ", link_texts)
        self.assertNotIn("プライバシー", link_texts)
        self.assertIn("L01", snip["links_by_id"])
        self.assertEqual(snip["links_by_id"]["L01"]["url"], "https://example.go.jp/council/dai10/index.html")
        self.assertTrue(snip["links_by_id"]["L02"]["is_pdf"])

    def test_batched_llm_crawl_fallback_cache_budget_and_hallucination_guard(self):
        """Drop 153: 5件バッチ集約・link_idハルシネーション遮断・llm_cacheヒット・予算上限遵守を検証"""
        from llm.crawl_fallback import build_compact_dom_snippet, run_batched_llm_crawl_fallback

        entries = []
        for idx in range(5):
            html = f"<html><body><h1>検討会{idx}</h1><a href='/c{idx}/dai1.html'>第1回</a><a href='/c{idx}/m1.pdf'>資料1</a></body></html>"
            entries.append({
                "council_id": f"test-c{idx}",
                "name": f"テスト検討会{idx}",
                "url": f"https://example.go.jp/c{idx}/index.html",
                "existing_latest_date": "",
                "score": 100 - idx,
                "reasons": ["zero_extraction"],
                "snippet": build_compact_dom_snippet(html, f"https://example.go.jp/c{idx}/index.html"),
            })

        def fake_responder(prompt, ctx):
            out = []
            for item in ctx["councils"]:
                cid = item["council_id"]
                out.append({
                    "council_id": cid,
                    "meetings": [{
                        "date": "2026/11/20",
                        "title": f"第1回 {item['name']}",
                        "subpage_link_id": "L01",
                        "material_link_ids": ["L02", "L99_HALLUCINATED"]
                    }]
                })
            # 架空会議体IDの注入も遮断されること
            out.append({"council_id": "hallucinated-cid", "meetings": [{"date": "2026/11/20", "title": "偽", "material_link_ids": ["L01"]}]})
            return {"results": out}

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_llm.db"
            client1 = LLMClient(schedule_tier="weekly", budget_config={"weekly": 1}, db_path=db_path, mock_responder=fake_responder)
            res1 = run_batched_llm_crawl_fallback(entries, llm_client=client1, batch_size=5)
            self.assertEqual(res1["stats"]["batches"], 1)
            self.assertEqual(res1["stats"]["llm_calls"], 1)
            self.assertEqual(res1["stats"]["resolved_councils"], 5)
            self.assertNotIn("hallucinated-cid", res1["results_by_council"])

            c0_mats = res1["results_by_council"]["test-c0"]["materials"]
            self.assertEqual(len(c0_mats), 1)
            self.assertEqual(c0_mats[0]["url"], "https://example.go.jp/c0/m1.pdf")

            # 2回目同一バッチは SQLite llm_cache ヒットで API コール 0 回
            client2 = LLMClient(schedule_tier="weekly", budget_config={"weekly": 1}, db_path=db_path, mock_responder=fake_responder)
            res2 = run_batched_llm_crawl_fallback(entries, llm_client=client2, batch_size=5)
            self.assertEqual(res2["stats"]["cache_hits"], 1)
            self.assertEqual(res2["stats"]["llm_calls"], 0)
            self.assertEqual(res2["stats"]["resolved_councils"], 5)

            # 予算上限 (budget=0) で別バッチを呼ぶと budget_exceeded で安全停止
            entries_other = [dict(entries[0], council_id="test-c9")]
            client3 = LLMClient(schedule_tier="weekly", budget_config={"weekly": 0}, db_path=db_path, mock_responder=fake_responder)
            res3 = run_batched_llm_crawl_fallback(entries_other, llm_client=client3, batch_size=5)
            self.assertEqual(res3["stats"]["status"], "budget_exceeded")
            self.assertEqual(res3["stats"]["llm_calls"], 0)

    def test_diagnose_rules_classification(self):
        """Drop 153: diagnose_rules.classify_council_issue の障害分類・推奨テンプレート判定を検証"""
        tools_dir = ADMIN_DIR / "tools"
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        import diagnose_rules

        d_warp = diagnose_rules.classify_council_issue(
            {"id": "meti-w", "ministry": "METI", "name": "過去", "official_url": "https://warp.ndl.go.jp/web/1/index.html"},
            {"result": "failed", "failure_reason": "WAF 202 Challenge"},
            {"template": "tpl-parent-table-direct"},
        )
        self.assertEqual(d_warp["category"], "warp_archive")

        d_waf = diagnose_rules.classify_council_issue(
            {"id": "meti-s", "ministry": "METI", "name": "通常", "official_url": "https://www.meti.go.jp/shingi/1.html"},
            {"result": "failed", "failure_reason": "WAF Blocked Skip (Ministry METI)"},
            {"template": "tpl-general-round-subpage"},
        )
        self.assertEqual(d_waf["category"], "waf_legacy_skip")

        d_tpl = diagnose_rules.classify_council_issue(
            {"id": "mhlw-x", "ministry": "MHLW", "name": "部会", "official_url": "https://www.mhlw.go.jp/stf/shingi/1.html"},
            {"result": "failed", "failure_reason": "配付資料・開催日・個別開催回のいずれも検出できませんでした"},
            {"template": "tpl-parent-table-direct"},
        )
        self.assertEqual(d_tpl["category"], "template_mismatch")
        self.assertEqual(d_tpl["recommended_template"], "tpl-mhlw-stf-subpage")

        d_part = diagnose_rules.classify_council_issue(
            {"id": "cas-x", "ministry": "CAS", "name": "会議", "official_url": "https://www.cas.go.jp/jp/seisaku/test/index.html"},
            {"result": "partial", "result_reason": "開催回 1 件を検出したが資料が0件"},
            {"template": "tpl-ministry-hybrid-kaisai"},
        )
        self.assertEqual(d_part["category"], "zero_material_partial")


if __name__ == "__main__":
    unittest.main()
