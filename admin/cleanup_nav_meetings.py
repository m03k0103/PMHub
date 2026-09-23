#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
admin/cleanup_nav_meetings.py
=============================
Drop 16 (CR-22): 既存データ内共通ナビ・常設資料ゴミ開催回の全件クリーンアップ (Clean and Repair)

docs/data.json 内に混入している共通ナビゲーション、広報リンク、組織常設資料（設置要綱・委員名簿等）の
ゴミ開催回を一括スキャンし、安全に削除してマスターデータの整合性を回復する。
削除後、各会議体の pastYearCount を再計算・更新する。
"""

import os
import sys
import json
import re
from datetime import datetime

# Windows コンソールでの文字化け・UnicodeEncodeError防止
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# PMHub 共通定数のインポート
try:
    from admin.crawler import (
        DATA_JSON_FILE,
        save_data_json_with_backup,
        COMMON_NAV_KEYWORDS,
        ORGANIZATION_DOC_KEYWORDS,
        GENERIC_TITLE_KEYWORDS
    )
except ImportError:
    DATA_JSON_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "data.json"))
    save_data_json_with_backup = None
    COMMON_NAV_KEYWORDS = frozenset({
        '報道・広報', '広報', '関連リンク', 'リンク集', '災害への対応', '施策紹介', '最近の話題',
        'オンライン利用率引上げ', '調査の依頼方法', '調査の概要', '外務省後援名義等の使用許可申請',
        '御意見・御感想', 'ご意見・ご感想', '大臣会見記録', '会見記録', '報道官会見記録', '広報印刷物',
        '赤れんが棟', '法務省の個人情報保護について', '個人情報保護について', '法制審議会開催予定表',
        '開催予定表', '検査方針・研修実績等', '対象者別メニュー', '提供可能となる食品の情報',
        '新型コロナウイルス感染症に関する情報一覧', '感染症に関する情報一覧',
        '審議会開催予定', '大臣等記者会見', '記者会見', '政策情報（会議・統計等）', '会議・委員会等',
        'パンフレット', 'リーフレット', 'メールマガジン', 'メルマガ', 'ポスター'
    })
    ORGANIZATION_DOC_KEYWORDS = frozenset({
        '設置要綱', '設置要領', '設置根拠', '設置要項', '運営規程', '運営要領', '委員名簿', '構成員名簿',
        '名簿', '根拠法令', '関係法令', '申し合わせ', '運営規律', '規約', '設置趣旨', '運営方針',
        '構成員', '審議会の構成', '委員会の構成', 'の構成', '機構図', '組織図'
    })
    GENERIC_TITLE_KEYWORDS = frozenset({
        '会議資料詳細', '資料詳細', '会議詳細', 'トップページ', '目次', 'ホーム', '配付資料一覧',
        '政策について', '総務省の紹介', '国立国会図書館インターネット資料収集保存事業（WARP）',
        '国立国会図書館インターネット資料収集保存事業', '議事次第', '配付資料', '配布資料',
        '議題', '資料', '議事', '日時', 'メンバー', '会議資料一覧', '審議会・検討会・研究会等',
        '審議会、検討会、研究会等', '令和３年改正個人情報保護法について', '原子力規制委員会',
        'サイトマップ', '開催案内', '開催について', '１開催日時', '１．日', '●日時', 'お知らせ',
        '新着情報', '１．日時', '１　開催日時', '議事要旨等', 'Interim Report', '共同主催国際会議',
        '議事次第・資料一覧', '配布資料一覧', '配付資料一覧', '覚書等', '覚書',
        '開催日', '開催日時', '開催期間', '議事次第等', '資料一覧', '配付資料等', '配布資料等',
        '会議結果', '開催案内等', '配付資料について', '配布資料について', '会議概要'
    })

NAV_EXCLUDE_EXACT = frozenset({
    '関連リンク', '施策紹介', '広報印刷物', '赤れんが棟', '法務省の個人情報保護について',
    '１ 調査の依頼方法', 'オンライン利用率引上げ', '検査方針・研修実績等',
    '法制審議会開催予定表', '２０２６年', '1.経緯'
})


def is_junk_meeting(m):
    """開催回が共通ナビ・広報・組織常設資料のゴミデータであるかを厳格に判定する"""
    name = (m.get("name") or "").strip()
    mid = m.get("id", "")
    
    # 開催日不明ラベルや番号プレフィックスを除去したコアタイトル
    name_clean = re.sub(r'\s*\([^\)]*開催日不明[^\)]*\)$', '', name).strip()
    name_clean = re.sub(r'^[0-9０-９一二三四五六七八九十]+[．.、\s]+', '', name_clean).strip()

    # 1. 組織常設資料（会議体資料であり個別の開催回ではない）
    if any(k in name_clean for k in ORGANIZATION_DOC_KEYWORDS) or any(k in name for k in ['報告書', '活動状況', '視察概要', '名簿']):
        if not re.search(r'第\s*\d+\s*回', name):
            return True, f"組織常設資料・報告書等（{name}）"

    # 2. 共通ナビゲーション・広報リンク・UI操作テキスト
    if any(k in name_clean for k in COMMON_NAV_KEYWORDS) or any(k in name for k in ['メニュー開閉', '文化庁の紹介', '政策情報（会議・統計等）', '会議・委員会等']):
        if not re.search(r'第\s*\d+\s*回', name):
            return True, f"共通ナビ・広報・UIリンク（{name}）"

    if name_clean in NAV_EXCLUDE_EXACT or name in NAV_EXCLUDE_EXACT:
        return True, f"除外アンカーテキスト一致（{name}）"

    # 3. 日付不明かつジェネリックタイトル（親会議体名そのまま + 開催日不明等）
    if m.get("isDateUnconfirmed") or m.get("date") == "2099/01/01":
        if any(kw == name_clean or kw in name_clean for kw in GENERIC_TITLE_KEYWORDS):
            return True, f"日付不明ジェネリックタイトル（{name}）"
        # 回次なしの親組織名プレースホルダー重複の除去（例: 高齢運転者... (開催日不明)）
        if not re.search(r'第\s*\d+\s*回', name) and '開催日不明' in name:
            # 既に正規の開催回が存在する会議体でのプレースホルダー残骸
            return True, f"回次なし日付不明プレースホルダー（{name}）"

    return False, ""


def cleanup_data(data_path=DATA_JSON_FILE, dry_run=False):
    """docs/data.json の meetings を走査してゴミ開催回をクリーンアップする"""
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    original_meetings = data.get("meetings", [])
    kept_meetings = []
    removed_meetings = []

    # 重複キーの追跡用
    seen_keys = set()

    for m in original_meetings:
        is_j, reason = is_junk_meeting(m)
        if is_j:
            removed_meetings.append((m, reason))
            continue

        # 同一 (councilId, name, date) の重複排除
        key = (m.get("councilId"), m.get("name"), m.get("date"))
        if key in seen_keys:
            removed_meetings.append((m, f"完全重複レコード（{key}）"))
            continue

        # 404 リンク切れ資料の整理
        if m.get("id") == "jsa-2227-20170118-001":
            m["materials"] = [mat for mat in m.get("materials", []) if "1380735_" not in mat.get("url", "")]

        seen_keys.add(key)
        kept_meetings.append(m)

    print(f"============================================================")
    print(f" PMHub 開催回クリーンアップ (CR-22: Clean and Repair)")
    print(f"============================================================")
    print(f"元 meetings 総件数: {len(original_meetings)} 件")
    print(f"削除対象ゴミ開催回: {len(removed_meetings)} 件")
    print(f"クリーンアップ後件数: {len(kept_meetings)} 件")
    print(f"============================================================")

    if removed_meetings:
        print(f"\n【削除対象開催回サマリー（先頭20件表示）】")
        for m, reason in removed_meetings[:20]:
            print(f"  - [{m.get('councilId')}] ID: {m.get('id')} | 日付: {m.get('date')} | 名称: {m.get('name')} (理由: {reason})")
        if len(removed_meetings) > 20:
            print(f"  ... 他 {len(removed_meetings) - 20} 件")

    if dry_run:
        print("\n[INFO] Dry-run モードのため、ファイルの変更は行いませんでした。")
        return len(removed_meetings)

    # meetings 更新
    data["meetings"] = kept_meetings

    # 各会議体の pastYearCount を再計算・同期
    c_counts = {}
    for m in kept_meetings:
        cid = m.get("councilId")
        if cid:
            c_counts[cid] = c_counts.get(cid, 0) + 1

    for c in data.get("councils", []):
        cid = c.get("id")
        c["pastYearCount"] = c_counts.get(cid, 0)

    # 保存
    if save_data_json_with_backup:
        save_data_json_with_backup(data)
    else:
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    print(f"\n✅ docs/data.json のクリーンアップおよび pastYearCount 再計算が完了しました。")
    return len(removed_meetings)


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    cleanup_data(dry_run=is_dry)
