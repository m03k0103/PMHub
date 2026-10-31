"""
register_council.py:
PMHub 標準ワンストップ DB 登録 CLI / API ツール (Drop 115)
会議体、開催回、配付資料、スクレイピングルールを SQLite マスター DB (admin/pmhub.db) へ
手動登録保護 (manual_lock = 1) 付きでアトミックに登録し、2系統エクスポートまで完遂します。
"""

import os
import sys
import json
import sqlite3
import re
import argparse
from datetime import datetime

# プロジェクトルートのパスを sys.path に追加
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from admin.db.export_data import export_data


def validate_council_id(council_id: str) -> bool:
    """会議体IDの規約検証: {省庁略称}-{スラグ} (ハイフン厳格1個・2セグメント)"""
    parts = council_id.split("-")
    if len(parts) != 2:
        return False
    if not parts[0].isalpha() or not parts[1]:
        return False
    return True


def validate_meeting_id(meeting_id: str, council_id: str) -> bool:
    """開催回IDの規約検証: {省庁略称}-{スラグ}-{YYYYMMDD}-{回次3〜4桁またはs+数字2〜3桁} (ハイフン厳格3個・4セグメント)"""
    parts = meeting_id.split("-")
    if len(parts) != 4:
        return False
    if f"{parts[0]}-{parts[1]}" != council_id:
        return False
    if not re.match(r"^\d{8}$", parts[2]):
        return False
    if not re.match(r"^(\d{3,4}|[a-zA-Z]\d{2,3})$", parts[3]):
        return False
    return True


def validate_date(date_str: str) -> bool:
    """日付の規約検証: YYYY/MM/DD (2099/01/01 の禁止)"""
    if not re.match(r"^\d{4}/\d{2}/\d{2}$", date_str):
        return False
    if date_str.startswith("2099"):
        return False
    return True


def register_council_data(
    council_data: dict,
    meetings_data: list,
    rule_data: dict = None,
    auto_export: bool = True,
    db_path: str = None
) -> dict:
    """
    会議体、開催回、配付資料、スクレイピングルールをマスターDBへ一括登録する。
    すべて manual_lock = 1 で保護される。
    """
    if db_path is None:
        db_path = os.path.join(PROJECT_ROOT, "admin", "pmhub.db")

    c_id = council_data.get("id")
    c_name = council_data.get("name")
    c_min = council_data.get("ministry")
    c_url = council_data.get("official_url") or council_data.get("officialUrl")

    if not c_id or not c_name or not c_min or not c_url:
        raise ValueError("council_data must contain 'id', 'name', 'ministry', and 'official_url'")

    if not validate_council_id(c_id):
        raise ValueError(f"Invalid council_id format: '{c_id}'. Must be '{{ministry}}-{{slug}}' with exactly 1 hyphen.")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        # 1. 会議体 (councils) の登録 / 更新
        cur.execute("SELECT id FROM councils WHERE id = ?", (c_id,))
        row = cur.fetchone()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if row:
            cur.execute("""
                UPDATE councils SET 
                    name = ?, ministry = ?, official_url = ?, manual_lock = 1, updated_at = ?
                WHERE id = ?
            """, (c_name, c_min, c_url, now_str, c_id))
            print(f"[COUNCIL UPDATE] {c_id}: {c_name}")
        else:
            cur.execute("""
                INSERT INTO councils (id, name, ministry, official_url, manual_lock, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (c_id, c_name, c_min, c_url, now_str, now_str))
            print(f"[COUNCIL INSERT] {c_id}: {c_name}")

        # 2. スクレイピングルール (scraping_rules) の登録 / 更新 (指定時)
        if rule_data:
            rule_data["manualLock"] = True
            rule_data["officialUrl"] = c_url
            rule_json_str = json.dumps(rule_data, ensure_ascii=False)
            cur.execute("SELECT council_id FROM scraping_rules WHERE council_id = ?", (c_id,))
            if cur.fetchone():
                cur.execute("""
                    UPDATE scraping_rules SET rule_json = ?, updated_at = ? WHERE council_id = ?
                """, (rule_json_str, now_str, c_id))
            else:
                cur.execute("""
                    INSERT INTO scraping_rules (council_id, rule_json, updated_at)
                    VALUES (?, ?, ?)
                """, (c_id, rule_json_str, now_str))
            print(f"[RULE UPDATED] {c_id}")

        # 3. 開催回 (meetings) & 配付資料 (materials) の登録
        ins_meetings = 0
        upd_meetings = 0
        ins_materials = 0

        for m in meetings_data:
            m_id = m.get("id") or m.get("meeting_id")
            m_name = m.get("name") or m.get("title")
            m_date = m.get("date")
            m_url = m.get("official_url") or m.get("officialUrl") or c_url
            mats = m.get("materials", [])

            if not m_id or not m_name or not m_date:
                raise ValueError(f"Meeting missing required fields (id, name, date): {m}")

            if not validate_meeting_id(m_id, c_id):
                raise ValueError(f"Invalid meeting_id format: '{m_id}' for council '{c_id}'")

            if not validate_date(m_date):
                raise ValueError(f"Invalid meeting date format or 2099 placeholder: '{m_date}' in meeting '{m_id}'")

            cur.execute("SELECT id FROM meetings WHERE id = ?", (m_id,))
            m_row = cur.fetchone()

            if m_row:
                cur.execute("""
                    UPDATE meetings SET
                        name = ?, date = ?, official_url = ?, manual_lock = 1, updated_at = ?
                    WHERE id = ?
                """, (m_name, m_date, m_url, now_str, m_id))
                upd_meetings += 1
            else:
                cur.execute("""
                    INSERT INTO meetings (id, council_id, name, date, official_url, manual_lock, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """, (m_id, c_id, m_name, m_date, m_url, now_str, now_str))
                ins_meetings += 1

            # 配付資料の登録 (既存資料の安全な更新・重複URL排除)
            cur.execute("DELETE FROM materials WHERE meeting_id = ?", (m_id,))
            seen_urls = set()
            for mat in mats:
                mat_name = mat.get("name") or mat.get("title")
                mat_url = mat.get("url")
                if not mat_name or not mat_url:
                    continue
                if mat_url in seen_urls:
                    continue
                seen_urls.add(mat_url)

                cur.execute("""
                    INSERT OR REPLACE INTO materials (meeting_id, name, url, manual_lock, created_at)
                    VALUES (?, ?, ?, 1, ?)
                """, (m_id, mat_name, mat_url, now_str))
                ins_materials += 1

        conn.commit()
        print(f"[SUCCESS] Registered for {c_id}: meetings={ins_meetings} new, {upd_meetings} updated; materials={ins_materials}")

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

    # 4. 2系統自動エクスポート同期
    if auto_export:
        print("[EXPORT] Triggering automatic 2-system export...")
        export_data(db_path=db_path)

    return {
        "council_id": c_id,
        "new_meetings": ins_meetings,
        "updated_meetings": upd_meetings,
        "materials": ins_materials
    }


def main():
    parser = argparse.ArgumentParser(description="PMHub One-Stop Council Registration Tool")
    parser.add_argument("json_file", help="Path to input JSON containing council, meetings, and optional rule")
    parser.add_argument("--db", default=None, help="Path to SQLite master database (default: admin/pmhub.db)")
    parser.add_argument("--no-export", action="store_true", help="Skip automatic 2-system export")

    args = parser.parse_args()

    if not os.path.exists(args.json_file):
        print(f"Error: File not found: {args.json_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    council_data = data.get("council")
    meetings_data = data.get("meetings", [])
    rule_data = data.get("rule")

    if not council_data:
        print("Error: Input JSON must have 'council' object", file=sys.stderr)
        sys.exit(1)

    try:
        res = register_council_data(
            council_data=council_data,
            meetings_data=meetings_data,
            rule_data=rule_data,
            auto_export=not args.no_export,
            db_path=args.db
        )
        print("Completed successfully:", res)
    except Exception as e:
        print(f"Registration failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
