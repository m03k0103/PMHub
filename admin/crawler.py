#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 審議会・会議体情報取得Engine (Information Retrieval Engine)
docs/data.json の会議体マスター (councils) およびスクレイピングルール (scrapingRules) を読み込み、
高速・高精度な階層クロールおよび資料データ取得を実行する専用Engine
"""

import sys
import os
import json
import shutil
import urllib.request
import urllib.parse
import re
import time
import threading
import concurrent.futures
import argparse
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from utils import (
    setup_win32_utf8, get_browser_headers, save_data_json_with_backup,
    decode_html_bytes, get_rejected_identifiers, normalize_japanese_numbers, load_data_json,
    parse_japanese_date
)
setup_win32_utf8()

# LLM (Gemini API) の遅延初期化キャッシュ
_gemini_model = None

def get_gemini_model():
    """
    LLMフォールバックが必要な場合にのみ初期化する（遅延ロード）。
    通常運用（Heuristicモード）時の起動時間を短縮し、依存警告を抑制する。
    """
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            import google.generativeai as genai
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel('gemini-3.8-flash')
        return _gemini_model
    except Exception as e:
        print(f"[WARN] Failed to initialize Gemini model (gemini-3.8-flash): {e}")
        return None


DATA_JSON_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "data.json"))
BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "backups"))
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "logs"))

# 無効な日付プレフィックス（旧クローラー残骸などスコアリング対象外の日付パターン）
INVALID_DATE_PREFIXES = ("1312",)

# ジェネリックタイトル・ポータル見出しキーワード（会議名として不適切な汎用文字列）
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
    '会議結果', '開催案内等', '配付資料について', '配布資料について', '会議概要',
    '報道・広報', '広報', '関連リンク', 'リンク集', '災害への対応', '施策紹介', '最近の話題',
    'オンライン利用率引上げ', '調査の概要', '外務省後援名義等の使用許可申請', '御意見・御感想',
    'ご意見・ご感想', '大臣会見記録', '会見記録', '報道官会見記録', '広報印刷物', '赤れんが棟',
    '法務省の個人情報保護について', '個人情報保護について', '法制審議会開催予定表', '開催予定表',
    '検査方針・研修実績等', '対象者別メニュー', '提供可能となる食品の情報',
    '新型コロナウイルス感染症に関する情報一覧', '感染症に関する情報一覧',
    '審議会開催予定', '大臣等記者会見', '記者会見', '政策情報（会議・統計等）', '会議・委員会等'
})

# 組織常設資料（設置要綱・委員名簿・運営規程等）のキーワード（CR-20: 会議体資料であり開催回ではない）
ORGANIZATION_DOC_KEYWORDS = frozenset({
    '設置要綱', '設置要領', '設置根拠', '設置要項', '運営規程', '運営要領', '委員名簿', '構成員名簿',
    '名簿', '根拠法令', '関係法令', '申し合わせ', '運営規律', '規約', '設置趣旨', '運営方針'
})

# 省庁共通ナビゲーション・広報リンク・非会議サブページのキーワード（CR-19: 開催回への誤登録を完全遮断）
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

# 配付資料として不適切な汎用ナビゲーション・UIテキスト（事前除外用定数）
EXCLUDE_MATERIAL_NAMES = frozenset({
    '本文へ移動します', 'フッターへ移動します', '閉じる', 'メニューを閉じる',
    'メニューを開く', 'このページの先頭へ', '前のページへ戻る', '前のページへ',
    '先頭へ戻る', 'ページトップへ', 'ページ先頭へ', 'PAGE TOP', 'Page Top',
    'pagetop', 'トップへ', 'トップ', 'HOME', 'Home', '戻る', '印刷', '印刷する',
    '別ウィンドウで開く', '新しいウィンドウで開く', '（別ウィンドウで開く）',
    'JavaScriptが無効です', 'JavaScriptを有効にしてください'
})

# デフォルトの日付抽出正規表現
DEFAULT_DATE_REGEX = r'(?:令和|平成)(?:\d+|元)年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+'

# 汎用インデックス・ポータルURL除外用の事前コンパイル正規表現
_GENERIC_INDEX_URL_PATTERNS = re.compile(
    r'houdou/index\.html|'
    r'houdou/houdou\.html|'
    r'press/index\.html|'
    r'topics/index\.html|'
    r'news/index\.html|'
    r'shingi(?:kai)?/index\.html|'
    r'/pressrelease/?$|'
    r'/houdou_topics/?$|'
    r'/houdou/?$|'
    r'comittee/kaisai\.html|'
    r'space/comittee/about\.html|'
    r'/kaisai\.html$|'
    r'indexshingi\.html|'
    r'newpage_19921\.html|'
    r'cas\.go\.jp/jp/s(?:i|hi)ryou?(?:/index\.html)?$|'
    r'cas\.go\.jp/jp/s(?:i|hi)ryou?/|'
    r'cas\.go\.jp/jp/seisakukaigi/index\.html|'
    r'cyber/what-we-do/csmeeting\.html|'
    r'/int/kaisai/kako\.html|'
    r'study/dai3sya/index\.html|'
    r'policymeeting/(?:index\.html)?$|'
    r'fiscal_system_council/[^/]+/(?:proceedings|report)/(?:index\.html)?$|'
    r'gijiroku/zeicho/\d{4}/(?:index\.html)?$|'
    r'fsc\.go\.jp/senmon/(?:[^/]+/)?$|'
    r'kanbou_library_library\d+_\d+\.html|'
    r'14th_congress_index\.html|'
    r'menu_sosiki/singi/index\.html|'
    r'sonota_index\.html|'
    r'seisakusesaku_index\.html|'
    r'shingi_index\.html|'
    r'shingikai_index\.html|'
    r'topics/bukyoku/syakai/soren/|'
    r'bousai\.go\.jp/kohou/oshirase/|'
    r'iinkaisai/iinkaisai\.html|'
    r'bunkakaisai/bunkakaisai\.html|'
    r'yusei_kaisai\.html|'
    r'/kaisai/yusei/|'
    r'menu_news/s-news|'
    r'b_menu/houdou|'
    r'da\.nra\.go\.jp/search\?.*f\.gi=.*f\.gi=|'
    r'digital\.go\.jp/(?:en/)?councils/[^/]+/?$|'
    r'digital\.go\.jp/en/|'
    r'digital\.go\.jp/councils/procurement-agile-opensource/(?:agile|opensource)-review-meeting/?$|'
    r'sitemap(?:\.html|\.xml|/)?$|'
    r'/sitemap/|'
    r'agenda/meeting/[^/]+/archive(?:_\d+-\d+)?\.html$|'
    r'archive_\d+-\d+\.html$|'
    r'member(?:\.html|/)?$|'
    r'meibo(?:\.html|/)?$',
    re.IGNORECASE
)

# 汎用インデックス判定用の除外タイトルキーワード（部分一致用）
_GENERIC_INDEX_TITLE_KEYWORDS = frozenset({
    "その他情報", "覚書等", "覚書", "有識者会議｜警察庁", "過去の国際会議",
    "研究会等一覧へのリンク", "会議資料詳細", "資料詳細", "会議詳細",
    "食の安全、を科学する", "審議会等", "｜デジタル庁", "｜Digital Agency", "Digital Agency",
    "政策・審議会等", "省議・審議会等", "政策・審議会等トップへ", "審議会・研究会"
})

# 汎用インデックス判定用の完全一致除外タイトル（単体での登録排除用）
_GENERIC_INDEX_EXACT_TITLES = frozenset({
    "審議会", "政策・審議会等トップへ", "その他会議", "会議", "委員会"
})


# 省庁コードと公式ドメインのマッピング（他省庁URLの誤混入ガード用）
MINISTRY_DOMAINS = {
    "MHLW": ["mhlw.go.jp"],
    "METI": ["meti.go.jp"],
    "MAFF": ["maff.go.jp"],
    "MOJ": ["moj.go.jp"],
    "CAO": ["cao.go.jp", "scj.go.jp"],
    "CAS": ["cas.go.jp"],
    "NPA": ["npa.go.jp"],
    "FSA": ["fsa.go.jp"],
    "MIC": ["soumu.go.jp"],
    "MOF": ["mof.go.jp"],
    "MEXT": ["mext.go.jp"],
    "MLIT": ["mlit.go.jp"],
    "ENV": ["env.go.jp"],
    "MOD": ["mod.go.jp"],
    "DIGITAL": ["digital.go.jp"],
    "CFA": ["cfa.go.jp"]
}
_OTHER_MINISTRY_DOMAINS_MAP = {
    m: tuple(d for om, dlist in MINISTRY_DOMAINS.items() if om != m for d in dlist)
    for m in MINISTRY_DOMAINS
}

# 429 Quota Exceeded 回避用のサーキットブレーカーフラグ
LLM_QUOTA_BLOCKED = False

def init_crawler_logfile():
    """admin/logs/ ディレクトリに日時付きログファイルと latest ログファイルを初期化してファイルオブジェクトを返す"""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"crawler_{ts}.log"
        log_filepath = os.path.join(LOGS_DIR, log_filename)
        latest_filepath = os.path.join(LOGS_DIR, "crawler_latest.log")
        
        log_f = open(log_filepath, "a", encoding="utf-8")
        latest_f = open(latest_filepath, "w", encoding="utf-8")
        return log_f, latest_f, log_filepath, latest_filepath
    except Exception as e:
        print(f"[WARN] Failed to initialize log file: {e}", file=sys.stderr)
        return None, None, "", ""

def load_crawler_config():
    data = load_data_json(DATA_JSON_FILE)
    config = data.get("crawlerConfig", {})
    return config.get("llm_mode", False)  # デフォルトは高速・安全な Heuristic モード

def load_councils_from_data_json(recent_years=2, include_closed=False, resume=False):
    """
    docs/data.json から登録済みの全会議体 (COUNCILS) を読み込む。
    - 却下済み会議体・非アクティブ会議体はクロール対象外
    - CR-24: 法改正等で廃止された会議体（isClosed: true）はデフォルトでスキップ（include_closed=True で全件対象）
    - CR-24: 直近開催年数フィルタリング（デフォルト2年以内、開催実績0件の新規会議体は探索対象として保持）
    - CR-27: resume=True の場合、既に今回の実行で巡回済みの会議体をスキップ
    """
    councils = []
    
    # 却下済みIDセットの読み込み
    rejected_ids, _, _ = get_rejected_identifiers()
    print(f"[INFO] 却下済み会議体 {len(rejected_ids)} 件をクロール対象から除外します。")

    data = load_data_json(DATA_JSON_FILE)
    raw_councils = data.get("councils", [])
    scraping_rules = data.get("scrapingRules", {})
    meetings = data.get("meetings", [])

    # 会議体ごとの最新開催日（実在日付）を事前算出
    council_latest_date = {}
    for m in meetings:
        mcid = m.get("councilId")
        mdt = m.get("date", "")
        if mdt and mdt != "2099/01/01":
            if mcid not in council_latest_date or mdt > council_latest_date[mcid]:
                council_latest_date[mcid] = mdt

    # 直近開催年数の基準日（カットオフ日）の計算
    cutoff_date = None
    if recent_years is not None and str(recent_years).lower() not in ("all", "none", "0"):
        try:
            years_float = float(recent_years)
            if years_float > 0:
                cutoff_dt = datetime.now() - timedelta(days=int(years_float * 365.25))
                cutoff_date = cutoff_dt.strftime('%Y/%m/%d')
        except (ValueError, TypeError):
            cutoff_date = None

    last_crawl_time_str = data.get("lastCrawlTime", "")

    inactive_count = 0
    closed_count = 0
    dormant_count = 0
    resumed_skip_count = 0

    for item in raw_councils:
        cid = item.get("id")
        if cid in rejected_ids:
            continue

        rule = scraping_rules.get(cid, {}) if isinstance(scraping_rules, dict) else {}

        # 1. 非アクティブフラグのチェック
        if (
            item.get("is_active") is False
            or item.get("isActive") is False
            or (isinstance(rule, dict) and (rule.get("is_active") is False or rule.get("isActive") is False))
        ):
            inactive_count += 1
            continue

        # 2. CR-24: 法改正等による廃止会議体（isClosed: true）のチェック
        is_closed = item.get("isClosed") is True or (isinstance(rule, dict) and rule.get("isClosed") is True)
        if is_closed and not include_closed:
            closed_count += 1
            continue

        # 3. CR-24: 直近開催年数フィルタリング
        if cutoff_date:
            latest_date = council_latest_date.get(cid)
            # 開催実績があるが、最新開催日が基準日より古い場合は休眠会議体としてスキップ
            if latest_date and latest_date < cutoff_date:
                dormant_count += 1
                continue
            # 開催実績がない（0件またはダミー日付のみ）会議体は新規探索のためスキップせず含める

        # 4. CR-27: レジューム時の巡回済みスキップチェック
        if resume and last_crawl_time_str:
            c_status = item.get("crawlStatus", {})
            c_last = c_status.get("lastCrawled", "") if isinstance(c_status, dict) else ""
            # lastCrawled が前回のクロール開始以降の日付・時刻であれば巡回済みと判定
            if c_last and c_last >= last_crawl_time_str[:10]:
                resumed_skip_count += 1
                continue

        if item.get("officialUrl") or item.get("archiveUrl"):
            councils.append({
                "id": cid,
                "ministry": item.get("ministry"),
                "name": item.get("name"),
                "url": (item.get("archiveUrl") or item.get("officialUrl", "")).strip(),
                "officialUrl": (item.get("officialUrl") or "").strip(),
                "archiveUrl": (item.get("archiveUrl") or "").strip(),
                "latestMeetingDate": council_latest_date.get(cid, "未開催/不明")
            })

    if inactive_count > 0:
        print(f"[INFO] 非アクティブ会議体 {inactive_count} 件をクロール対象から除外しました。")
    if closed_count > 0:
        print(f"[INFO] 法改正等廃止会議体（isClosed: true） {closed_count} 件をクロール対象から除外しました。")
    if dormant_count > 0:
        print(f"[INFO] 直近 {recent_years} 年未開催の休眠会議体 {dormant_count} 件をクロール対象からスキップしました（基準日: {cutoff_date} 以降を対象）。")
    if resumed_skip_count > 0:
        print(f"[INFO] レジューム再開: 巡回済み会議体 {resumed_skip_count} 件をスキップしました。")

    return councils

def _extract_council_host(c):
    u = c.get("officialUrl") or c.get("url") or ""
    if u:
        h = urllib.parse.urlparse(u).netloc.lower()
        if h:
            return h
    return (c.get("ministry") or "OTHER").lower() + ".go.jp"

def interleave_by_host_and_ministry(councils):
    """
    同一ホスト名（ドメイン）および同一省庁への連続アクセスを防止するため、
    ホスト名（netloc）を主キー、省庁を副キーとして均等間隔（インターリーブ）で
    巡回順序を並び替える（CR-21）。
    METIとANRE等の同一ドメイン（www.meti.go.jp）連続アクセスを根本回避する。
    """
    if not councils:
        return []
    from collections import defaultdict, deque
    buckets = defaultdict(deque)
    for c in councils:
        h = _extract_council_host(c)
        buckets[h].append(c)
    
    # 件数が多い順にソートしたホストリスト
    sorted_hosts = sorted(buckets.keys(), key=lambda k: len(buckets[k]), reverse=True)
    
    # ラウンドロビン抽出
    interleaved = []
    while buckets:
        for h in list(sorted_hosts):
            if h in buckets and buckets[h]:
                interleaved.append(buckets[h].popleft())
                if not buckets[h]:
                    del buckets[h]
                    
    # 末尾に同一ホストが連続して残る場合、先頭側の別のホストの隙間に遡って挿入・分散
    final_list = []
    for item in interleaved:
        item_host = _extract_council_host(item)
        if not final_list or _extract_council_host(final_list[-1]) != item_host:
            final_list.append(item)
        else:
            # 連続してしまう場合は、直前・直後と異なるホストの隙間に遡って挿入
            inserted = False
            for idx in range(len(final_list) - 1, 0, -1):
                prev_h = _extract_council_host(final_list[idx - 1])
                curr_h = _extract_council_host(final_list[idx])
                if prev_h != item_host and curr_h != item_host:
                    final_list.insert(idx, item)
                    inserted = True
                    break
            if not inserted:
                final_list.append(item)
                
    return final_list

interleave_by_ministry = interleave_by_host_and_ministry

def load_scraping_rules():
    """docs/data.json の scrapingRules キーからスクレイピングルールを読み込み、必要に応じて scrapingRuleTemplates を展開・マージする"""
    data = load_data_json(DATA_JSON_FILE)
    if data:
        try:
            templates = data.get("scrapingRuleTemplates", {})
            raw_rules = data.get("scrapingRules", {})
            resolved_rules = {}
            for cid, r in raw_rules.items():
                if not isinstance(r, dict):
                    continue
                # is_active / isActive が明示的に False の場合はスキップ
                if r.get("is_active") is False or r.get("isActive") is False:
                    continue
                if "template" in r and r["template"] in templates:
                    tpl_name = r["template"]
                    # テンプレートをベースに個別オーバーライドをマージ
                    merged = dict(templates[tpl_name])
                    merged.update(r)
                    merged.pop("template", None)
                else:
                    merged = dict(r)

                # ネストされた rules 辞書が存在する場合はトップレベルにフラット化
                if isinstance(merged.get("rules"), dict):
                    nested = merged.pop("rules")
                    for k, v in nested.items():
                        if k not in merged:
                            merged[k] = v

                resolved_rules[cid] = merged
            return resolved_rules
        except Exception as e:
            print(f"[WARN] Failed to load scrapingRules from data.json: {e}", file=sys.stderr)
    return {}

_RATE_LIMIT_LOCK = threading.Lock()
_LAST_REQUEST_TIME_BY_HOST = {}
_MIN_HOST_INTERVAL = 0.5  # 同一ホストへの最低アクセス間隔（秒）（AGENTS.md ルール9: 0.35秒以上のレートリミット遵守）

def _rate_limit_host(host):
    """
    同一ホストへの過密アクセス防止（CR-21, CR-26: スレッドセーフなレートリミット）。
    ロック内では予約時刻のみを更新し、実際の sleep はロック外で行うため、
    異なるホストへのアクセスは一切ブロックされず完全並行で実行される。
    """
    if not host:
        return
    sleep_needed = 0.0
    with _RATE_LIMIT_LOCK:
        now_t = time.time()
        last_t = _LAST_REQUEST_TIME_BY_HOST.get(host, 0.0)
        elapsed = now_t - last_t
        if elapsed < _MIN_HOST_INTERVAL:
            sleep_needed = _MIN_HOST_INTERVAL - elapsed
            _LAST_REQUEST_TIME_BY_HOST[host] = now_t + sleep_needed
        else:
            _LAST_REQUEST_TIME_BY_HOST[host] = now_t

    if sleep_needed > 0:
        time.sleep(sleep_needed)

def fetch_url(url, timeout=12):
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme not in ("http", "https"):
        print(f"[ERROR] Invalid scheme: {url}", file=sys.stderr)
        return None

    # CR-21, CR-26: 同一ホストへの過密アクセス防止（スレッドセーフ）
    host = parsed_url.netloc.lower()
    _rate_limit_host(host)

    headers = get_browser_headers()
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get('Content-Type', '')
            raw_bytes = response.read()
            return decode_html_bytes(raw_bytes, content_type)
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}", file=sys.stderr)
        return None

def parse_materials_from_html(html, base_url, pdf_selector=None):
    """HTMLから全配布資料（公開PDF、HTML議事録、および非公開資料）を抽出（ポータルやヘッダー・ナビノイズは事前除外）"""
    materials = []
    if not html:
        return materials
        
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. Base URL consideration
    base_tag = soup.find('base', href=True)
    if base_tag:
        base_url = urllib.parse.urljoin(base_url, base_tag['href'])
    
    # 2. 共通ヘッダー・フッター・ナビゲーション領域の事前完全除去（スキップリンク・UIノイズの根本遮断）
    for noise_tag in soup(['header', 'footer', 'nav', 'aside', 'script', 'style']):
        noise_tag.extract()
    for noise_id in ['header_navskip', 'js_drawer', 'header', 'footer', 'local_nav', 'gnavi', 'topic_path_head', 'sub_contents']:
        el = soup.find(id=noise_id)
        if el:
            el.extract()

    seen_urls = set()

    # 3. リンク抽出 (PDF文書およびHTML議事録・要旨)
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].strip()
        if not href or href.startswith('#') or href.startswith('javascript:'):
            continue
            
        # ハッシュアンカー付きURLのアンカー部分を正規化・判定
        if '#' in href and any(h in href.lower() for h in ['#contents', '#block_', '#header', '#footer', '#skip', '#main', '#page']):
            continue

        abs_url = urllib.parse.urljoin(base_url, href)
        if abs_url == base_url or abs_url in seen_urls:
            continue
        if any(k in abs_url.lower() for k in ['cas.go.jp/jp/siryou', 'cas.go.jp/jp/shiryo']) or is_generic_index_url(abs_url):
            continue

        raw_text = a_tag.get_text(" ", strip=True)
        clean_name = re.sub(r'[\（\(]PDF[／/形式\:\s\d\.\,KBMB]+\s*[\）\)]', '', raw_text).strip()
        clean_name = re.sub(r'［PDF形式：\d+.*?］', '', clean_name).strip()
        
        parsed_path = urllib.parse.urlparse(abs_url).path
        filename = os.path.basename(parsed_path)
        if not clean_name:
            clean_name = filename if filename else "配付資料"

        if clean_name in EXCLUDE_MATERIAL_NAMES or any(k in clean_name for k in ['移動します', '公式ポータル', '公式ページ', '公式情報ポータル', '審議会・検討会等一覧', '公式掲載資料・ページ']):
            continue

        # A. PDFおよび各種文書ファイル
        if href.lower().endswith(('.pdf', '.docx', '.xlsx', '.doc', '.xls')) or '/pdf/' in href.lower():
            seen_urls.add(abs_url)
            materials.append({
                "name": clean_name,
                "url": abs_url,
                "type": "PDF",
                "isPrivate": False
            })
        # B. HTML形式の議事録・議事要旨
        elif any(k in href.lower() for k in ['gijiroku', 'gijiyoshi', 'giji_yoshi', 'proceedings']) or any(k in clean_name for k in ['議事録', '議事要旨', '議事次第・配布資料']):
            seen_urls.add(abs_url)
            doc_name = clean_name
            if 'gijiroku' in href.lower() and ('議事録' not in doc_name):
                doc_name = "議事録"
            elif 'gijiyoshi' in href.lower() and ('議事要旨' not in doc_name):
                doc_name = "議事要旨"
            materials.append({
                "name": doc_name,
                "url": abs_url,
                "type": "HTML",
                "isPrivate": False
            })
            
    private_lines = re.findall(r'(資料\d+[\s\:\：]*[^\n<]+(?:非公開)[^\n<]*)', html)
    for p_text in private_lines:
        clean_p_text = re.sub(r'<[^>]+>', '', p_text).strip()
        materials.append({
            "name": clean_p_text,
            "url": "#",
            "type": "非公開",
            "isPrivate": True
        })
        
    return materials

def extract_page_title(soup, rule=None, fallback_url=""):
    """
    HTML soupから会議名・ページタイトルを抽出する。
    title_selector -> 見出しタグ (h2, h1, h3) -> <title> タグの順に探索し、ジェネリックタイトルを除外する。
    """
    try:
        title = ""
        if rule:
            title_sel = rule.get("title_selector")
            if title_sel:
                sel_el = soup.select_one(title_sel)
                if sel_el:
                    cand = sel_el.get_text(" ", strip=True)
                    if cand and not any(kw == cand or kw in cand for kw in GENERIC_TITLE_KEYWORDS):
                        title = cand

        # title_selector で取れなかった場合、またはジェネリックタイトルの場合
        if not title or any(kw == title for kw in GENERIC_TITLE_KEYWORDS):
            for tag_name in ['h2', 'h1', 'h3']:
                found_tags = soup.find_all(tag_name)
                for ft in found_tags:
                    t_cand = ft.get_text(" ", strip=True)
                    # サフィックス・余分な空白の除去
                    t_cand = re.sub(r'｜.*$', '', t_cand).strip()
                    t_cand = re.sub(r' - .*$', '', t_cand).strip()
                    t_cand = re.sub(r'\s+', ' ', t_cand).strip()
                    if not t_cand or len(t_cand) <= 3:
                        continue
                    if any(kw == t_cand or (len(kw) >= 3 and kw in t_cand) for kw in GENERIC_TITLE_KEYWORDS):
                        continue
                    title = t_cand
                    break
                if title:
                    break

        # それでもなければ <title> タグ
        if not title and soup.title and soup.title.string:
            cand_title = soup.title.string.strip()
            # サフィックス・余分な空白の除去
            cand_title = re.sub(r'｜.*$', '', cand_title).strip()
            cand_title = re.sub(r' - .*$', '', cand_title).strip()
            cand_title = re.sub(r'\s+', ' ', cand_title).strip()
            if cand_title and not any(kw == cand_title for kw in GENERIC_TITLE_KEYWORDS):
                title = cand_title

        if title:
            title = re.sub(r'｜.*$', '', title).strip()
            title = re.sub(r' - .*$', '', title).strip()
            title = re.sub(r'\s+', ' ', title).strip()
            if any(kw == title for kw in GENERIC_TITLE_KEYWORDS):
                title = ""

        return title if title else fallback_url
    except Exception:
        # パース失敗やネットワーク異常時はフォールバックURLを安全に返却
        return fallback_url


def _sort_subpage_urls_by_recency(urls):
    """URL内の数字（回次・西暦・ファイル番号等）を元に最新と思われる順（降順）に並び替える"""
    def key_fn(u):
        nums = re.findall(r'\d+', u)
        if nums:
            last_num = int(nums[-1])
            max_num = max(int(n) for n in nums)
            return (last_num, max_num)
        return (-1, -1)
    return sorted(urls, key=key_fn, reverse=True)

def _is_parent_or_nav_url(sub_url, target_url):
    """ターゲットURLより上位のインデックスページや共通ナビゲーションであるかを判定"""
    clean_sub = sub_url.rstrip('/')
    clean_tgt = target_url.rstrip('/')
    if clean_sub == clean_tgt:
        return True
    parsed_sub = urllib.parse.urlparse(clean_sub)
    parsed_tgt = urllib.parse.urlparse(clean_tgt)
    if parsed_sub.netloc == parsed_tgt.netloc:
        sub_path = parsed_sub.path.rstrip('/')
        tgt_path = parsed_tgt.path.rstrip('/')
        # サブページのパスがターゲットより短く、index.html で終わる場合は上位一覧
        if len(sub_path) < len(tgt_path) and (sub_path.endswith('/index.html') or sub_path.endswith('/index') or sub_path == ''):
            return True
        if sub_path in ('/shingikai/index.html', '/shingikai', '/index.html'):
            return True
    return False

def _normalize_url_for_comparison(u):
    """プロトコルや末尾スラッシュ・フラグメントの差異を吸収して比較用キーを生成"""
    if not u or not isinstance(u, str):
        return ""
    u_clean = u.split('#')[0].strip()
    parsed = urllib.parse.urlparse(u_clean)
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip('/')
    query = parsed.query
    return f"{netloc}{path}{'?' + query if query else ''}"

def _filter_incremental_subpages(candidate_urls, existing_urls, max_unvisited=50, max_recent=1, full_check=False):
    """
    候補サブページ群を、登録済み開催回URLと照合して差分フィルタリングする（CR-10, CR-23）。
    - 未登録サブページ: 最大 max_unvisited 件（デフォルト50件）まで巡回
    - 更新確認サブページ: 既登録のうち最新 max_recent 件（デフォルト1件: 後日掲載資料対応）を巡回
    - 既登録過去サブページ: スキップ（巡回しない。full_check=True の場合は全件再検査）

    戻り値:
        target_urls: 巡回対象URLのリスト（最新順、未登録＋更新確認）
        stats: {"unvisited": int, "recent_update": int, "skipped_known": int, "total_targets": int}
    """
    if not candidate_urls:
        return [], {"unvisited": 0, "recent_update": 0, "skipped_known": 0, "total_targets": 0}

    # full_check が有効な場合は、既登録サブページも全件再検査対象とする
    eff_max_recent = 999999 if full_check else max_recent

    # 既登録URLの正規化セット
    existing_set = set()
    if existing_urls:
        for eu in existing_urls:
            norm_eu = _normalize_url_for_comparison(eu)
            if norm_eu:
                existing_set.add(norm_eu)

    unvisited_selected = []
    recent_selected = []
    skipped_known = []

    # candidate_urls は最新順（降順）にソート済みであることを前提とする
    for u in candidate_urls:
        norm_u = _normalize_url_for_comparison(u)
        if not norm_u:
            continue

        if norm_u in existing_set:
            if len(recent_selected) < eff_max_recent:
                recent_selected.append(u)
            else:
                skipped_known.append(u)
        else:
            if len(unvisited_selected) < max_unvisited:
                unvisited_selected.append(u)

    combined = unvisited_selected + recent_selected
    target_urls = _sort_subpage_urls_by_recency(combined)

    stats = {
        "unvisited": len(unvisited_selected),
        "recent_update": len(recent_selected),
        "skipped_known": len(skipped_known),
        "total_targets": len(target_urls)
    }
    return target_urls, stats

# 非会議サブページの除外アンカーテキスト（CR-14, CR-19, CR-20）
NAV_EXCLUDE_TEXTS = frozenset({
    'ホーム', 'トップ', 'トップページ', 'トップへ', 'トップへ戻る', '目次', '政策について',
    '組織案内', 'プライバシーポリシー', 'サイトマップ', 'english', 'アクセス', 'リンク集',
    '戻る', '前のページへ戻る', '前のページへ', '次へ', '閉じる', 'メニュー', 'サイト内検索',
    '利用規約', 'ご意見・ご要望', '本文へ移動', 'フッターへ移動', 'page top', 'pagetop',
    '印刷', '印刷する', '文字サイズ', '拡大', '標準', '関連リンク', '施策紹介',
    '広報印刷物', '赤れんが棟', '法務省の個人情報保護について', '個人情報保護について',
    'オンライン利用率引上げ', '検査方針・研修実績等', '法制審議会開催予定表', '開催予定表',
    '調査の依頼方法', '調査の概要', '対象者別メニュー', '提供可能となる食品の情報',
    '新型コロナウイルス感染症に関する情報一覧', '感染症に関する情報一覧',
    '後援名義等の使用許可申請', '御意見・御感想', 'ご意見・ご感想', '会見記録', '記者会見'
})

# 会議開催・回次・資料を示すアンカーテキスト判定パターン（CR-14: 投機的類推を排除し実リンクの文脈から判定）
ROUND_OR_DATE_TEXT_PATTERN = re.compile(
    r'(?:第\s*[0-9０-９一二三四五六七八九十百]+\s*(?:回|期|部会|分科会|WG|ワーキンググループ|委員会|会合)|'
    r'配付資料|配布資料|議事次第|議事録|議事要旨|開催状況|資料一覧|開催案内等|'
    r'(?:令和|平成)(?:\d+|元)年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+)',
    re.IGNORECASE
)

# デフォルトのサブページURL正規表現パターン（CR-14: 実在リンク判定用）
DEFAULT_SUBPAGE_URL_REGEX = re.compile(
    r'(?:dai\d+|\d+kai|kaisai|gijisidai|gijiroku|newpage_\d+|shingi2|session|meeting|siryou|bunkakai|\d{3,4}\.html?$|r0?\d+/|h\d+/)',
    re.IGNORECASE
)

def _extract_date_from_url(url):
    """
    URL文字列から開催日（YYYY/MM/DD形式）を安全に抽出・復元する（CR-16: フォールバック用）。
    西暦8桁、ハイフン/アンダースコア区切り、和暦形式（r050720, h290401等）に対応。
    不正な日付（範囲外の月日）は厳格に除外し、妥当な日付のみを返す。
    """
    if not url or not isinstance(url, str):
        return None

    clean_u = url.split('?')[0].split('#')[0]

    # 1. 西暦ハイフン/アンダースコア区切り: 2024-05-10, 2024_05_10
    m_sep = re.search(r'(?:^|[/_-])(19\d{2}|20\d{2})[-_]([01]?\d)[-_]([0-3]?\d)(?:$|[._/-])', clean_u)
    if m_sep:
        try:
            y, m, d = int(m_sep.group(1)), int(m_sep.group(2)), int(m_sep.group(3))
            dt = datetime(y, m, d)
            if 1995 <= y <= 2035:
                return dt.strftime("%Y/%m/%d")
        except ValueError:
            pass

    # 2. 西暦連続8桁: 20070208, 20240820
    m_8 = re.search(r'(?:^|[/_-])(19\d{2}|20\d{2})([01]\d)([0-3]\d)(?:$|[._/-])', clean_u)
    if m_8:
        try:
            y, m, d = int(m_8.group(1)), int(m_8.group(2)), int(m_8.group(3))
            dt = datetime(y, m, d)
            if 1995 <= y <= 2035:
                return dt.strftime("%Y/%m/%d")
        except ValueError:
            pass

    # 3. 令和形式: r050720, r5-07-20
    m_r = re.search(r'(?:^|[/_-])r0?(\d{1,2})[-_]?([01]\d)[-_]?([0-3]\d)(?:$|[._/-])', clean_u, re.IGNORECASE)
    if m_r:
        try:
            r_val, m, d = int(m_r.group(1)), int(m_r.group(2)), int(m_r.group(3))
            y = 2018 + r_val
            dt = datetime(y, m, d)
            if 2019 <= y <= 2035:
                return dt.strftime("%Y/%m/%d")
        except ValueError:
            pass

    # 4. 平成形式: h290401, h190208
    m_h = re.search(r'(?:^|[/_-])h0?(\d{1,2})[-_]?([01]\d)[-_]?([0-3]\d)(?:$|[._/-])', clean_u, re.IGNORECASE)
    if m_h:
        try:
            h_val, m, d = int(m_h.group(1)), int(m_h.group(2)), int(m_h.group(3))
            y = 1988 + h_val
            dt = datetime(y, m, d)
            if 1995 <= y <= 2019:
                return dt.strftime("%Y/%m/%d")
        except ValueError:
            pass

    return None

def extract_actual_subpage_links(html, target_url, rule=None, return_meta=False):
    """
    親会議体URLまたはarchiveUrlのHTML内に実在するリンク（<a>タグ）から、
    アンカーテキストおよびURLパターンに基づき開催回サブページを確実に抽出する（CR-14）。
    URLの類推生成や投機的アクセスは一切行わない。
    return_meta=True の場合、(candidates, meta_map) のタプルを返す。
    """
    if not html or not target_url:
        return ([], {}) if return_meta else []

    soup = BeautifulSoup(html, 'html.parser')
    base_tag = soup.find('base', href=True)
    page_base_url = urllib.parse.urljoin(target_url, base_tag['href']) if base_tag else target_url
    target_domain = urllib.parse.urlparse(target_url).netloc.lower()

    custom_pattern = rule.get("subpage_discovery_pattern") if rule else None
    custom_re = re.compile(custom_pattern, re.IGNORECASE) if custom_pattern else None

    candidates = []
    meta_map = {}
    seen = set()

    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if not href or href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:'):
            continue
        if href.lower().endswith('.pdf') or href.lower().endswith('.zip'):
            continue

        abs_url = urllib.parse.urljoin(page_base_url, href)
        parsed = urllib.parse.urlparse(abs_url)
        if parsed.scheme not in ('http', 'https'):
            continue

        # 同一ドメインのみ（他省庁や外部リンクは除外）
        if parsed.netloc.lower() != target_domain:
            continue

        # 同一ページや基底URLそのものは除外
        abs_clean = abs_url.split('#')[0].rstrip('/')
        target_clean = target_url.split('#')[0].rstrip('/')
        if abs_clean == target_clean:
            continue

        # 汎用インデックスURLや親ナビURLの除外
        if is_generic_index_url(abs_url) or _is_parent_or_nav_url(abs_url, target_url):
            continue

        if any(k in abs_url.lower() for k in ['cas.go.jp/jp/siryou', 'cas.go.jp/jp/shiryo']):
            continue

        if abs_clean in seen:
            continue

        text = a.get_text(' ', strip=True)
        t_clean = re.sub(r'\s+', ' ', text).strip()
        t_stripped = re.sub(r'^[0-9０-９一二三四五六七八九十]+[．.、\s]+', '', t_clean).strip()

        # CR-19 / CR-20: ナビゲーション・広報・組織常設資料の厳格除外
        if t_clean in NAV_EXCLUDE_TEXTS or t_stripped in NAV_EXCLUDE_TEXTS:
            continue
        if any(kw in t_clean for kw in COMMON_NAV_KEYWORDS) or any(kw in t_stripped for kw in COMMON_NAV_KEYWORDS):
            continue
        if any(kw in t_clean for kw in ORGANIZATION_DOC_KEYWORDS) or any(kw in t_stripped for kw in ORGANIZATION_DOC_KEYWORDS):
            continue
        if any(kw == t_clean for kw in GENERIC_TITLE_KEYWORDS):
            continue

        # 開催告知・事前案内単体ページの除外
        if is_preliminary_notice_page(abs_url, t_clean):
            continue

        # 判定1: アンカーテキストに回次・開催・日付・資料キーワードが含まれるか
        is_subpage_by_text = bool(ROUND_OR_DATE_TEXT_PATTERN.search(t_clean))

        # 判定2: URLパターンに合致するか
        # ※アンカーテキストに会議要素がない場合、単なる数字HTML等の一般的URLは候補から除外
        is_subpage_by_url = False
        if custom_re:
            is_subpage_by_url = bool(custom_re.search(href))
        elif DEFAULT_SUBPAGE_URL_REGEX.search(href):
            has_strong_url_kw = bool(re.search(r'(?:dai\d+|\d+kai|kaisai|gijisidai|gijiroku|session|meeting|bunkakai|r0?\d+/|h\d+/)', href, re.IGNORECASE))
            if is_subpage_by_text or has_strong_url_kw:
                is_subpage_by_url = True

        if is_subpage_by_text or is_subpage_by_url:
            seen.add(abs_clean)
            candidates.append(abs_url)

            # 親ページ側のアンカーおよび行コンテナから開催日を先行抽出
            parent_date = None
            anchor_dates = extract_clean_dates_from_html(t_clean)
            if anchor_dates:
                parent_date = anchor_dates[0]
            else:
                parent_container = a.find_parent(['tr', 'li', 'dd', 'p', 'div'])
                if parent_container:
                    c_text = parent_container.get_text(' ', strip=True)
                    c_dates = extract_clean_dates_from_html(c_text)
                    if c_dates:
                        parent_date = c_dates[0]

            meta_map[abs_url] = {
                "anchor_text": t_clean,
                "parent_date": parent_date
            }

    if return_meta:
        return candidates, meta_map
    return candidates

def _crawl_subpages(target_url, html, rule, quirk_note, pdf_pattern, existing_urls=None, recheck_recent=1, full_check=False):
    """サブページの深掘りクロールロジック（CR-14: 親ページ実リンク解析型・CR-23: 最新1件更新確認＆過去回再検査ゼロ化）"""
    subpage_meetings = []
    additional_materials = []
    all_extracted_dates = []

    # CR-14: 親ページHTML内の実在リンク（<a>タグ）から、アンカーテキストとURLパターンでサブページを確実に抽出
    filtered_subpages, subpage_meta = extract_actual_subpage_links(html, target_url, rule, return_meta=True)

    if filtered_subpages:
        # 最新と思われる順（降順）にソートして差分巡回フィルタを適用
        sorted_subpages = _sort_subpage_urls_by_recency(filtered_subpages)
        target_subpages, inc_stats = _filter_incremental_subpages(
            sorted_subpages,
            existing_urls,
            max_unvisited=50,
            max_recent=recheck_recent,
            full_check=full_check
        )
        if inc_stats["skipped_known"] > 0 or inc_stats["unvisited"] > 0:
            print(f"   [差分巡回 ({quirk_note})] 未登録 {inc_stats['unvisited']} 件, 更新確認 {inc_stats['recent_update']} 件, 既登録スキップ {inc_stats['skipped_known']} 件 (探索対象: 計 {inc_stats['total_targets']} 件)")
        else:
            print(f"   [2回目情報取得Engine ({quirk_note})] サブページ {len(target_subpages)} 件を深掘り巡回中...")

        for sub_url in target_subpages:
            parsed_url = urllib.parse.urlparse(sub_url)
            if parsed_url.scheme not in ('http', 'https'):
                continue
            if sub_url.lower().endswith('.pdf'):
                continue

            time.sleep(0.35)  # レートリミット遵守
            sub_html = fetch_url(sub_url)
            if sub_html:
                sub_soup = BeautifulSoup(sub_html, 'html.parser')
                sub_title = extract_page_title(sub_soup, rule, fallback_url=sub_url)

                sub_materials = parse_materials_from_html(sub_html, sub_url, pdf_pattern)
                
                # 2段階配付資料自動探索: もしPDF資料が0件（または議事録のみ）の場合、ページ内の明示的リンクを探索
                has_pdf = any(m.get("type") == "PDF" for m in sub_materials)
                if not has_pdf:
                    companion_candidates = []
                    for a in sub_soup.find_all('a', href=True):
                        h_lower = a['href'].lower()
                        if any(k in h_lower for k in ['gijishidai', 'shiryo', 'siryou', 'haifu']) and not h_lower.endswith('.pdf'):
                            comp_abs = urllib.parse.urljoin(sub_url, a['href'])
                            if comp_abs != sub_url and not _is_parent_or_nav_url(comp_abs, target_url) and not is_generic_index_url(comp_abs):
                                companion_candidates.append(comp_abs)
                    
                    for comp_url in list(dict.fromkeys(companion_candidates))[:3]:
                        time.sleep(0.35)
                        comp_html = fetch_url(comp_url)
                        if comp_html:
                            comp_mats = parse_materials_from_html(comp_html, comp_url, pdf_pattern)
                            comp_pdfs = [cm for cm in comp_mats if cm.get("type") == "PDF"]
                            if comp_pdfs:
                                for cp in comp_pdfs:
                                    if not any(m.get("url") == cp.get("url") for m in sub_materials):
                                        sub_materials.append(cp)
                                # 自身が議事録ページであれば議事録としても保持
                                if 'gijiroku' in sub_url.lower() and not any(m.get("url") == sub_url for m in sub_materials):
                                    sub_materials.append({
                                        "name": "議事録",
                                        "url": sub_url,
                                        "type": "HTML",
                                        "isPrivate": False
                                    })
                                break

                # 3段階配付資料自動展開: 抽出された資料リストに「会議資料」「資料」等のHTMLページがある場合、そのリンク先を取得して内部の末端PDF資料を展開
                html_materials = [m for m in sub_materials if (m.get('url', '').endswith('.html') or m.get('url', '').endswith('.htm'))]
                for hm in html_materials[:5]:
                    hm_url = hm.get('url')
                    hm_name = hm.get('name', '')
                    if any(k in hm_name for k in ['会議資料', '配付資料', '配布資料', '資料一覧', '資料']) or re.search(r'\d+kai\.html$', hm_url):
                        time.sleep(0.35)
                        hm_html = fetch_url(hm_url)
                        if hm_html:
                            expanded_mats = parse_materials_from_html(hm_html, hm_url, pdf_pattern)
                            for em in expanded_mats:
                                if em.get('type') == 'PDF' and not any(m.get('url') == em.get('url') for m in sub_materials):
                                    sub_materials.append(em)

                raw_sub_dates = extract_clean_dates_from_html(sub_html, rule.get("date_regex", DEFAULT_DATE_REGEX))
                norm_sub_dates = [normalize_japanese_numbers(d) for d in raw_sub_dates]
                # 親ページ側（リンク行・アンカー）から先行抽出した開催日をフォールバック適用
                if not norm_sub_dates and subpage_meta:
                    p_info = subpage_meta.get(sub_url, {})
                    p_date = p_info.get("parent_date")
                    if p_date:
                        norm_sub_dates.append(normalize_japanese_numbers(p_date))
                # CR-16: 本文および親リンクから日付が取れなかった場合、サブページURLから日付をフォールバック復元
                if not norm_sub_dates and sub_url:
                    url_date = _extract_date_from_url(sub_url)
                    if url_date:
                        norm_sub_dates.append(url_date)
                all_extracted_dates.extend(norm_sub_dates)

                subpage_meetings.append({
                    "subpageUrl": sub_url,
                    "name": sub_title,
                    "title": sub_title,
                    "extractedMaterialsCount": len(sub_materials),
                    "materials": sub_materials,
                    "extractedDates": list(set(norm_sub_dates))[:2]
                })
                additional_materials.extend(sub_materials)

    return subpage_meetings, additional_materials, all_extracted_dates


def _extract_meetings_from_parent_table(html, target_url, council_name, rule=None, pdf_pattern=None):
    """
    親ページ内のテーブル（<table>）を行（<tr>）単位で走査し、
    各開催回の「回次・開催日・配付資料リスト」を一体抽出する。
    """
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    base_tag = soup.find('base', href=True)
    page_base = urllib.parse.urljoin(target_url, base_tag['href']) if base_tag else target_url

    meetings = []
    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')
        if len(rows) < 2:
            continue

        # ヘッダー行の確認（回数、日時、開催日、資料、議題、議事、次第、年度等のキーワード）
        header_text = ' '.join(r.get_text(' ', strip=True) for r in rows[:2])
        is_candidate_table = any(k in header_text for k in ['回', '日', '資料', '議題', '議事', '次第', '年度', '開催'])
        if not is_candidate_table:
            continue

        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue

            row_text = row.get_text(' ', strip=True)
            norm_text = normalize_japanese_numbers(row_text)
            clean_search_text = re.sub(r'[\s\u2000-\u200f]+', '', norm_text)

            # 1. 回次の抽出
            sess_match = re.search(r'第\s*(\d+)\s*回', norm_text) or re.search(r'第(\d+)回', clean_search_text)
            round_num = int(sess_match.group(1)) if sess_match else None

            # 2. 日付の抽出（空白・全角スペース混入に対応した clean_search_text から抽出）
            date_matches = re.findall(r'(?:令和|平成)(?:\d+|元)年\d{1,2}月\d{1,2}日|\d{4}年\d{1,2}月\d{1,2}日|\d{4}[/-]\d{1,2}[/-]\d{1,2}', clean_search_text)
            if not date_matches:
                date_matches = re.findall(r'(?:令和|平成)\s*(?:\d+|元)\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|\d{4}[/-]\d{1,2}[/-]\d{1,2}', norm_text)
            meet_date = None
            for d in date_matches:
                clean_d = re.sub(r'[\s\u2000-\u200f]+', '', d)
                val = validate_and_normalize_date(clean_d)
                if val:
                    dt = parse_japanese_date(val)
                    if dt:
                        meet_date = dt.strftime('%Y/%m/%d')
                        break

            # 回次も日付も取れない行はヘッダーや名簿等のためスキップ
            if not round_num and not meet_date:
                continue

            # 3. 配付資料および個別URLの抽出
            row_materials = []
            row_official_url = target_url
            for a in row.find_all('a', href=True):
                href = a['href'].strip()
                if not href or href.startswith('#') or href.startswith('javascript:'):
                    continue
                abs_url = urllib.parse.urljoin(page_base, href)
                if is_generic_index_url(abs_url) or _is_parent_or_nav_url(abs_url, target_url):
                    continue

                raw_mat_name = a.get_text(' ', strip=True)
                clean_mat_name = re.sub(r'[\（\(\［\[]PDF.*?[）\)\］\]]', '', raw_mat_name, flags=re.IGNORECASE).strip()

                if not clean_mat_name or clean_mat_name in ('PDF', 'ダウンロード', 'リンク', 'こちら'):
                    parent_cell = a.find_parent(['td', 'th'])
                    if parent_cell:
                        cell_txt = parent_cell.get_text(' ', strip=True)
                        clean_cell_txt = re.sub(r'[\（\(]PDF[／/形式\:\s\d\.\,KBMB]+\s*[\）\)]', '', cell_txt).strip()
                        clean_cell_txt = re.sub(r'［PDF形式：\d+.*?］', '', clean_cell_txt).strip()
                        if clean_cell_txt and clean_cell_txt != clean_mat_name:
                            clean_mat_name = clean_cell_txt[:60]

                if not clean_mat_name:
                    clean_mat_name = "配付資料"

                is_pdf = href.lower().endswith(('.pdf', '.docx', '.xlsx', '.doc', '.xls')) or '/pdf/' in href.lower()
                is_html_doc = any(k in href.lower() for k in ['gijiroku', 'gijiyoshi', 'proceedings']) or any(k in clean_mat_name for k in ['議事録', '議事要旨'])

                if is_pdf:
                    row_materials.append({
                        "name": clean_mat_name,
                        "url": abs_url,
                        "type": "PDF"
                    })
                elif is_html_doc:
                    row_materials.append({
                        "name": clean_mat_name,
                        "url": abs_url,
                        "type": "HTML"
                    })
                elif (href.endswith('.html') or href.endswith('.htm')) and row_official_url == target_url:
                    row_official_url = abs_url

            # 資料も個別URLもない行はスキップ
            if not row_materials and row_official_url == target_url:
                continue

            # 会議名・タイトルの決定
            if round_num:
                meet_title = f"第{round_num}回 {council_name}"
            else:
                meet_title = f"{council_name}"

            meetings.append({
                "subpageUrl": row_official_url,
                "name": meet_title,
                "title": meet_title,
                "extractedMaterialsCount": len(row_materials),
                "materials": row_materials,
                "extractedDates": [meet_date] if meet_date else [],
                "isFromParentTable": True
            })

    return meetings

def clean_html_for_dates(html_str):
    """ヘッダー・フッター・サイドバー・パンくず・スキップリンク等のノイズを除去して本文ブロックを抽出"""
    if not html_str:
        return ""
    try:
        soup = BeautifulSoup(html_str, 'html.parser')
        # 1. ノイズタグの除去
        for tag in soup(['nav', 'aside', 'footer', 'script', 'style', 'header']):
            tag.decompose()

        # 2. スキップリンク・ジャンプリンクの事前明示的除去
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            aid = a_tag.get('id', '')
            acls = ' '.join(a_tag.get('class', []))
            if href.startswith('#') and any(k in href.lower() for k in ['content', 'main', 'skip', 'jump']):
                a_tag.decompose()
            elif any(k in aid.lower() for k in ['jump', 'skip', 'navskip']):
                a_tag.decompose()
            elif any(k in acls.lower() for k in ['jump', 'skip', 'navskip']):
                a_tag.decompose()

        # 3. ナビゲーション・フッター系ID/Class要素の除去
        for el in soup.find_all(id=re.compile(r'(side|nav|footer|header|menu|breadcrumb|popup|modal)', re.I)):
            if el.name not in ('body', 'html'):
                el.decompose()
        for el in soup.find_all(class_=re.compile(r'(side|nav|footer|header|menu|breadcrumb|popup|modal)', re.I)):
            if el.name not in ('body', 'html'):
                el.decompose()

        # 4. 本文ブロックコンテナの探索
        # main または article タグが存在すれば最優先
        main_tag = soup.find(['main', 'article'])
        if main_tag and len(main_tag.get_text(strip=True)) > 50:
            return str(main_tag)

        # 特定クラス（p-details 等の会議詳細コンテナ）が存在すれば優先
        detail_container = soup.find('div', class_=re.compile(r'(p-details|meeting-detail|kaigi-detail)', re.I))
        if detail_container and len(detail_container.get_text(strip=True)) > 50:
            return str(detail_container)

        block_tags = ['div', 'section']
        candidates = []
        # \b(main|content)\b に厳格マッチさせ、小さなパーツへの縮退を防止
        for tag_name in block_tags:
            for el in soup.find_all(tag_name, id=re.compile(r'\b(main|content)\b|^l-(main|content)', re.I)):
                candidates.append(el)
            for el in soup.find_all(tag_name, class_=re.compile(r'\b(main|content)\b|^l-(main|content)', re.I)):
                candidates.append(el)

        body_text_len = len(soup.body.get_text(strip=True)) if soup.body else 0
        if candidates:
            best_el = max(candidates, key=lambda el: len(el.get_text(strip=True)))
            best_len = len(best_el.get_text(strip=True))
            # 候補のテキストが極端に短くなく、かつbodyの重要部分を占めている場合のみ採用
            if best_len > 100 and (body_text_len == 0 or best_len >= body_text_len * 0.3):
                return str(best_el)

        return str(soup.body) if soup.body else str(soup)
    except Exception:
        return html_str

def validate_and_normalize_date(date_str):
    """
    抽出された日付文字列が実在する妥当な日付（1990年〜2035年、月1〜12、日1〜31）であるかを検証し、
    正規化された文字列または None を返す。
    """
    if not date_str or not isinstance(date_str, str):
        return None
    dt = parse_japanese_date(date_str)
    if not dt:
        return None
    max_year = datetime.now().year + 2
    if 1990 <= dt.year <= max_year and 1 <= dt.month <= 12 and 1 <= dt.day <= 31:
        return date_str.strip()
    return None

def extract_clean_dates_from_html(html_str, date_regex_pattern=r'(?<![\d\w\/\-])(?:(?:令和|平成)(?:\d+|元)年\d{1,2}月\d{1,2}日|\d{4}年\d{1,2}月\d{1,2}日|\d{4}[/-]\d{1,2}[/-]\d{1,2})(?![\d\w\/\-])'):
    """更新日・掲載日などのノイズや不正パターンを除去して会議開催日を抽出"""
    cleaned_html = clean_html_for_dates(html_str)
    # 全角数字を半角に正規化
    cleaned_html = normalize_japanese_numbers(cleaned_html)
    # 年号併記の括弧を除去 (例: 2026年（令和8年）3月24日 -> 2026年3月24日)
    cleaned_html = re.sub(r'(\d{4}年)[（\(][^）\)\n]+[）\)]\s*(\d{1,2}月\d{1,2}日)', r'\1\2', cleaned_html)
    cleaned_html = re.sub(r'((?:令和|平成)(?:\d+|元)年)[（\(][^）\)\n]+[）\)]\s*(\d{1,2}月\d{1,2}日)', r'\1\2', cleaned_html)
    raw_dates = re.findall(date_regex_pattern, cleaned_html)
    
    # 優先判定: 「実施日」「開催日時」「開催日」に直結する日付文字列があれば最優先で抽出
    explicit_matches = re.findall(r'(?:実施日|開催日|開催日時)\s*[:：]?\s*((?:(?:令和|平成)(?:\d+|元)年|\d{4}年)\d{1,2}月\d{1,2}日|\d{4}[/-]\d{1,2}[/-]\d{1,2})', html_str)
    valid_explicit = []
    if explicit_matches:
        for em in explicit_matches:
            vd = validate_and_normalize_date(normalize_japanese_numbers(em))
            if vd and vd not in valid_explicit:
                valid_explicit.append(vd)

    # 「更新日: 2024年X月X日」「掲載日: ...」などの直前ラベル付きの日付を除外
    filtered_dates = []
    for d in raw_dates:
        # 直前ラベルに「更新日」「掲載日」「公表日」「作成日」「施行期日」「適用期日」等が含まれる場合は除外
        escaped_d = re.escape(d)
        if re.search(r'(?:更新日|最終更新|掲載日|公表日|作成日|ページID|copyright|施行期日|施行日|施行|適用期日|適用日|公布の日|公布日|施行予定|適用予定)[^。\n]{0,30}' + escaped_d, cleaned_html, re.I):
            continue
        valid_d = validate_and_normalize_date(d)
        if valid_d:
            filtered_dates.append(valid_d)

    # 明示的な開催日/実施日を最優先とし、残りの抽出日付を統合（順序保持・重複排除）
    combined_dates = []
    for vd in valid_explicit + filtered_dates:
        if vd not in combined_dates:
            combined_dates.append(vd)

    return combined_dates


def calculate_past_year_count(extracted_dates, ref_date=None):
    """抽出された日付から過去1年間の開催数を算出。トップページ等に日付がなければ ('-', False) を返す"""
    if ref_date is None:
        ref_date = datetime.now()
    if not extracted_dates:
        return "-", False
    
    parsed_dates = []
    for d_str in extracted_dates:
        dt = parse_japanese_date(d_str)
        if dt:
            parsed_dates.append(dt)
            
    if not parsed_dates:
        return "-", False
        
    one_year_ago = ref_date - timedelta(days=365)
    unique_past_year_dates = set([dt.strftime('%Y-%m-%d') for dt in parsed_dates if one_year_ago <= dt <= ref_date])
    return len(unique_past_year_dates), True

def discover_subpage_links(html, base_url):
    """トップページHTMLから会議の個別ページへの実在リンクを発見する（CR-14: 投機的類推排除）"""
    candidates = extract_actual_subpage_links(html, base_url)
    
    # 優先度ソート: 議事次第（gijishidai）、配付資料（shiryo）、ディレクトリトップ（index.html/末尾スラッシュ）を議事録単体より優先
    def subpage_priority(url):
        u_low = url.lower()
        if any(k in u_low for k in ['gijishidai', 'shiryo', 'siryou', 'haifu']):
            return 3
        if u_low.endswith('/') or u_low.endswith('/index.html') or 'dai' in u_low or 'kai' in u_low:
            return 2
        if 'gijiroku' in u_low:
            return 1
        return 0

    candidates.sort(key=subpage_priority, reverse=True)
    return candidates[:12]  # 最大12サブページを優先巡回

def extract_via_llm_single(url, html, target_name):
    """単一ページに対してLLM抽出を実行する"""
    global LLM_QUOTA_BLOCKED
    model = get_gemini_model()
    if not model or LLM_QUOTA_BLOCKED:
        return [], []
        
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup(["script", "style"]):
        script.extract()
    body_text = soup.get_text(separator=' ', strip=True)
    body_text = re.sub(r'\s+', ' ', body_text)[:5000]
    
    prompt = f"""
以下の官公庁会議（{target_name}）のウェブページの内容から、配付資料のリストと開催日を抽出してください。
URL: {url}

必ず以下のJSONスキーマに従って出力してください。Markdownコードブロックは含めないでください。
{{
  "materials": [
    {{"name": "資料名", "url": "資料のURL"}}
  ],
  "extractedDates": [
    "2023-12-01", "2024-01-15" (日付の配列、YYYY-MM-DD形式、和暦は西暦に変換)
  ]
}}

本文:
{body_text}
"""
    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        if result_text.startswith("```json"): result_text = result_text[7:]
        if result_text.startswith("```"): result_text = result_text[3:]
        if result_text.endswith("```"): result_text = result_text[:-3]
        
        data = json.loads(result_text.strip())
        materials = data.get("materials", [])
        
        for m in materials:
            if m.get("url") and not m["url"].startswith("http"):
                m["url"] = urllib.parse.urljoin(url, m["url"])
                
        return materials, data.get("extractedDates", [])
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "quota" in err_str.lower():
            LLM_QUOTA_BLOCKED = True
            print(f"[WARN] Gemini API クォータ制限 (429) を検知しました。以降の巡回は高速 Heuristic ルール抽出モードで安全に継続します。")
        else:
            print(f"[WARN] LLM Extraction failed for {url}: {e}")
        return [], []

def extract_via_llm(target_url, html, target_name):
    """LLM抽出（トップページ + サブページ巡回）"""
    global LLM_QUOTA_BLOCKED
    model = get_gemini_model()
    if not model or LLM_QUOTA_BLOCKED:
        return [], []
    
    # Step 1: トップページ抽出
    all_materials, all_dates = extract_via_llm_single(target_url, html, target_name)
    
    # Step 2: サブページ発見・巡回
    if not LLM_QUOTA_BLOCKED:
        subpage_urls = discover_subpage_links(html, target_url)
        if subpage_urls:
            print(f"   [LLM Subpage Crawl] {len(subpage_urls)} 件のサブページを巡回中...")
            for sub_url in subpage_urls:
                if LLM_QUOTA_BLOCKED:
                    break
                sub_html = fetch_url(sub_url)
                if sub_html:
                    sub_materials, sub_dates = extract_via_llm_single(sub_url, sub_html, target_name)
                    all_materials.extend(sub_materials)
                    all_dates.extend(sub_dates)
    
    # 重複排除
    seen_urls = set()
    unique_materials = []
    for m in all_materials:
        key = m.get("url", m.get("name", ""))
        if key not in seen_urls:
            seen_urls.add(key)
            unique_materials.append(m)
    
    unique_dates = list(set(all_dates))
    return unique_materials, unique_dates

def get_unconfirmed_meetings_count(data):
    """docs/data.json の meetings 内で開催日未確定（2099/01/01 または isDateUnconfirmed: True）の開催回件数を集計"""
    if not data or not isinstance(data, dict):
        return 0
    count = 0
    for m in data.get("meetings", []):
        d = str(m.get("date", "")).strip()
        if d.startswith("2099") or m.get("isDateUnconfirmed"):
            count += 1
    return count

def determine_crawl_result(unique_materials, norm_date_matches, subpage_meetings=None, page_title=""):
    """
    抽出された配付資料、開催日、開催回データ、ページタイトルの品質を総合評価し、
    クロール成否（success / partial / failed）およびその理由（resultReason）を判定する。
    """
    materials = unique_materials or []
    dates = norm_date_matches or []
    subpages = subpage_meetings or []
    title = (page_title or "").strip()

    has_materials = len(materials) > 0
    has_pdf = any(m.get("type") == "PDF" or str(m.get("url", "")).lower().endswith(".pdf") for m in materials)

    # 正常な実在開催日（2099ダミーや無効プレフィックス 1312 を除く）
    valid_dates = [
        d for d in dates
        if d and not str(d).startswith("2099") and not str(d).startswith("1312")
    ]
    has_valid_dates = len(valid_dates) > 0
    has_subpages = len(subpages) > 0
    is_generic_title = any(kw in title for kw in GENERIC_TITLE_KEYWORDS) if title else False

    # 1. サブページ開催回または親テーブル開催回が抽出されている場合
    if has_subpages:
        sub_with_mats = any(len(s.get("materials", [])) > 0 for s in subpages)
        sub_with_dates = any(len(s.get("extractedDates", [])) > 0 for s in subpages)
        if sub_with_mats and (sub_with_dates or has_valid_dates):
            return "success", f"開催回 {len(subpages)} 件を検出（資料・日付完備）"
        elif sub_with_mats:
            return "success", f"開催回 {len(subpages)} 件を検出（資料完備）"
        else:
            return "partial", f"開催回 {len(subpages)} 件を検出したが資料が0件"

    # 2. トップページ単独での抽出
    if has_materials and has_valid_dates:
        if is_generic_title:
            return "partial", f"資料 {len(materials)} 件・開催日 {len(valid_dates)} 件を検出したがタイトルが汎用見出し（{title}）"
        if has_pdf:
            return "success", f"PDF配付資料 {len(materials)} 件・開催日 {len(valid_dates)} 件を正常取得"
        else:
            return "success", f"配付資料 {len(materials)} 件・開催日 {len(valid_dates)} 件を正常取得"

    if has_materials and not has_valid_dates:
        reason = "開催日未取得（資料のみ検出）"
        if dates and any(str(d).startswith("2099") for d in dates):
            reason = "開催日が未確定（2099/01/01ダミー）かつ資料のみ検出"
        return "partial", reason

    if not has_materials and has_valid_dates:
        return "partial", f"開催日のみ検出（資料0件: {valid_dates[0]}）"

    return "failed", "配付資料・開催日・個別開催回のいずれも検出できませんでした"

def execute_rule_retrieval(target, html, rule_item, use_llm=False, recheck_recent=1, full_check=False):
    """多段情報取得Engine (高速Heuristicルール優先 → 未抽出時LLMフォールバック)"""
    global LLM_QUOTA_BLOCKED
    rule = rule_item.get("rules", {})
    quirk_note = rule_item.get("ministryQuirk", "標準抽出ルール")
    
    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    page_title = title_match.group(1).strip() if title_match else target["name"]

    unique_materials = []
    norm_date_matches = []
    subpage_meetings = []
    extraction_method = "none"
    
    # Stage 1: 高速・網羅的な Heuristic ルール抽出 (scrapingRules 準拠)
    pdf_pattern = rule.get("pdf_selector", r'href=["\']([^"\']+\.pdf)["\']')
    top_materials = parse_materials_from_html(html, target["url"], pdf_pattern)
    
    # ディープクロールは常に実行（スマート差分探索エンジンによりサブページを深掘りして配付資料を収集）
    all_extracted_dates = []
    existing_urls = target.get("existing_meeting_urls")
    new_meetings, new_materials, new_dates = _crawl_subpages(
        target["url"], html, rule, quirk_note, pdf_pattern, existing_urls=existing_urls,
        recheck_recent=recheck_recent, full_check=full_check
    )
    subpage_meetings.extend(new_meetings)
    top_materials.extend(new_materials)
    all_extracted_dates.extend(new_dates)

    # 親ページテーブル解析の実行（テーブル構造から各開催回の回次・日付・資料を直接抽出）
    table_meetings = _extract_meetings_from_parent_table(html, target["url"], target["name"], rule, pdf_pattern)
    if table_meetings:
        print(f"   [親ページテーブル解析] 親ページ内から {len(table_meetings)} 件の開催回を検出しました。")
        subpage_meetings.extend(table_meetings)
        for tm in table_meetings:
            top_materials.extend(tm.get("materials", []))
            all_extracted_dates.extend(tm.get("extractedDates", []))

    seen_keys = set()
    for m in top_materials:
        key = m["url"] if m["url"] != "#" else m["name"]
        if key not in seen_keys:
            seen_keys.add(key)
            unique_materials.append(m)

    raw_date_matches = extract_clean_dates_from_html(html, rule.get("date_regex", DEFAULT_DATE_REGEX))
    top_norm_dates = [normalize_japanese_numbers(d) for d in raw_date_matches]
    all_extracted_dates.extend(top_norm_dates)
    norm_date_matches = list(dict.fromkeys(all_extracted_dates))
    
    if unique_materials or norm_date_matches or subpage_meetings:
        extraction_method = "rule"
    else:
        # Stage 2: ルールで0件の場合のみ LLM (Gemini API) フォールバックを試行
        if use_llm and not LLM_QUOTA_BLOCKED and get_gemini_model():
            print(f"   [Stage 2 Fallback] ルール未検出 → LLM Extraction (Gemini API: gemini-3.8-flash) を試行...")
            materials, dates = extract_via_llm(target["url"], html, target["name"])
            if materials or dates:
                unique_materials = materials
                norm_date_matches = dates
                extraction_method = "llm"
                print(f"   [Stage 2 OK] LLMフォールバック抽出成功: 資料 {len(materials)} 件, 日付 {len(dates)} 件")
            else:
                extraction_method = "none"

    past_year_count, has_top_page_dates = calculate_past_year_count(norm_date_matches)

    # 抽出結果の判定（CR-12: determine_crawl_result による品質・成否の精緻化）
    crawl_result, result_reason = determine_crawl_result(
        unique_materials, norm_date_matches, subpage_meetings, page_title
    )

    scraped_item = {
        "councilId": target["id"],
        "councilName": target["name"],
        "ministry": target["ministry"],
        "officialUrl": target["url"],
        "scrapedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ruleApplied": rule_item.get("rule_id", "rule-default"),
        "extractionMethod": extraction_method,
        "crawlResult": crawl_result,
        "resultReason": result_reason,
        "ministryQuirk": quirk_note,
        "pageTitle": page_title,
        "pastYearCount": past_year_count,
        "hasTopPageDates": has_top_page_dates,
        "totalExtractedMaterials": len(unique_materials),
        "materials": unique_materials,
        "extractedDates": list(set(norm_date_matches))[:5],
        "subpageMeetings": subpage_meetings
    }
    return scraped_item


def is_generic_index_url(url, title=""):
    """報道発表インデックスやポータルトップ・開催状況一覧・「その他情報」等の汎用インデックスURLかどうかを判定する"""
    if not url:
        return True
    if _GENERIC_INDEX_URL_PATTERNS.search(url.lower()):
        return True
    if title:
        t_clean = title.strip()
        if t_clean in _GENERIC_INDEX_EXACT_TITLES:
            return True
        if any(k in t_clean for k in _GENERIC_INDEX_TITLE_KEYWORDS):
            return True
    return False

def is_preliminary_notice_page(url, title=""):
    """
    開催案内・事前告知ページ（例: .../kaisai/index.html, .../annai/..., .../kaisaiannai/..., 〜の開催について）や資料未添付の議事要旨・議事録単体ページであるかを判定。
    これらは資料が掲載される会議ページではないため、独立した会議として追加しない。
    """
    if not url and not title:
        return False
    u_lower = (url or "").lower()
    # URLに /kaisai/ や /annai/ や /kaisaiannai/ や /online_kaisai 等が含まれる場合
    if re.search(r'/(?:kaisai|kaisaiannai|online_kaisai|annai)/', u_lower) or u_lower.endswith('/kaisai.html') or 'kaisaiannai' in u_lower or '_annai_' in u_lower:
        return True
    # タイトルから末尾の省庁・委員会名サフィックスを除去して判定
    t_clean = (title or "").strip()
    t_clean = re.sub(r'[\s｜\|].*?(?:厚生労働省|内閣府|内閣官房|財務省|金融庁|法務省|経済産業省|文部科学省|総務省|外務省|農林水産省|国土交通省|環境省|防衛省|デジタル庁|こども家庭庁|食品安全委員会|原子力規制委員会|消費者庁|警察庁|文化庁|スポーツ庁|観光庁|気象庁|林野庁|水産庁).*$', '', t_clean).strip()
    # 末尾の括弧表記（例: （非公開）、（WEB開催）、（持ち回り開催）等）を除去して判定
    t_clean = re.sub(r'[\(（][^\)）]+[\)）]$', '', t_clean).strip()
    if re.search(r'(?:の開催について|の開催案内|の開催のお知らせ|開催のお知らせ|開催案内|傍聴の案内|傍聴について|の開催概要について|議事要旨|議事録)$', t_clean):
        return True
    return False


def _resolve_meeting_date(sub_dates, sub_title, sub_url):
    """
    サブページの抽出日付、タイトル、URLから開催日を特定し、
    YYYY/MM/DD 形式の日付文字列と is_date_unconfirmed (未特定ダミー 2099/01/01 フラグ) を返す。
    """
    meet_date = ""
    is_date_unconfirmed = False
    if sub_dates:
        dt = parse_japanese_date(sub_dates[0])
        if dt:
            meet_date = dt.strftime("%Y/%m/%d")
        else:
            m_iso = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', str(sub_dates[0]))
            if m_iso:
                meet_date = f"{int(m_iso.group(1)):04d}/{int(m_iso.group(2)):02d}/{int(m_iso.group(3)):02d}"

    if not meet_date and sub_title:
        dt = parse_japanese_date(sub_title)
        if dt:
            meet_date = dt.strftime("%Y/%m/%d")

    if not meet_date and sub_url:
        # CR-16: URL内の日付パターンから安全・厳格に抽出・復元
        url_extracted = _extract_date_from_url(sub_url)
        if url_extracted:
            meet_date = url_extracted

    # 開催日が特定できない場合は当日日付ではなくダミー日付(2099/01/01)を設定（管理画面で要確認対象とする）
    if not meet_date:
        meet_date = "2099/01/01"
        is_date_unconfirmed = True

    return meet_date, is_date_unconfirmed


def _build_new_meeting(target, sub, clean_materials_list, sess_nums, meet_date, is_date_unconfirmed, existing_c_meets, added_count, existing_meeting_ids, council_parent_url):
    """
    新規開催回（meeting）オブジェクトを生成して返す。
    4セグメントID生成、重複ID回避、タイトル正規化、公式URL解決を実施。
    """
    council_id = target["id"]
    council_name = target["name"]
    ministry = target.get("ministry", "")
    sub_title = sub.get("title", "").strip()

    # 会議IDの生成（4セグメント統一形式: {council_id}-{YYYYMMDD}-{回次000またはs00}）
    clean_d = meet_date.replace("/", "").replace("-", "")
    sess_suffix = f"{sorted(sess_nums)[0]:03d}" if sess_nums else f"s{len(existing_c_meets) + added_count + 1:02d}"
    new_meet_id = f"{council_id}-{clean_d}-{sess_suffix}"

    # 重複ID回避
    if new_meet_id in existing_meeting_ids:
        new_meet_id = f"{council_id}-{clean_d}-{sess_suffix}_{added_count+1}"

    # タイトルの正規化
    formatted_title = sub_title
    # 開催案内プレフィックス/サフィックスのクリーンアップ
    if formatted_title:
        formatted_title = re.sub(r'「(.*?)」を開催します.*$', r'\1', formatted_title)
        formatted_title = re.sub(r'を開催します.*$', '', formatted_title)
        formatted_title = re.sub(r'（開催案内）$', '', formatted_title)
        formatted_title = re.sub(r'\(開催案内\)$', '', formatted_title)
        formatted_title = re.sub(r'の開催について$', '', formatted_title)
        formatted_title = re.sub(r'[（\(](?:令和|平成)(?:\d+|元)年度.*?[）\)]$', '', formatted_title)
        formatted_title = formatted_title.strip()

    is_generic = not formatted_title or formatted_title.startswith("http") or any(kw == formatted_title for kw in GENERIC_TITLE_KEYWORDS)
    if is_generic:
        if sess_nums:
            formatted_title = f"第{sorted(sess_nums)[0]}回 {council_name}"
        else:
            date_label = "開催日不明" if is_date_unconfirmed else meet_date
            formatted_title = f"{council_name} ({date_label})"
    elif council_name not in formatted_title and sess_nums:
        formatted_title = f"第{sorted(sess_nums)[0]}回 {council_name}"

    if is_date_unconfirmed and "開催日不明" not in formatted_title:
        formatted_title = f"{formatted_title} (開催日不明)"

    # 汎用報道URLや資料未掲載の場合は親の会議体URLを設定
    resolved_meet_url = sub.get("subpageUrl")
    if not resolved_meet_url or is_generic_index_url(resolved_meet_url, sub_title):
        resolved_meet_url = council_parent_url

    new_meeting_obj = {
        "id": new_meet_id,
        "councilId": council_id,
        "name": formatted_title,
        "date": meet_date,
        "officialUrl": resolved_meet_url,
        "materials": clean_materials_list,
        "isNewlyDiscovered": True,
        "discoveredAt": datetime.now().strftime("%Y/%m/%d %H:%M")
    }
    if is_date_unconfirmed:
        new_meeting_obj["isDateUnconfirmed"] = True

    return new_meeting_obj


def sync_new_meetings_from_crawl(data, target, scraped_item):
    """
    クロール時に検出されたサブページ（個別開催回）から、
    1. 未登録の新規開催回を自動検知して docs/data.json の meetings 配列に追加する。
    2. 開催前・未掲載で親URLのままだった既存会議に、新たに個別資料ページが公開された場合は officialUrl と資料を自動昇格・更新する。
    ※ 既存の手動作成済み会議（manualLock: true かつ個別資料登録済み）は保護する。
    """
    if not scraped_item:
        return 0

    subpages = scraped_item.get("subpageMeetings", [])
    if not subpages:
        return 0

    council_id = target["id"]
    council_name = target["name"]
    council_parent_url = target.get("officialUrl") or target.get("url", "")
    ministry = target["ministry"]
    meetings = data.setdefault("meetings", [])

    existing_c_meets = [m for m in meetings if m.get("councilId") == council_id]
    existing_urls = {m.get("officialUrl", "").rstrip("/"): m for m in existing_c_meets if m.get("officialUrl")}
    existing_names = {m.get("name", ""): m for m in existing_c_meets if m.get("name")}
    existing_meeting_ids = {m.get("id") for m in meetings if m.get("id")}
    existing_sessions = set()
    for m in existing_c_meets:
        sess = extract_session_numbers(m.get("name", "") + " " + m.get("officialUrl", "") + " " + m.get("id", ""))
        existing_sessions.update(sess)

    added_count = 0
    for sub in subpages:
        sub_url = sub.get("subpageUrl", "").rstrip("/")
        sub_title = (sub.get("name") or sub.get("title") or "").strip()
        sub_mats = sub.get("materials", [])
        sub_dates = sub.get("extractedDates", [])

        # 汎用インデックスURLや内閣官房「その他情報」等は会議ページとして登録しない
        if is_generic_index_url(sub_url, sub_title):
            continue

        # 事前開催案内ページ（資料なしの事前告知）は会議ページとして登録しない
        if is_preliminary_notice_page(sub_url, sub_title) and not sub_mats:
            continue

        # CR-19 / CR-20: 共通ナビ・広報リンク・組織常設資料およびジェネリックタイトルの登録遮断ガード
        sub_title_clean = re.sub(r'\s*\([^\)]*開催日不明[^\)]*\)$', '', sub_title).strip()
        sub_title_clean = re.sub(r'^[0-9０-９一二三四五六七八九十]+[．.、\s]+', '', sub_title_clean).strip()
        if any(kw in sub_title for kw in COMMON_NAV_KEYWORDS) or any(kw in sub_title_clean for kw in COMMON_NAV_KEYWORDS):
            continue
        if any(kw in sub_title for kw in ORGANIZATION_DOC_KEYWORDS) or any(kw in sub_title_clean for kw in ORGANIZATION_DOC_KEYWORDS):
            continue
        if any(kw == sub_title or kw == sub_title_clean for kw in GENERIC_TITLE_KEYWORDS) or '食の安全、を科学する' in sub_title:
            continue

        # 親会議体への下部組織・専門家会合の誤混入ガード（例: 税制調査会(cao-zei_cho)にEBPM等の専門家会合が混入するのを防止）
        if council_id == "cao-zei_cho":
            if any(k in sub_url.lower() for k in ['/ebpm/', '/life/', '/digital-noukan/', '/noukan/', '/sozoku-zoyo/', '/renketsu/', '/rougo/', '/koku-han/', '/discussion']) or "専門家会合" in sub_title or "ディスカッショングループ" in sub_title:
                continue
        if council_id == "cao-cstp":
            if any(k in sub_url.lower() for k in ['kaisaiannai', 'bridge', 'brige_wg']) or any(k in sub_title for k in ['ワーキンググループ', 'WG', 'BRIDGE', '中間評価']):
                continue

        # 他省庁URLの誤混入ガード（例: MHLW会議体にMETIのURLが混入するのを防止）
        ministry_code = (ministry or "").upper()
        if ministry_code:
            parsed_sub = urllib.parse.urlparse(sub_url)
            sub_host = parsed_sub.netloc.lower()
            if "example.com" not in sub_host and "localhost" not in sub_host:
                other_ministry_domains = _OTHER_MINISTRY_DOMAINS_MAP.get(ministry_code, ())
                if any(other_d in sub_host for other_d in other_ministry_domains):
                    continue

        # 開催回番号の抽出
        sess_nums = extract_session_numbers(sub_title + " " + sub_url)

        # 資料配列の構築（配付資料の名称属性は 'name' で厳格統一）
        clean_materials_list = []
        for mat in sub_mats:
            mat_name = (mat.get("name") or mat.get("title") or "").strip()
            mat_url = mat.get("url", "").strip()
            mat_type = mat.get("type", "PDF")
            if not mat_url or mat_url == "#" or mat_url == sub_url:
                continue
            mat_item = {
                "name": mat_name if mat_name else os.path.basename(mat_url),
                "url": mat_url
            }
            if mat_type and mat_type not in ("PDF", "pdf"):
                mat_item["type"] = mat_type
            if mat.get("isPrivate"):
                mat_item["isPrivate"] = True
            clean_materials_list.append(mat_item)

        # --- A. 既存会議の自動昇格・更新（資料未掲載・親URLだった会議が開催日後に個別資料ページを検出した場合） ---
        if sess_nums and any(s in existing_sessions for s in sess_nums):
            matched_existing = []
            for m in existing_c_meets:
                m_sess = extract_session_numbers(m.get("name", "") + " " + m.get("officialUrl", "") + " " + m.get("id", ""))
                if any(s in m_sess for s in sess_nums):
                    matched_existing.append(m)

            for ex_m in matched_existing:
                curr_url = ex_m.get("officialUrl", "").rstrip("/")
                curr_mats = ex_m.get("materials", [])
                
                is_parent_or_generic = (curr_url == council_parent_url.rstrip("/") or is_generic_index_url(curr_url))
                has_no_mats = len(curr_mats) == 0
                has_new_valid_subpage = (sub_url and not is_generic_index_url(sub_url, sub_title) and sub_url != council_parent_url.rstrip("/"))

                can_upgrade_url = (is_parent_or_generic and has_new_valid_subpage)
                can_update_mats = (has_no_mats and clean_materials_list)

                if (can_upgrade_url or can_update_mats) and clean_materials_list:
                    if can_upgrade_url:
                        ex_m["officialUrl"] = sub.get("subpageUrl")
                    ex_m["materials"] = clean_materials_list
                    ex_m["lastUpdatedFromCrawl"] = datetime.now().strftime("%Y/%m/%d %H:%M")
                    print(f"  [✨ 資料ページ自動更新] [{ex_m.get('date')}] {ex_m.get('name')} (URL: {sub_url}, 資料: {len(clean_materials_list)}件)")
                    added_count += 1
            continue

        # 既にURLまたはタイトルが完全一致している場合はスキップ
        # ※親URLと同じURL（親テーブル抽出等）の場合はURL一致スキップをパスし、回次・日付チェックへ進む
        is_parent_url = (sub_url == council_parent_url.rstrip("/"))
        if sub_url and not is_parent_url and sub_url in existing_urls:
            continue
        if sub_title and sub_title in existing_names:
            continue

        # --- B. 新規開催回の追加 ---
        meet_date, is_date_unconfirmed = _resolve_meeting_date(sub_dates, sub_title, sub_url)

        # 開催日未確認（2099/01/01）の場合の厳格ガード（資料0件またはジェネリックタイトルは登録禁止）
        if is_date_unconfirmed:
            if not clean_materials_list:
                continue
            if any(kw in sub_title for kw in GENERIC_TITLE_KEYWORDS) or any(kw in sub_title for kw in COMMON_NAV_KEYWORDS) or any(kw in sub_title for kw in ORGANIZATION_DOC_KEYWORDS):
                continue

        # 同一会議体・同一日付の重複チェック（同日重複の自動防止および資料マージ）
        if not is_date_unconfirmed:
            same_date_meets = [m for m in existing_c_meets if m.get("date") == meet_date]
            if same_date_meets:
                # 既に同一日付の会議が存在する場合、資料のみを既存会議にマージして新規追加はスキップ
                for ex_m in same_date_meets:
                    ex_mats = ex_m.setdefault("materials", [])
                    ex_mat_urls = {mat.get("url") for mat in ex_mats if mat.get("url")}
                    for new_mat in clean_materials_list:
                        if new_mat.get("url") not in ex_mat_urls:
                            ex_mats.append(new_mat)
                            ex_mat_urls.add(new_mat.get("url"))
                continue
        new_meeting = _build_new_meeting(
            target=target,
            sub=sub,
            clean_materials_list=clean_materials_list,
            sess_nums=sess_nums,
            meet_date=meet_date,
            is_date_unconfirmed=is_date_unconfirmed,
            existing_c_meets=existing_c_meets,
            added_count=added_count,
            existing_meeting_ids=existing_meeting_ids,
            council_parent_url=council_parent_url
        )

        meetings.append(new_meeting)
        existing_meeting_ids.add(new_meeting["id"])
        existing_urls[sub_url] = new_meeting
        meet_name = new_meeting.get("name") or ""
        existing_names[meet_name] = new_meeting
        for s in sess_nums:
            existing_sessions.add(s)
        added_count += 1
        log_prefix = "⚠️ [開催日不明(2099/01/01)]" if is_date_unconfirmed else "✨ [新規開催回自動追加]"
        print(f"  {log_prefix} [{meet_date}] {meet_name} (ID: {new_meeting['id']}, 資料: {len(clean_materials_list)}件)")

    if added_count > 0:
        # 日付降順に再ソート
        meetings.sort(key=lambda x: x.get("date", ""), reverse=True)
        # 会議体の pastYearCount を更新
        for c in data.get("councils", []):
            if c.get("id") == council_id:
                c_meets = [m for m in meetings if m.get("councilId") == council_id]
                c["pastYearCount"] = len(c_meets)
                break

    return added_count


def update_crawl_status(data, council_id, scraped_item, failure_reason=None):
    """data.json の councils 配列内の該当会議体に crawlStatus を記録する。
    manualLock: true が設定された会議体はクロールステータスのみ更新し、
    officialUrl / name / description 等のコアフィールドを上書きしない。"""
    for council in data.get("councils", []):
        if council.get("id") == council_id:
            is_locked = council.get("manualLock", False)
            if is_locked:
                print(f"  [\U0001F512 LOCKED] {council_id}: manualLock が設定されています。crawlStatus のみ更新します（コアフィールドは保護済み）。")

            prev_status = council.get("crawlStatus", {})
            prev_failures = prev_status.get("consecutiveFailures", 0)

            if scraped_item is None:
                # fetch自体が失敗
                council["crawlStatus"] = {
                    "lastAttempt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "result": "failed",
                    "resultReason": failure_reason or "Fetch failed",
                    "extractionMethod": "none",
                    "materialsCount": 0,
                    "datesCount": 0,
                    "failureReason": failure_reason or "Fetch failed",
                    "consecutiveFailures": prev_failures + 1,
                    "manualLockActive": is_locked
                }
            else:
                result = scraped_item.get("crawlResult", "failed")
                result_reason = scraped_item.get("resultReason", "")
                council["crawlStatus"] = {
                    "lastAttempt": scraped_item.get("scrapedAt", ""),
                    "result": result,
                    "resultReason": result_reason,
                    "extractionMethod": scraped_item.get("extractionMethod", "none"),
                    "materialsCount": scraped_item.get("totalExtractedMaterials", 0),
                    "datesCount": len(scraped_item.get("extractedDates", [])),
                    "failureReason": "" if result != "failed" else (result_reason or "Both LLM and rule extraction returned 0 results"),
                    "consecutiveFailures": 0 if result != "failed" else prev_failures + 1,
                    "manualLockActive": is_locked
                }
            break

def extract_session_numbers(text):
    if not text:
        return set()
    t_norm = normalize_japanese_numbers(str(text))
    nums = set()
    matches = re.findall(r'第\s*(\d+)\s*回', t_norm)
    for m in matches:
        nums.add(int(m))
    matches_dai = re.findall(r'dai\s*(\d+)', t_norm, re.IGNORECASE)
    for m in matches_dai:
        nums.add(int(m))
    matches_slash = re.findall(r'[/_](\d{1,3})(?:[_.]|pdf|giji)', t_norm, re.IGNORECASE)
    for m in matches_slash:
        nums.add(int(m))
    return nums

def extract_years(text):
    if not text:
        return set()
    years = set()
    reiwa = re.findall(r'令和([元\d]+)年', text)
    for r in reiwa:
        val = 1 if r == '元' else int(r)
        years.add(2018 + val)
    heisei = re.findall(r'平成([元\d]+)年', text)
    for h in heisei:
        val = 1 if h == '元' else int(h)
        years.add(1988 + val)
    western = re.findall(r'20\d\d', text)
    for w in western:
        years.add(int(w))
    r_file = re.findall(r'[/_]r0?(\d+)', text, re.IGNORECASE)
    for rf in r_file:
        years.add(2018 + int(rf))
    h_file = re.findall(r'[/_]h0?(\d+)', text, re.IGNORECASE)
    for hf in h_file:
        years.add(1988 + int(hf))
    return years

def deduplicate_data_materials(data):
    """docs/data.json の会議（MEETINGS）に紐づく資料リンクの重複を排除し、正確な回へ一意に再配分する"""
    from collections import defaultdict
    meetings = data.get("meetings", [])
    councils = {c["id"]: c for c in data.get("councils", [])}

    council_meetings = defaultdict(list)
    for m in meetings:
        c_id = m.get("councilId")
        if c_id:
            council_meetings[c_id].append(m)

    removed_cross_dup = 0
    removed_portal = 0

    for c_id, m_list in council_meetings.items():
        c_info = councils.get(c_id, {})
        c_url = (c_info.get("officialUrl") or c_info.get("url", "")).strip()

        # 1. ポータル・公式ページ・一覧ページの資料リンクを除外
        for m in m_list:
            # manualLock: true の会議はそのまま保護（重複排除・移動対象外）
            if m.get("manualLock", False):
                continue
            clean_mats = []
            for mat in m.get("materials", []):
                # manualLock: true の個別資料も保護
                if mat.get("manualLock", False):
                    clean_mats.append(mat)
                    continue
                url = mat.get("url", "").strip()
                name = mat.get("name", "").strip()
                if (c_url and url == c_url) or any(k in name for k in ["公式ポータル", "公式ページ", "公式情報ポータル", "審議会・検討会等一覧", "公式掲載資料・ページ"]):
                    removed_portal += 1
                    continue
                clean_mats.append(mat)
            m["materials"] = clean_mats

        # 2. 会議体内の複数開催回に重複して紐づいている同一資料URLの解消
        url_to_instances = defaultdict(list)
        for m in m_list:
            # manualLock: true の会議はそのまま保護（重複排除・移動対象外）
            if m.get("manualLock", False):
                continue
            for mat in m.get("materials", []):
                url = mat.get("url", "").strip()
                if url and url != "#":
                    # manualLock: true の個別資料も除外
                    if mat.get("manualLock", False):
                        continue
                    url_to_instances[url].append((m, mat))

        for url, insts in url_to_instances.items():
            if len(insts) <= 1:
                continue

            scored_candidates = []
            for m, mat in insts:
                score = 0
                m_name = m.get("name") or m.get("title", "")
                m_id = m.get("id", "")
                mat_name = mat.get("name", "")

                m_sessions = extract_session_numbers(m_name + " " + m_id)
                mat_sessions = extract_session_numbers(mat_name + " " + url)

                common_sessions = m_sessions.intersection(mat_sessions)
                if common_sessions:
                    score += 100 * len(common_sessions)

                m_years = extract_years(m.get("date", "") + " " + m_name)
                mat_years = extract_years(mat_name + " " + url)
                common_years = m_years.intersection(mat_years)
                if common_years:
                    score += 10 * len(common_years)

                if re.search(r'第\d+回', m_name):
                    score += 5

                m_date = m.get("date", "")
                if m_date and not m_date.startswith(INVALID_DATE_PREFIXES):
                    score += 2

                scored_candidates.append((score, m, mat))

            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            best_m = scored_candidates[0][1]

            for score, m, mat in scored_candidates:
                if m["id"] != best_m["id"]:
                    m["materials"] = [x for x in m["materials"] if x.get("url") != url]
                    removed_cross_dup += 1

    if removed_cross_dup > 0 or removed_portal > 0:
        print(f"[重複排除] 会議間重複資料 {removed_cross_dup} 件、ポータルリンク {removed_portal} 件を自動整理しました。")

def run_meeting_crawler(progress_callback=None, stop_event=None, workers=4, recent_years=2, recheck_recent=1, full_check=False, include_closed=False, resume=False):
    """
    審議会・会議体情報取得Engine（Drop 17 高速化・直近アクティブ重点化対応）
    - CR-23: 確定済み過去回の再検査ゼロ化 & 最新1件更新確認（recheck_recent, full_check）
    - CR-24: 直近開催年数フィルタリング（recent_years）& 廃止会議体スキップ（include_closed）
    - CR-26: ホスト単位マルチスレッド並行巡回エンジン（workers）
    - CR-27: 中断耐性と安全チェックポイント保存（SIGINT/停止時即時保存 & resume 再開）
    """
    global CRAWL_TARGETS
    
    log_f, latest_f, log_filepath, latest_filepath = init_crawler_logfile()
    emit_lock = threading.Lock()
    data_lock = threading.Lock()

    def emit(msg, payload=None):
        with emit_lock:
            try:
                print(msg)
            except (OSError, UnicodeEncodeError):
                try:
                    enc = getattr(sys.stdout, 'encoding', None) or 'utf-8'
                    sys.stdout.write(msg.encode(enc, errors='replace').decode(enc) + '\n')
                    sys.stdout.flush()
                except Exception:
                    pass
            now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_line = f"[{now_ts}] {msg}\n"
            if log_f:
                try:
                    log_f.write(log_line)
                    log_f.flush()
                except OSError:
                    pass
            if latest_f:
                try:
                    latest_f.write(log_line)
                    latest_f.flush()
                except OSError:
                    pass
        if progress_callback:
            try:
                progress_callback(msg, payload)
            except Exception as pe:
                try:
                    print(f"[WARN] progress_callback error: {pe}", file=sys.stderr)
                except Exception:
                    pass

    try:
        dynamic_targets = load_councils_from_data_json(
            recent_years=recent_years,
            include_closed=include_closed,
            resume=resume
        )
        if dynamic_targets:
            CRAWL_TARGETS = interleave_by_host_and_ministry(dynamic_targets)
            emit(f"[INFO] docs/data.json から {len(CRAWL_TARGETS)} 件の会議体を動的に読み込み、同一ホスト名・省庁連続アクセス防止のためホスト分散インターリーブ巡回順に並び替えました。")
        else:
            CRAWL_TARGETS = []
            emit(f"[INFO] クロール対象の会議体が見つかりませんでした。")
            return {"success": 0, "partial": 0, "failed": 0, "fetch_error": 0, "new_meetings": 0, "log_file": log_filepath}

        use_llm = load_crawler_config()
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        emit("=" * 65)
        emit(" 政策会議ウォッチ (PM-HUB) クローラー [Drop 17 高速化エンジン]")
        emit("=" * 65)
        emit(f"抽出モード: {'LLM抽出 (Gemini API) + フォールバック' if use_llm else '既存ルール (Heuristic)'}")
        emit(f"並行ワーカー数: {workers} スレッド (ホスト単位レートリミット: 0.5s)")
        emit(f"直近開催年数絞り込み: {recent_years} 年以内 (新規0件含む)")
        emit(f"開催回再検査設定: {'全件再検査 (--full-check)' if full_check else f'最新 {recheck_recent} 件のみ更新確認 (過去回ゼロ化)'}")
        emit(f"取得実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        emit(f"対象会議体数: {len(CRAWL_TARGETS)} 件")
        if log_filepath:
            emit(f"ログファイル出力先: {log_filepath}\n")

        # data.json を読み込み（ステータス更新用）
        data = load_data_json(DATA_JSON_FILE)

        # クロール開始時に lastCrawlTime を即時更新・バックアップ保存
        data["lastCrawlTime"] = now_str
        save_data_json_with_backup(data)

        rules = load_scraping_rules()
        results = []
        stats = {
            "success": 0,
            "partial": 0,
            "failed": 0,
            "fetch_error": 0,
            "new_meetings": 0,
            "stopped": False,
            "processed_councils": 0,
            "newly_added_list": [],
            "log_file": log_filepath
        }

        # 会議体ごとの既登録開催回URL（officialUrl）マップを事前構築（スマート差分探索エンジン用）
        councils_meeting_urls = {}
        for m in data.get("meetings", []):
            cid = m.get("councilId")
            u = m.get("officialUrl")
            if cid and u:
                if cid not in councils_meeting_urls:
                    councils_meeting_urls[cid] = set()
                councils_meeting_urls[cid].add(u)

        total_councils = len(CRAWL_TARGETS)
        processed_counter = 0
        checkpoint_interval = 25  # 25件ごとにチェックポイント安全保存

        def process_target(idx, target):
            nonlocal processed_counter
            if stop_event and stop_event.is_set():
                return None

            pct = int((idx / max(total_councils, 1)) * 90)
            c_name = target.get("name", target.get("id"))
            c_min = target.get("ministry", "")

            emit(f"▶ [{idx}/{total_councils}] [{c_min}] HTTP GET: {c_name} ({target['url']})...", {
                "type": "council_start",
                "council_id": target["id"],
                "council_name": c_name,
                "ministry": c_min,
                "progress": pct,
                "current": idx,
                "total": total_councils,
                "log_file": log_filepath
            })

            try:
                html = fetch_url(target["url"])
                
                if html:
                    c_id = target["id"]
                    target["existing_meeting_urls"] = councils_meeting_urls.get(c_id, set())
                    rule_obj = rules.get(c_id, {
                        "rule_id": "rule-fallback-v1",
                        "rules": {}
                    })

                    item = execute_rule_retrieval(
                        target, html, rule_obj, use_llm=use_llm,
                        recheck_recent=recheck_recent, full_check=full_check
                    )

                    cr = item.get("crawlResult", "failed")
                    status_icon = {"success": "🟢", "partial": "🟡", "failed": "🔴"}.get(cr, "⚪")
                    emit(f"  -> {status_icon} [{cr.upper()}] タイトル: {item['pageTitle']}")
                    if item.get("resultReason"):
                        emit(f"  -> 判定理由: {item['resultReason']}")
                    emit(f"  -> 資料: {item['totalExtractedMaterials']} 件, 日付: {item['extractedDates']}, 抽出方法: {item['extractionMethod']}")

                    with data_lock:
                        stats["processed_councils"] += 1
                        stats[cr] = stats.get(cr, 0) + 1
                        results.append(item)
                        update_crawl_status(data, target["id"], item)
                        new_added = sync_new_meetings_from_crawl(data, target, item)
                        if new_added > 0:
                            stats["new_meetings"] += new_added
                            emit(f"  -> 📦 新規会議 {new_added} 件を data.json の meetings に自動追加・同期しました。", {
                                "type": "new_meeting_added",
                                "council_id": target["id"],
                                "council_name": c_name,
                                "new_added": new_added
                            })

                        processed_counter += 1
                        # チェックポイント保存（25件ごと、または新規会議追加時）
                        if processed_counter % checkpoint_interval == 0 or new_added > 0:
                            data["lastCrawlTime"] = datetime.now().strftime("%Y/%m/%d %H:%M")
                            save_data_json_with_backup(data, create_backup=False)

                    return item
                else:
                    emit(f"  -> 🔴 [FETCH ERROR] ネットワーク取得失敗: {c_name}")
                    with data_lock:
                        stats["processed_councils"] += 1
                        stats["fetch_error"] += 1
                        update_crawl_status(data, target["id"], None, "Network fetch failed")
                        processed_counter += 1
                        if processed_counter % checkpoint_interval == 0:
                            save_data_json_with_backup(data, create_backup=False)
                    return None
            except Exception as council_err:
                emit(f"  -> 🔴 [UNEXPECTED ERROR] 会議体巡回中に予期せぬ例外が発生しました ({c_name}): {council_err}")
                with data_lock:
                    stats["processed_councils"] += 1
                    stats["failed"] += 1
                    try:
                        update_crawl_status(data, target["id"], None, f"Unexpected error: {council_err}")
                    except Exception as status_err:
                        emit(f"  -> [WARN] update_crawl_status 記録失敗: {status_err}")
                    processed_counter += 1
                return None
            finally:
                emit("-" * 65)

        # 巡回実行ディスパッチ（直列 or ホスト単位マルチスレッド並行）
        if workers <= 1:
            for idx, target in enumerate(CRAWL_TARGETS, 1):
                if stop_event and stop_event.is_set():
                    emit(f"\n🛑 [STOP] ユーザーまたはシステムによる停止要求を受信しました。処理を安全に中断します（処理済み: {processed_counter}/{total_councils} 件）。")
                    stats["stopped"] = True
                    break
                process_target(idx, target)
                if idx < total_councils and not (stop_event and stop_event.is_set()):
                    time.sleep(0.35)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {}
                for idx, target in enumerate(CRAWL_TARGETS, 1):
                    if stop_event and stop_event.is_set():
                        stats["stopped"] = True
                        break
                    future = executor.submit(process_target, idx, target)
                    future_map[future] = target

                for future in concurrent.futures.as_completed(future_map):
                    if stop_event and stop_event.is_set():
                        stats["stopped"] = True
                        for f in future_map:
                            f.cancel()
                        break
                    try:
                        future.result()
                    except Exception as e:
                        emit(f"[ERROR] Worker thread unhandled exception: {e}", file=sys.stderr)

        # サマリー表示
        emit(f"\n{'='*65}")
        if stats.get("stopped"):
            emit(f" 🛑 クロール中断サマリー (途中停止・進捗安全保存済み)")
        else:
            emit(f" クロール結果サマリー (完了)")
        emit(f"{'='*65}")
        emit(f"  処理会議体数:          {stats['processed_councils']} / {total_councils} 件")
        emit(f"  🟢 成功 (success):     {stats['success']} 件")
        emit(f"  🟡 部分成功 (partial):    {stats['partial']} 件")
        emit(f"  🔴 失敗 (failed):      {stats['failed']} 件")
        emit(f"  🔴 取得エラー:         {stats['fetch_error']} 件")
        emit(f"  📦 新規追加会議:       {stats['new_meetings']} 件")
        total_unconfirmed = get_unconfirmed_meetings_count(data)
        stats["unconfirmed_meetings"] = total_unconfirmed
        if total_unconfirmed > 0:
            emit(f"  ⚠️  開催日未確定 (2099/01/01): {total_unconfirmed} 件 (要確認・修正推奨)")
        if log_filepath:
            emit(f"  📄 ログファイル:       {log_filepath}")
        emit(f"{'='*65}")

        # 全体データに対して資料リンクの重複排除・正規化を実施
        deduplicate_data_materials(data)

        # data.json にクロールステータスと最終タイムスタンプを安全保存（バックアップ付き）
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        data["lastCrawlTime"] = now_str
        if save_data_json_with_backup(data):
            emit(f"[更新成功] docs/data.json にクロール結果・ステータスと lastCrawlTime ({now_str}) を安全に保存しました（自動バックアップ作成完了）。")
        else:
            emit(f"[WARN] data.json 更新失敗")

        # 新規追加された会議リストを抽出してイベントに添付
        newly_added = [m for m in data.get("meetings", []) if m.get("isNewlyDiscovered")]
        stats["newly_added_list"] = newly_added[:20]

        finish_type = "crawl_stopped" if stats.get("stopped") else "crawl_completed"
        emit(f"処理終了: docs/data.json を更新しました。", {
            "type": finish_type,
            "progress": 100,
            "stats": stats,
            "newly_added_count": len(newly_added),
            "lastCrawlTime": now_str,
            "log_file": log_filepath,
            "stopped": stats.get("stopped", False)
        })
        
        return stats
    finally:
        if log_f:
            try: log_f.close()
            except OSError: pass
        if latest_f:
            try: latest_f.close()
            except OSError: pass

def main():
    import traceback
    
    parser = argparse.ArgumentParser(description="政策会議ウォッチ (PM-HUB) クローラー [Drop 17]")
    parser.add_argument("--workers", type=int, default=4, help="並行ワーカー数（デフォルト: 4。1で直列実行）")
    parser.add_argument("--recent-years", default="2", help="最終開催日の年数絞り込み（デフォルト: 2。0 または all で全件）")
    parser.add_argument("--recheck-recent", type=int, default=1, help="再検査する直近開催回数（デフォルト: 1。0 で完全ゼロ化）")
    parser.add_argument("--full-check", action="store_true", help="すべての登録済み開催回を再検査する")
    parser.add_argument("--include-closed", action="store_true", help="法改正等で廃止された会議体も含めて巡回する")
    parser.add_argument("--resume", action="store_true", help="中断されたクロールを続きから再開する")
    args = parser.parse_args()

    cli_stop_event = threading.Event()
    
    try:
        run_meeting_crawler(
            stop_event=cli_stop_event,
            workers=args.workers,
            recent_years=args.recent_years,
            recheck_recent=args.recheck_recent,
            full_check=args.full_check,
            include_closed=args.include_closed,
            resume=args.resume
        )
    except KeyboardInterrupt:
        print("\n\n[INFO] キーボード割り込み (Ctrl+C) を検知しました。停止シグナルを発行します...")
        cli_stop_event.set()
    except Exception as e:
        print(f"\n\n[FATAL CRASH] クローラー実行中に未処理の例外が発生しました: {e}", file=sys.stderr)
        traceback.print_exc()
        try:
            with open("admin/logs/crawler_crash.log", "a", encoding="utf-8") as cf:
                cf.write(f"[{datetime.now()}] FATAL CRASH: {e}\n")
                traceback.print_exc(file=cf)
        except OSError:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
