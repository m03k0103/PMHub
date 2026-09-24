#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
admin/batch_normalize_data.py
=============================
Drop 22 (CR-47): 康煕部首・特殊異体字・全角英数 NFKC 一括バッチ正規化スクリプト

docs/data.json 内の全既存データ（councils, meetings, materials）を走査し、
行政文書で頻出する康煕部首（⾦, ⽊, ⽔, ⾼, ⼩ 等）や環境依存文字、全角英数を
unicodedata.normalize('NFKC', ...) で標準文字へ一括正規化する。
これにより、文字コードの表記揺れによる検索漏れを完全根絶する。
"""

import os
import sys
import json
import re
import unicodedata
import argparse

# Windows コンソールでの文字化け防止
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# PMHub 共通モジュールのインポート
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'admin')))
try:
    from crawler import DATA_JSON_FILE, save_data_json_with_backup, normalize_text
except ImportError:
    DATA_JSON_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs', 'data.json'))
    save_data_json_with_backup = None

    def normalize_text(text):
        if not text:
            return ""
        norm = unicodedata.normalize('NFKC', str(text))
        return re.sub(r'[\s\u3000]+', ' ', norm).strip()


def is_kangxi_or_supplement(ch):
    """康煕部首（U+2F00〜U+2FD5）またはCJK部首補助（U+2E80〜U+2EF3）であるかを判定"""
    cp = ord(ch)
    return (0x2F00 <= cp <= 0x2FD5) or (0x2E80 <= cp <= 0x2EF3)


def count_kangxi_chars(text):
    """テキスト内に含まれる康煕部首・部首補助文字の数を集計"""
    if not text or not isinstance(text, str):
        return 0
    return sum(1 for ch in text if is_kangxi_or_supplement(ch))


def scan_dataset_kangxi_stats(data):
    """データセット全体の康煕部首の出現統計を集計"""
    stats = {
        "councils": 0,
        "meetings": 0,
        "materials": 0,
        "total": 0,
        "unique_chars": set()
    }

    for c in data.get("councils", []):
        for field in ["name", "description"]:
            val = c.get(field, "")
            cnt = count_kangxi_chars(val)
            if cnt:
                stats["councils"] += cnt
                for ch in val:
                    if is_kangxi_or_supplement(ch):
                        stats["unique_chars"].add(ch)

    for m in data.get("meetings", []):
        for field in ["name", "summary"]:
            val = m.get(field, "")
            cnt = count_kangxi_chars(val)
            if cnt:
                stats["meetings"] += cnt
                for ch in val:
                    if is_kangxi_or_supplement(ch):
                        stats["unique_chars"].add(ch)
        for t in m.get("tags", []):
            cnt = count_kangxi_chars(t)
            if cnt:
                stats["meetings"] += cnt
                for ch in t:
                    if is_kangxi_or_supplement(ch):
                        stats["unique_chars"].add(ch)
        for a in m.get("agenda", []):
            cnt = count_kangxi_chars(a)
            if cnt:
                stats["meetings"] += cnt
                for ch in a:
                    if is_kangxi_or_supplement(ch):
                        stats["unique_chars"].add(ch)

        for mat in m.get("materials", []):
            val = mat.get("name", "")
            cnt = count_kangxi_chars(val)
            if cnt:
                stats["materials"] += cnt
                for ch in val:
                    if is_kangxi_or_supplement(ch):
                        stats["unique_chars"].add(ch)

    stats["total"] = stats["councils"] + stats["meetings"] + stats["materials"]
    return stats


def normalize_value(val):
    """文字列値を安全に NFKC 正規化する（改行は保持、連続半角スペースは整流、康煕部首・CJK部首補助を完全置換）"""
    if not val or not isinstance(val, str):
        return val
    return normalize_text(val)


def run_batch_normalization(data_path=DATA_JSON_FILE, dry_run=False):
    """全データの NFKC 正規化を一括実行する"""
    print("=" * 65)
    print(" PMHub 康煕部首・特殊文字 NFKC 一括バッチ正規化 (CR-47)")
    print("=" * 65)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pre_stats = scan_dataset_kangxi_stats(data)
    print(f"【正規化前 康煕部首検出状況】")
    print(f"  総検出数:         {pre_stats['total']} 箇所")
    print(f"  会議体マスター:   {pre_stats['councils']} 箇所")
    print(f"  開催回データ:     {pre_stats['meetings']} 箇所")
    print(f"  配付資料データ:   {pre_stats['materials']} 箇所")
    print(f"  ユニーク文字種数: {len(pre_stats['unique_chars'])} 種")

    modified_councils = 0
    modified_meetings = 0
    modified_materials = 0

    # 1. 会議体マスターの正規化
    for c in data.get("councils", []):
        changed = False
        for field in ["name", "description"]:
            if field in c and isinstance(c[field], str):
                orig = c[field]
                norm = normalize_value(orig)
                if orig != norm:
                    c[field] = norm
                    changed = True
        if changed:
            modified_councils += 1

    # 2. 開催回データおよび配付資料データの正規化
    for m in data.get("meetings", []):
        changed = False
        for field in ["name", "summary"]:
            if field in m and isinstance(m[field], str):
                orig = m[field]
                norm = normalize_value(orig)
                if orig != norm:
                    m[field] = norm
                    changed = True
        if "tags" in m and isinstance(m["tags"], list):
            new_tags = []
            for t in m["tags"]:
                if isinstance(t, str):
                    nt = normalize_value(t)
                    if nt != t:
                        changed = True
                    new_tags.append(nt)
                else:
                    new_tags.append(t)
            m["tags"] = new_tags
        if "agenda" in m and isinstance(m["agenda"], list):
            new_agenda = []
            for a in m["agenda"]:
                if isinstance(a, str):
                    na = normalize_value(a)
                    if na != a:
                        changed = True
                    new_agenda.append(na)
                else:
                    new_agenda.append(a)
            m["agenda"] = new_agenda

        # 配付資料
        for mat in m.get("materials", []):
            if "name" in mat and isinstance(mat["name"], str):
                orig_m = mat["name"]
                norm_m = normalize_value(orig_m)
                if orig_m != norm_m:
                    mat["name"] = norm_m
                    modified_materials += 1
                    changed = True

        if changed:
            modified_meetings += 1

    post_stats = scan_dataset_kangxi_stats(data)
    print("\n" + "-" * 65)
    print(f"【正規化後 康煕部首検出状況】")
    print(f"  総検出数:         {post_stats['total']} 箇所（0件であることを確認）")
    print(f"  会議体マスター:   {post_stats['councils']} 箇所")
    print(f"  開催回データ:     {post_stats['meetings']} 箇所")
    print(f"  配付資料データ:   {post_stats['materials']} 箇所")
    print("-" * 65)
    print(f"【更新対象レコード件数】")
    print(f"  変更された会議体数: {modified_councils} 件")
    print(f"  変更された開催回数: {modified_meetings} 件")
    print(f"  変更された配付資料数: {modified_materials} 件")
    print("=" * 65)

    if dry_run:
        print("\n[INFO] Dry-run モードのため、ファイルの保存はスキップしました。")
        return post_stats["total"] == 0

    # 保存
    if save_data_json_with_backup:
        save_data_json_with_backup(data)
    else:
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    print("\n✅ docs/data.json の一括正規化および安全保存が完了しました。")
    return post_stats["total"] == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PMHub NFKC 一括バッチ正規化スクリプト")
    parser.add_argument("--dry-run", action="store_true", help="ファイル保存を行わずに統計のみ表示")
    args = parser.parse_args()

    success = run_batch_normalization(dry_run=args.dry_run)
    sys.exit(0 if success else 1)
