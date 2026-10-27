#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
admin/cleanup_nav_meetings.py
=============================
Drop 16 (CR-22) & Drop 99: 既存データ内共通ナビ・常設資料ゴミ開催回の全件クリーンアップ (Clean and Repair)

docs/data.json 内に混入している共通ナビゲーション、広報リンク、組織常設資料（設置要綱・委員名簿等）の
ゴミ開催回を一括スキャンし、安全に削除してマスターデータの整合性を回復する。
特定省庁・特定会議体の除外設定は SQLite マスターDB（admin_configs / scraping_rules）から動的参照する。
"""

import os
import sys
import json
import re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ADMIN_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(ADMIN_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if ADMIN_DIR not in sys.path:
    sys.path.insert(0, ADMIN_DIR)

from crawler import (
    DATA_JSON_FILE,
    ADMIN_DATA_FILE,
    save_data_json_with_backup,
    COMMON_NAV_KEYWORDS,
    ORGANIZATION_DOC_KEYWORDS,
    GENERIC_TITLE_KEYWORDS,
    NAV_EXCLUDE_TEXTS,
    is_generic_title_text,
    _MINISTRY_EXCLUSIONS_MAP
)


def _is_ministry_excluded_title(text, ministry=None):
    """省庁別除外タイトルキーワード（admin_configs.ministries）に一致するかを判定"""
    if ministry:
        m_cfg = _MINISTRY_EXCLUSIONS_MAP.get(ministry.upper(), {})
        return any(kw in text for kw in m_cfg.get("exclude_title_keywords", ()))
    for m_cfg in _MINISTRY_EXCLUSIONS_MAP.values():
        for kw in m_cfg.get("exclude_title_keywords", ()):
            if kw in text:
                return True
    return False


def is_junk_meeting(m, council_ministry_map=None):
    """開催回が共通ナビ・広報・組織常設資料のゴミデータであるかを厳格に判定する"""
    name = (m.get("name") or "").strip()
    cid = m.get("councilId", "")
    ministry = (council_ministry_map or {}).get(cid) or (cid.split("-")[0].upper() if "-" in cid else None)

    # 開催日不明ラベルや番号プレフィックスを除去したコアタイトル
    name_clean = re.sub(r'\s*\([^\)]*開催日不明[^\)]*\)$', '', name).strip()
    name_clean = re.sub(r'^[0-9０-９一二三四五六七八九十]+[．.、\s]+', '', name_clean).strip()

    # 1. 組織常設資料（会議体資料であり個別の開催回ではない）
    if any(k in name_clean for k in ORGANIZATION_DOC_KEYWORDS) or any(k in name for k in ['報告書', '活動状況', '視察概要', '名簿']):
        if not re.search(r'第\s*\d+\s*回', name):
            return True, f"組織常設資料・報告書等（{name}）"

    # 2. 共通ナビゲーション・広報リンク・UI操作テキスト・省庁別除外キーワード
    if (
        any(k in name_clean for k in COMMON_NAV_KEYWORDS) or
        any(k in name for k in ['メニュー開閉', '政策情報（会議・統計等）', '会議・委員会等']) or
        _is_ministry_excluded_title(name_clean, ministry=ministry)
    ):
        if not re.search(r'第\s*\d+\s*回', name):
            return True, f"共通ナビ・広報・UIリンク（{name}）"

    if name_clean in NAV_EXCLUDE_TEXTS or name in NAV_EXCLUDE_TEXTS or name_clean in ('２０２６年', '1.経緯'):
        if not re.search(r'第\s*\d+\s*回', name):
            return True, f"除外アンカーテキスト一致（{name}）"

    # 3. 日付不明かつジェネリックタイトル（親会議体名そのまま + 開催日不明等）
    if m.get("isDateUnconfirmed") or m.get("date") == "2099/01/01":
        if any(kw == name_clean or kw in name_clean for kw in GENERIC_TITLE_KEYWORDS) or is_generic_title_text(name_clean, ministry=ministry):
            return True, f"日付不明ジェネリックタイトル（{name}）"
        if not re.search(r'第\s*\d+\s*回', name) and '開催日不明' in name:
            return True, f"回次なし日付不明プレースホルダー（{name}）"

    return False, ""


def _load_scraping_rules():
    """admin_data.json から scrapingRules を読み込む"""
    if os.path.exists(ADMIN_DATA_FILE):
        try:
            with open(ADMIN_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("scrapingRules", {})
        except Exception:
            pass
    return {}


def cleanup_data(data_path=DATA_JSON_FILE, dry_run=False):
    """docs/data.json の meetings を走査してゴミ開催回をクリーンアップする"""
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    councils = data.get("councils", [])
    council_ministry_map = {c.get("id"): c.get("ministry") for c in councils if c.get("id")}
    scraping_rules = _load_scraping_rules()

    original_meetings = data.get("meetings", [])
    kept_meetings = []
    removed_meetings = []
    seen_keys = set()

    for m in original_meetings:
        is_j, reason = is_junk_meeting(m, council_ministry_map=council_ministry_map)
        if is_j:
            removed_meetings.append((m, reason))
            continue

        # 同一 (councilId, name, date) の重複排除
        key = (m.get("councilId"), m.get("name"), m.get("date"))
        if key in seen_keys:
            removed_meetings.append((m, f"完全重複レコード（{key}）"))
            continue

        # Drop 99: scraping_rules.material_exclude_url_patterns に基づく無効資料リンクのフィルタリング
        cid = m.get("councilId", "")
        c_rule = scraping_rules.get(cid) or {}
        mat_excl_pats = c_rule.get("material_exclude_url_patterns") or []
        if mat_excl_pats and m.get("materials"):
            m["materials"] = [
                mat for mat in m.get("materials", [])
                if not any(pat in mat.get("url", "") for pat in mat_excl_pats)
            ]

        seen_keys.add(key)
        kept_meetings.append(m)

    print("============================================================")
    print(" PMHub 開催回クリーンアップ (CR-22: Clean and Repair)")
    print("============================================================")
    print(f"元 meetings 総件数: {len(original_meetings)} 件")
    print(f"削除対象ゴミ開催回: {len(removed_meetings)} 件")
    print(f"クリーンアップ後件数: {len(kept_meetings)} 件")
    print("============================================================")

    if removed_meetings:
        print("\n【削除対象開催回サマリー（先頭20件表示）】")
        for m, reason in removed_meetings[:20]:
            print(f"  - [{m.get('councilId')}] ID: {m.get('id')} | 日付: {m.get('date')} | 名称: {m.get('name')} (理由: {reason})")
        if len(removed_meetings) > 20:
            print(f"  ... 他 {len(removed_meetings) - 20} 件")

    if dry_run:
        print("\n[INFO] Dry-run モードのため、ファイルの変更は行いませんでした。")
        return len(removed_meetings)

    data["meetings"] = kept_meetings

    c_counts = {}
    for m in kept_meetings:
        cid = m.get("councilId")
        if cid:
            c_counts[cid] = c_counts.get(cid, 0) + 1

    for c in data.get("councils", []):
        cid = c.get("id")
        c["pastYearCount"] = c_counts.get(cid, 0)

    if save_data_json_with_backup:
        save_data_json_with_backup(data)
    else:
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    print("\n✅ docs/data.json のクリーンアップおよび pastYearCount 再計算が完了しました。")
    return len(removed_meetings)


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    cleanup_data(dry_run=is_dry)
