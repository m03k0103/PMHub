#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 共通ユーティリティ (admin/utils.py)

プロジェクト内の各 Python スクリプトから共通利用するユーティリティ関数を定義する。
"""

import sys
import os
import io
import json
import re
import shutil
from datetime import datetime

# パス定義
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DEFAULT_DATA_JSON_PATH = os.path.join(PROJECT_ROOT, "docs", "data.json")
DEFAULT_BACKUP_DIR = os.path.join(BASE_DIR, "backups")
DEFAULT_REJECTED_COUNCILS_PATH = os.path.join(BASE_DIR, "rejected_councils.json")


def setup_win32_utf8():
    """
    Windows ターミナルでの日本語ログ文字化けを防止する。
    chcp 65001 で UTF-8 コードページに設定し、stdout/stderr を UTF-8 として再構成する。
    Windows 以外の環境では何もしない。
    """
    if sys.platform != "win32":
        return
    os.system("chcp 65001 > NUL 2>&1")
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass


def get_browser_headers():
    """
    AGENTS.md §10 準拠の標準ブラウザヘッダー（最新 Chrome 相当）を取得する。
    行政機関サイト等の WAF/CDN によるアクセス遮断（403 Forbidden）を回避するため、
    カスタム Bot 名を含めず、標準ブラウザと同一のヘッダーおよび Sec-Ch-Ua 等を設定する。
    """
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        'Sec-Ch-Ua': '"Chromium";v="130", "Not?A_Brand";v="99", "Google Chrome";v="130"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1'
    }


def save_data_json_with_backup(data, target_file=DEFAULT_DATA_JSON_PATH, backup_dir=DEFAULT_BACKUP_DIR, max_backups=30):
    """
    docs/data.json を更新する前に、タイムスタンプ付きで admin/backups/ に自動バックアップを作成し、
    安全に上書き保存する（デフォルト過去30世代保持）。
    """
    try:
        os.makedirs(backup_dir, exist_ok=True)
        if os.path.exists(target_file):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"data_{ts}.json")
            shutil.copy2(target_file, backup_path)
            
            # 過去 max_backups 世代を超える古いバックアップの自動整理
            b_files = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith("data_") and f.endswith(".json")])
            if len(b_files) > max_backups:
                for old_f in b_files[:-max_backups]:
                    try:
                        os.remove(old_f)
                    except Exception:
                        pass

        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save data.json with backup: {e}", file=sys.stderr)
        return False


def decode_html_bytes(content_bytes, content_type_header=""):
    """
    HTTPヘッダー、metaタグ、各種エンコーディング（UTF-8, CP932/Shift_JIS, EUC-JP）を
    正確に自動判別してデコードし、文字化けを完全排除する。
    """
    if not content_bytes:
        return ""
    
    encoding = None
    # 1. Content-Type ヘッダーの charset 判定
    if content_type_header:
        m = re.search(r'charset=([\'"]?[\w\-]+[\'"]?)', content_type_header, re.I)
        if m:
            raw_enc = m.group(1).strip('\'"').lower()
            if raw_enc in ('shift_jis', 'shift-jis', 'sjis', 'x-sjis'):
                encoding = 'cp932'
            elif raw_enc in ('euc-jp', 'eucjp'):
                encoding = 'euc-jp'
            elif raw_enc in ('utf-8', 'utf8'):
                encoding = 'utf-8'

    # 2. HTMLの先頭2048バイトから <meta charset="..."> または <meta http-equiv=... charset=...> を抽出
    head_sample = content_bytes[:2048].decode('ascii', errors='ignore')
    m_meta = re.search(r'<meta[^>]+charset=[\'"]?([\w\-]+)', head_sample, re.I)
    if not m_meta:
        m_meta = re.search(r'content=[\'"][^"\']*charset=([\w\-]+)', head_sample, re.I)
        
    if m_meta:
        meta_enc = m_meta.group(1).strip('\'"').lower()
        if meta_enc in ('shift_jis', 'shift-jis', 'sjis', 'x-sjis'):
            encoding = 'cp932'
        elif meta_enc in ('euc-jp', 'eucjp'):
            encoding = 'euc-jp'
        elif meta_enc in ('utf-8', 'utf8'):
            encoding = 'utf-8'

    # 3. 試行デコード（検出されたエンコーディング最優先 -> UTF-8 -> CP932 -> EUC-JP）
    encodings_to_try = []
    if encoding:
        encodings_to_try.append(encoding)
    encodings_to_try.extend(['utf-8', 'cp932', 'euc-jp'])
    
    # 重複除去
    seen = set()
    unique_encs = []
    for e in encodings_to_try:
        if e not in seen:
            seen.add(e)
            unique_encs.append(e)

    for enc in unique_encs:
        try:
            decoded = content_bytes.decode(enc)
            # 文字化け特有の不正バイトや置換文字の混入チェック
            if '\ufffd' not in decoded:
                return decoded
        except (UnicodeDecodeError, LookupError):
            continue

    # 4. chardet による推測（インストールされている場合）
    try:
        import chardet
        detected = chardet.detect(content_bytes[:4096])
        if detected and detected.get('encoding'):
            return content_bytes.decode(detected['encoding'], errors='replace')
    except Exception:
        pass

    return content_bytes.decode('utf-8', errors='replace')


def load_rejected_councils(rejected_file=DEFAULT_REJECTED_COUNCILS_PATH):
    """
    admin/rejected_councils.json を安全に読み込み、却下済み会議体のリストを返す。
    ファイルが存在しないかエラーの場合は空リスト [] を返す。
    """
    if os.path.exists(rejected_file):
        try:
            with open(rejected_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[WARN] Failed to load {rejected_file}: {e}", file=sys.stderr)
    return []


def save_rejected_councils(rejected_data, rejected_file=DEFAULT_REJECTED_COUNCILS_PATH):
    """
    admin/rejected_councils.json に却下済み会議体リストを整形保存する。
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(rejected_file)), exist_ok=True)
        with open(rejected_file, "w", encoding="utf-8") as f:
            json.dump(rejected_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save {rejected_file}: {e}", file=sys.stderr)
        return False


def get_rejected_identifiers(rejected_file=DEFAULT_REJECTED_COUNCILS_PATH):
    """
    却下済み会議体から (ids_set, names_set, urls_set) のタプルを取得する。
    URLは末尾スラッシュを除去した正規化形式で保持する。
    """
    rej_list = load_rejected_councils(rejected_file)
    rej_ids = set()
    rej_names = set()
    rej_urls = set()
    for rc in rej_list:
        if rc.get("id"):
            rej_ids.add(rc.get("id").strip())
        if rc.get("name"):
            rej_names.add(rc.get("name").strip())
        if rc.get("officialUrl"):
            rej_urls.add(rc.get("officialUrl").strip().rstrip("/"))
    return rej_ids, rej_names, rej_urls
