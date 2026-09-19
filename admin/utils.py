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
import functools


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


_ZEN_TO_HAN_DIGITS_TABLE = str.maketrans('０１２３４５６７８９', '0123456789')


def normalize_japanese_numbers(text):
    """
    全角数字を半角数字に正規化する。
    None や空文字の場合は空文字列を返す。
    """
    if not text:
        return ""
    return str(text).translate(_ZEN_TO_HAN_DIGITS_TABLE)


# 和暦・西暦日付パース用事前コンパイル正規表現
_RE_REIWA_DATE = re.compile(r'(?<!\d)令和(\d+|元)年(\d{1,2})月(\d{1,2})日(?!\d)')
_RE_HEISEI_DATE = re.compile(r'(?<!\d)平成(\d+|元)年(\d{1,2})月(\d{1,2})日(?!\d)')
_RE_SEIREKI_DATE = re.compile(r'(?<!\d)(\d{4})年(\d{1,2})月(\d{1,2})日(?!\d)')
_RE_SLASH_DATE = re.compile(r'(?<![\d\w])(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?![\d\w])')


@functools.lru_cache(maxsize=2048)
def parse_japanese_date(date_str):
    """
    和暦・西暦文字列を datetime オブジェクトに変換（元年対応・厳格検証）。
    結果は lru_cache でキャッシュされ、頻出日付のパースを高速化する。
    """
    if not date_str:
        return None
    date_str = normalize_japanese_numbers(date_str).strip()
    m_reiwa = _RE_REIWA_DATE.search(date_str)
    if m_reiwa:
        try:
            yr_num = 1 if m_reiwa.group(1) == '元' else int(m_reiwa.group(1))
            year = 2018 + yr_num
            month = int(m_reiwa.group(2))
            day = int(m_reiwa.group(3))
            return datetime(year, month, day)
        except Exception:
            pass
    m_heisei = _RE_HEISEI_DATE.search(date_str)
    if m_heisei:
        try:
            yr_num = 1 if m_heisei.group(1) == '元' else int(m_heisei.group(1))
            year = 1988 + yr_num
            month = int(m_heisei.group(2))
            day = int(m_heisei.group(3))
            return datetime(year, month, day)
        except Exception:
            pass
    m_seireki = _RE_SEIREKI_DATE.search(date_str)
    if m_seireki:
        try:
            year = int(m_seireki.group(1))
            month = int(m_seireki.group(2))
            day = int(m_seireki.group(3))
            return datetime(year, month, day)
        except Exception:
            pass
    m_slash = _RE_SLASH_DATE.search(date_str)
    if m_slash:
        try:
            year = int(m_slash.group(1))
            month = int(m_slash.group(2))
            day = int(m_slash.group(3))
            return datetime(year, month, day)
        except Exception:
            pass
    return None



_RE_COUNCIL_ID = re.compile(r'^[a-z]+-[a-z0-9_]+$')
_RE_MEETING_ID = re.compile(r'^[a-z]+-[a-z0-9_]+-\d{8}-[a-z0-9_]+$')


def validate_council_id(council_id):
    """
    AGENTS.md §3-1 準拠の会議体ID形式（{ministry}-{slug}、ハイフン厳格1個・2セグメント）を検証する。
    """
    if not council_id or not isinstance(council_id, str):
        return False
    return council_id.count('-') == 1 and bool(_RE_COUNCIL_ID.match(council_id))


def validate_meeting_id(meeting_id):
    """
    AGENTS.md §3-2 準拠の開催回ID形式（{councilId}-{YYYYMMDD}-{round/session}、ハイフン厳格3個・4セグメント）を検証する。
    """
    if not meeting_id or not isinstance(meeting_id, str):
        return False
    return meeting_id.count('-') == 3 and bool(_RE_MEETING_ID.match(meeting_id))


_DATA_JSON_CACHE = {}


def clear_data_json_cache(target_file=None):
    """load_data_json のメモリキャッシュをクリアする。"""
    global _DATA_JSON_CACHE
    if target_file is None:
        _DATA_JSON_CACHE.clear()
    else:
        abs_path = os.path.abspath(target_file)
        _DATA_JSON_CACHE.pop(abs_path, None)


def load_data_json(target_file=DEFAULT_DATA_JSON_PATH, cached=False):
    """
    docs/data.json を安全に読み込み、辞書オブジェクトを返す。
    cached=True の場合、mtime（ファイル最終更新日時）連動のインメモリキャッシュを返し、再パースをスキップする。
    ファイルが存在しないかエラーの場合は空辞書 {} を返す。
    """
    if not os.path.exists(target_file):
        return {}

    abs_path = os.path.abspath(target_file)
    try:
        mtime = os.path.getmtime(abs_path)
    except OSError:
        mtime = 0

    if cached and abs_path in _DATA_JSON_CACHE:
        cached_mtime, cached_data = _DATA_JSON_CACHE[abs_path]
        if cached_mtime == mtime:
            return cached_data

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data_dict = data if isinstance(data, dict) else {}
            if cached:
                _DATA_JSON_CACHE[abs_path] = (mtime, data_dict)
            return data_dict
    except Exception as e:
        print(f"[WARN] Failed to load {target_file}: {e}", file=sys.stderr)
        return {}


def save_data_json_with_backup(data, target_file=DEFAULT_DATA_JSON_PATH, backup_dir=DEFAULT_BACKUP_DIR, max_backups=30, create_backup=True):
    """
    docs/data.json をアトミックに安全保存する。
    create_backup=True の場合、更新前にタイムスタンプ付きで admin/backups/ に自動バックアップを作成する（デフォルト過去30世代保持）。
    書き込みは一時ファイル (.tmp) に行い、os.replace によるアトミック置換でファイル破損（0バイト化）を防止する。
    """
    tmp_file = f"{target_file}.tmp"
    try:
        if create_backup:
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

        target_dir = os.path.dirname(os.path.abspath(target_file))
        os.makedirs(target_dir, exist_ok=True)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, target_file)
        clear_data_json_cache(target_file)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save data.json with backup: {e}", file=sys.stderr)
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        return False


# HTML デコード用文字コード別名マッピングおよびフォールバック候補
_SJIS_ALIASES = frozenset({'shift_jis', 'shift-jis', 'sjis', 'x-sjis'})
_EUCJP_ALIASES = frozenset({'euc-jp', 'eucjp'})
_UTF8_ALIASES = frozenset({'utf-8', 'utf8'})
_DEFAULT_FALLBACK_ENCODINGS = ('utf-8', 'cp932', 'euc-jp')


def _resolve_charset_alias(raw_enc):
    """charset 文字列から Python 標準エンコーディング名を解決する"""
    if not raw_enc:
        return None
    c = raw_enc.strip('\'"').lower()
    if c in _SJIS_ALIASES:
        return 'cp932'
    elif c in _EUCJP_ALIASES:
        return 'euc-jp'
    elif c in _UTF8_ALIASES:
        return 'utf-8'
    return None


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
            encoding = _resolve_charset_alias(m.group(1))

    # 2. HTMLの先頭2048バイトから <meta charset="..."> または <meta http-equiv=... charset=...> を抽出
    head_sample = content_bytes[:2048].decode('ascii', errors='ignore')
    m_meta = re.search(r'<meta[^>]+charset=[\'"]?([\w\-]+)', head_sample, re.I)
    if not m_meta:
        m_meta = re.search(r'content=[\'"][^"\']*charset=([\w\-]+)', head_sample, re.I)
        
    if m_meta and not encoding:
        encoding = _resolve_charset_alias(m_meta.group(1))

    # 3. 試行デコード（検出されたエンコーディング最優先 -> UTF-8 -> CP932 -> EUC-JP）
    encodings_to_try = []
    if encoding:
        encodings_to_try.append(encoding)
    encodings_to_try.extend(_DEFAULT_FALLBACK_ENCODINGS)
    
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
    admin/rejected_councils.json に却下済み会議体リストをアトミックに整形保存する。
    """
    tmp_file = f"{rejected_file}.tmp"
    try:
        target_dir = os.path.dirname(os.path.abspath(rejected_file))
        os.makedirs(target_dir, exist_ok=True)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(rejected_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, rejected_file)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save {rejected_file}: {e}", file=sys.stderr)
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
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


def add_to_rejected_councils(target_id, council=None, reason="Admin rejected council", rejected_at=None, rejected_file=DEFAULT_REJECTED_COUNCILS_PATH):
    """
    admin/rejected_councils.json に会議体を重複なく安全に追加・保存する共通関数。
    追加された場合は True、既に存在していたか無効なIDの場合は False を返す。
    """
    if not target_id:
        return False
    target_id = target_id.strip()
    rejected_list = load_rejected_councils(rejected_file)
    if not any(rc.get("id") == target_id for rc in rejected_list):
        c_obj = council or {}
        rej_item = {
            "id": target_id,
            "name": c_obj.get("name") if c_obj.get("name") else target_id,
            "ministry": c_obj.get("ministry") or "",
            "category": c_obj.get("category", "COUNCIL") or "COUNCIL",
            "officialUrl": c_obj.get("officialUrl") or "",
            "rejectedAt": rejected_at or datetime.now().strftime("%Y-%m-%d"),
            "reason": reason or "Admin rejected council"
        }
        rejected_list.append(rej_item)
        return save_rejected_councils(rejected_list, rejected_file)
    return False

