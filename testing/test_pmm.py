#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - PMM 配付資料ローカル資産管理 単体テスト (test_pmm.py) [Drop 71]
pmm_common, downloader, normalize_folders, cleanup などの関数仕様を単体検証する。
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_DIR = os.path.join(PROJECT_ROOT, "admin")
if ADMIN_DIR not in sys.path:
    sys.path.insert(0, ADMIN_DIR)

from pmm.downloader import sync_local_materials_status
from pmm.pmm_common import (
    sanitize_filename,
    clean_material_name,
    format_meeting_folder_name,
    guess_extension_from_url_or_type,
    get_council_materials_dir,
    get_meeting_dir,
    files_are_identical,
    safe_unlink,
    safe_rmdir,
    safe_move_file,
    COUNCIL_MATERIALS_FOLDER
)


class TestPmmCommonUtilities(unittest.TestCase):
    """PMM 共通ユーティリティ (pmm_common.py) の単体検証"""

    def test_sanitize_filename_invalid_chars(self):
        r"""Windows 禁止文字（\ / : * ? " < > |）が全角に安全置換されること"""
        raw = '資料:第1回*テスト? "重要"<速報>|パイプ/スラッシュ\\円'
        sanitized = sanitize_filename(raw)
        self.assertNotIn(":", sanitized)
        self.assertNotIn("*", sanitized)
        self.assertNotIn("?", sanitized)
        self.assertNotIn('"', sanitized)
        self.assertNotIn("<", sanitized)
        self.assertNotIn(">", sanitized)
        self.assertNotIn("|", sanitized)
        self.assertNotIn("/", sanitized)
        self.assertNotIn("\\", sanitized)
        self.assertIn("：", sanitized)
        self.assertIn("＊", sanitized)
        self.assertIn("？", sanitized)

    def test_clean_material_name_bracket_removal(self):
        """資料名から (PDF: 1.2MB) や [HTML 500KB] などのファイルサイズ・形式注記が削除されること"""
        self.assertEqual(clean_material_name("議事次第 (PDF : 150KB)"), "議事次第")
        self.assertEqual(clean_material_name("資料1 説明資料［PDF形式：1.2MB］"), "資料1 説明資料")
        self.assertEqual(clean_material_name("参考資料2-1 (340KB)"), "参考資料2-1")
        self.assertEqual(clean_material_name("名簿【HTML】"), "名簿")

    def test_format_meeting_folder_name(self):
        """会議フォルダ名が YYYYMMDD_回次 のフォーマットで正規化されること"""
        meeting = {
            "date": "2026/04/15",
            "name": "第24回 総合科学技術・イノベーション会議"
        }
        council_name = "総合科学技術・イノベーション会議"
        folder_name = format_meeting_folder_name(meeting, council_name)
        self.assertEqual(folder_name, "20260415_第24回")

    def test_guess_extension(self):
        """URLおよび資料タイプから適切な拡張子が推定されること"""
        self.assertEqual(guess_extension_from_url_or_type("https://example.com/doc.pdf"), ".pdf")
        self.assertEqual(guess_extension_from_url_or_type("https://example.com/page.html"), ".html")
        self.assertEqual(guess_extension_from_url_or_type("https://example.com/data.xlsx"), ".xlsx")
        self.assertEqual(guess_extension_from_url_or_type("https://example.com/download?id=123", mat_type="PDF"), ".pdf")
        self.assertEqual(guess_extension_from_url_or_type("https://example.com/download?id=123", mat_type="HTML"), ".html")

    def test_council_and_meeting_dirs(self):
        """会議体資料フォルダが 00_会議体資料、開催回フォルダが YYYYMMDD_回次 で解決されること"""
        base = Path("C:/local_docs")
        c_dir = get_council_materials_dir(base, "内閣府", "人工知能戦略会議")
        self.assertTrue(str(c_dir).endswith(os.path.join("内閣府", "人工知能戦略会議", COUNCIL_MATERIALS_FOLDER)))

        meeting = {"date": "2026/05/20", "name": "第5回"}
        m_dir = get_meeting_dir(base, "内閣府", "人工知能戦略会議", meeting)
        self.assertTrue("20260520_第5回" in str(m_dir))

    def test_files_are_identical_and_safe_ops(self):
        """バイナリ比較および Windows ロック解除対応の安全操作の検証"""
        temp_dir = tempfile.mkdtemp()
        try:
            p1 = Path(temp_dir) / "test1.bin"
            p2 = Path(temp_dir) / "test2.bin"
            p3 = Path(temp_dir) / "test3.bin"

            content_a = b"Antigravity PMM Test Content" * 100
            content_b = b"Antigravity PMM Different Content" * 100

            p1.write_bytes(content_a)
            p2.write_bytes(content_a)
            p3.write_bytes(content_b)

            self.assertTrue(files_are_identical(p1, p2))
            self.assertFalse(files_are_identical(p1, p3))

            # safe_move_file
            dst_move = Path(temp_dir) / "test_moved.bin"
            self.assertTrue(safe_move_file(p1, dst_move))
            self.assertFalse(p1.exists())
            self.assertTrue(dst_move.exists())

            # safe_unlink
            self.assertTrue(safe_unlink(dst_move))
            self.assertFalse(dst_move.exists())

            # safe_rmdir
            sub_dir = Path(temp_dir) / "empty_sub"
            sub_dir.mkdir()
            self.assertTrue(safe_rmdir(sub_dir))
            self.assertFalse(sub_dir.exists())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


    def test_sync_local_materials_status(self):
        """sync_local_materials_status が通信なしでローカル格納状況をスキャン・更新できること (Drop 72)"""
        import sqlite3
        temp_dir = tempfile.mkdtemp()
        try:
            temp_db = Path(temp_dir) / "test.db"
            temp_out = Path(temp_dir) / "local_docs"
            temp_out.mkdir()

            # Create test DB schema via schema.sql
            schema_file = Path(PROJECT_ROOT) / "admin" / "db" / "schema.sql"
            conn = sqlite3.connect(str(temp_db))
            conn.executescript(schema_file.read_text(encoding="utf-8"))
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO admin_configs (key, value_json) VALUES
                ('ministries', '{"CAO": {"name": "内閣府"}}');
            """)
            cur.execute("""
                INSERT INTO councils (id, ministry, category, name, official_url, manual_lock)
                VALUES ('cao-ai_hq', 'CAO', 'COUNCIL', '人工知能戦略会議', 'https://example.com', 0);
            """)
            cur.execute("""
                INSERT INTO council_materials (council_id, name, url, type)
                VALUES ('cao-ai_hq', '構成員名簿', 'https://example.com/meibo.pdf', 'PDF');
            """)
            cur.execute("""
                INSERT INTO meetings (id, council_id, name, date, round, manual_lock)
                VALUES ('cao-ai_hq-20260415-024', 'cao-ai_hq', '第24回 人工知能戦略会議', '2026/04/15', 24, 0);
            """)
            cur.execute("""
                INSERT INTO materials (meeting_id, name, url, type)
                VALUES ('cao-ai_hq-20260415-024', '議事次第', 'https://example.com/shisai.pdf', 'PDF');
            """)
            conn.commit()
            conn.close()

            # Place dummy file on disk for meeting material only
            mat_folder = temp_out / "内閣府" / "人工知能戦略会議" / "20260415_第24回"
            mat_folder.mkdir(parents=True)
            dummy_file = mat_folder / "議事次第.pdf"
            dummy_file.write_bytes(b"%PDF-1.4 dummy test content")

            # Execute sync_local_materials_status
            stats = sync_local_materials_status(output_base=temp_out, db_path=temp_db)
            self.assertEqual(stats["matched"], 1)
            self.assertEqual(stats["pending"], 1)
            self.assertEqual(stats["total"], 2)
            self.assertGreater(stats["total_size_bytes"], 0)

            # Check DB updated records
            conn = sqlite3.connect(str(temp_db))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            m_row = cur.execute("SELECT * FROM materials WHERE meeting_id = 'cao-ai_hq-20260415-024';").fetchone()
            self.assertEqual(m_row["download_status"], "downloaded")
            self.assertIsNotNone(m_row["local_path"])
            self.assertIn("内閣府/人工知能戦略会議/20260415_第24回/議事次第.pdf", m_row["local_path"])
            self.assertGreater(m_row["file_size"], 0)

            cm_row = cur.execute("SELECT * FROM council_materials WHERE council_id = 'cao-ai_hq';").fetchone()
            self.assertEqual(cm_row["download_status"], "pending")
            self.assertIsNone(cm_row["local_path"])
            conn.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
