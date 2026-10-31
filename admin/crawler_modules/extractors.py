# -*- coding: utf-8 -*-
"""
extractors.py:
クローラーのテキスト・日付・タイトル・資料名抽出ロジック (Drop 115)
- 会議名クレンジング (clean_meeting_title)
- 資料文脈・ラベル復元 (recover_material_context)
- テキスト議事録パース (parse_txt_minutes)
- ページタイトル抽出 (extract_page_title)
- URL内日付抽出 (_extract_date_from_url)
- 開催回日付解決 (_resolve_meeting_date)
"""

import os
import re
import urllib.parse
from datetime import datetime

try:
    from admin.utils import (
        normalize_text,
        parse_japanese_date,
        normalize_japanese_numbers,
    )
except ImportError:
    from utils import (
        normalize_text,
        parse_japanese_date,
        normalize_japanese_numbers,
    )

try:
    from admin.crawler_modules.filters import (
        is_generic_title_text,
        is_generic_material_name,
        GOV_SUFFIX_REGEX,
    )
except ImportError:
    from crawler_modules.filters import (
        is_generic_title_text,
        is_generic_material_name,
        GOV_SUFFIX_REGEX,
    )

def recover_material_context(a_tag, initial_name="", rule=None):
    """
    リンクテキストが「PDF」「資料」等のジェネリック名である場合に、
    先行テキスト、親セル、同一テーブル行ヘッダー等から本来の資料名をスマート復元する（CR-110）。
    """
    cand_name = initial_name

    # 1. 直前の兄弟テキスト / 要素から資料番号・先行テキストを取得
    prefix_parts = []
    for prev in a_tag.previous_siblings:
        if prev.name == 'a':
            break
        if isinstance(prev, str):
            prefix_parts.append(prev)
        else:
            prefix_parts.append(prev.get_text(' ', strip=True))
    prefix = ' '.join(reversed(prefix_parts)).strip()
    prefix = re.sub(r'[\（\(]PDF[／/形式\:\s\d\.\,KBMB]+\s*[\）\)]', '', prefix, flags=re.IGNORECASE).strip()
    prefix = re.sub(r'［PDF形式：\d+.*?］', '', prefix).strip()
    prefix = normalize_text(prefix)
    prefix = re.sub(r'^[\[\(\（\［【\s・:：]+|[\]\)\）\］】\s・:：]+$', '', prefix).strip()

    # 2. 同一テーブル行 (tr) の先行セル（th / td）の見出しテキスト
    tr = a_tag.find_parent('tr')
    tr_prefix = ''
    if tr:
        cells = tr.find_all(['td', 'th'])
        parent_cell = a_tag.find_parent(['td', 'th'])
        if parent_cell and parent_cell in cells:
            idx = cells.index(parent_cell)
            if idx > 0:
                header_texts = [c.get_text(' ', strip=True) for c in cells[:idx]]
                tr_prefix = ' '.join(t for t in header_texts if t and t not in ('PDF', '資料')).strip()
                tr_prefix = normalize_text(tr_prefix)
                tr_prefix = re.sub(r'[\（\(]PDF[／/形式\:\s\d\.\,KBMB]+\s*[\）\)]', '', tr_prefix, flags=re.IGNORECASE).strip()
                tr_prefix = re.sub(r'［PDF形式：\d+.*?］', '', tr_prefix).strip()
                # 単なる回次や日付（またはその組み合わせ）のみの場合は資料名ではないため除外
                if re.match(r'^(?:第[\d〇一二三四五六七八九十百]+回)?[\s\u3000]*(?:(?:令和|平成|昭和|\d{4}年)[\s\d年月日時分秒/・\-–—―\(\)（）]*)+$', tr_prefix):
                    tr_prefix = ''
                elif re.match(r'^第[\d〇一二三四五六七八九十百]+回$', tr_prefix):
                    tr_prefix = ''

    # 3. 親ブロック要素 (td, li, p, dd) のテキスト
    parent_block = a_tag.find_parent(['td', 'th', 'li', 'p', 'dd', 'dt'])
    parent_text = ''
    if parent_block:
        p_txt = parent_block.get_text(' ', strip=True)
        p_txt = re.sub(r'[\（\(]PDF[／/形式\:\s\d\.\,KBMB]+\s*[\）\)]', '', p_txt, flags=re.IGNORECASE).strip()
        p_txt = re.sub(r'［PDF形式：\d+.*?］', '', p_txt).strip()
        p_txt = normalize_text(p_txt)
        # 他のリンクテキストが大量に混ざっていないかチェック
        other_links = parent_block.find_all('a')
        if len(other_links) <= 2:
            p_txt = re.sub(r'\bPDF\b', '', p_txt, flags=re.IGNORECASE).strip()
            p_txt = re.sub(r'^[\[\(\（\［【\s・:：]+|[\]\)\）\］】\s・:：]+$', '', p_txt).strip()
            if len(p_txt) >= 2 and not is_generic_material_name(p_txt):
                parent_text = p_txt

    # 4. コンテキストの合成と選定
    recovered = ''
    if tr_prefix and prefix:
        recovered = f"{tr_prefix} {prefix}"
    elif prefix and len(prefix) >= 2 and not is_generic_material_name(prefix):
        recovered = prefix
    elif tr_prefix and len(tr_prefix) >= 2 and not is_generic_material_name(tr_prefix):
        recovered = tr_prefix
    elif parent_text:
        recovered = parent_text

    # 前後のノイズ記号のクリーンアップ（閉じ括弧は正当なテキスト末尾でありうるため除外）
    if recovered:
        recovered = re.sub(r'^[\[\(\（\［【\s・:：\-–—―\.]+|[\]\［】\s・:：\-–—―\.]+$', '', recovered).strip()
        # 末尾の未閉じ開き括弧の除去（例: "資料名(" -> "資料名"）
        if (recovered.endswith('(') or recovered.endswith('（')) and not (recovered.startswith('(') or recovered.startswith('（')):
            recovered = recovered[:-1].strip()
        if len(recovered) >= 2 and not is_generic_material_name(recovered):
            return recovered

    # 復元できずジェネリックなままで、URL/ファイル名に gijiroku が含まれる場合は「議事録」へフォールバック
    href = a_tag.get('href', '')
    parsed_path = urllib.parse.urlparse(href).path
    fn = os.path.basename(parsed_path)
    if 'gijiroku' in fn.lower():
        return "議事録"

    # Drop 99: URLのディレクトリ名からコンテキストを補完（scraping_rules.material_dir_prefix_map 駆動）
    dir_name = os.path.basename(os.path.dirname(parsed_path)).lower()
    prefix_map = {}
    if isinstance(rule, dict) and isinstance(rule.get("material_dir_prefix_map"), dict):
        prefix_map = rule["material_dir_prefix_map"]
    elif _MATERIAL_DIR_PREFIX_MAP:
        prefix_map = _MATERIAL_DIR_PREFIX_MAP
    for dir_key, label_prefix in prefix_map.items():
        if dir_key.lower() in dir_name:
            return f"{label_prefix} {cand_name}"

    return cand_name

def parse_txt_minutes(text, url=""):
    """
    議事録・議事次第等のテキストファイル（.txt）から開催日、回次、タイトル、および配付資料レコードを抽出する（CR-114）。
    Returns: dict with 'date', 'round_number', 'title', 'materials'
    """
    if not text:
        return {"date": None, "round_number": None, "title": None, "materials": []}

    lines = [normalize_text(line.strip()) for line in text.splitlines() if line.strip()]
    header_text = ' '.join(lines[:15])

    # 1. 開催日抽出
    date = None
    # パターンA: 冒頭の "07/04/26" 形式 (YY/MM/DD)
    m_short_date = re.search(r'\b(\d{2})/(\d{1,2})/(\d{1,2})\b', header_text)
    if m_short_date:
        yy, mm, dd = m_short_date.groups()
        full_year = 2000 + int(yy) if int(yy) < 50 else 1900 + int(yy)
        date = f"{full_year:04d}/{int(mm):02d}/{int(dd):02d}"

    # パターンB: 和暦 "平成19年4月26日", "令和3年5月10日"
    if not date:
        m_era = re.search(r'(平成|令和)(\d+|元)年\s*(\d{1,2})月\s*(\d{1,2})日', header_text)
        if m_era:
            era, y, mm, dd = m_era.groups()
            y_val = 1 if y == '元' else int(y)
            base_y = 2018 if era == '令和' else 1988
            full_year = base_y + y_val
            date = f"{full_year:04d}/{int(mm):02d}/{int(dd):02d}"

    # パターンC: 西暦 "2007年4月26日"
    if not date:
        m_seireki = re.search(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日', header_text)
        if m_seireki:
            yyyy, mm, dd = m_seireki.groups()
            date = f"{int(yyyy):04d}/{int(mm):02d}/{int(dd):02d}"

    # 2. 回次およびタイトル抽出
    round_number = None
    title = None
    doc_kind = "議事録"
    if url and any(k in url.lower() for k in ['sidai', 'shidai', 'gijisidai', 'gijishidai']):
        doc_kind = "議事次第"

    for line in lines[:8]:
        # 回次抽出
        m_round = re.search(r'第\s*([0-9０-９一二三四五六七八九十百]+)\s*回', line)
        if m_round:
            r_raw = m_round.group(1)
            r_norm = normalize_japanese_numbers(r_raw)
            if r_norm.isdigit():
                round_number = int(r_norm)
            
            clean_l = re.sub(r'^\d{2}/\d{2}/\d{2}\s*', '', line).strip()
            clean_l = re.sub(r'(?:議事録|議事要旨|議事次第)$', '', clean_l).strip()
            clean_l = re.sub(r'^[（\(]+|[）\)]+$', '', clean_l).strip()
            if clean_l and len(clean_l) >= 4:
                title = clean_l
                break

    # 回次が見つかったがタイトルが取れなかった場合
    if round_number and not title and lines:
        first_line = re.sub(r'^\d{2}/\d{2}/\d{2}\s*', '', lines[0]).strip()
        first_line = re.sub(r'(?:議事録|議事要旨|議事次第)$', '', first_line).strip()
        if len(first_line) >= 4:
            title = first_line

    materials = []
    if url:
        materials.append({
            "name": doc_kind,
            "url": url,
            "type": "TXT",
            "manualLock": True
        })

    return {
        "date": date,
        "round_number": round_number,
        "title": title,
        "materials": materials
    }

def clean_meeting_title(title):
    """
    会議タイトルからHTMLタグ、末尾の省庁サフィックス、配付資料一覧、共通ノイズ等を除去・正規化する（CR-28 / CR-46 / CR-101）。
    """
    if not title:
        return ""
    # HTMLタグ（<br>, <span>等）を除去
    t = re.sub(r'<[^>]+>', ' ', title)
    t = normalize_text(t)
    # 1. 末尾の省庁・行政組織サフィックスの除去
    t = GOV_SUFFIX_REGEX.sub('', t).strip()
    # 2. 末尾の資料・配付資料・配付資料一覧等の除去
    t = re.sub(r'[\s\u3000]*(?:配付|配布|会議)?資料(?:一覧)?$', '', t).strip()
    # 3. 連続する空白を1つに正規化
    t = re.sub(r'[\s\u3000]+', ' ', t).strip()
    return t

DEFAULT_DATE_REGEX = r'(?:令和|平成)(?:\d+|元)年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+'

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
                    if cand and not is_generic_title_text(cand):
                        title = cand

        # title_selector で取れなかった場合、またはジェネリックタイトルの場合
        if not title or is_generic_title_text(title):
            for tag_name in ['h1', 'h2', 'h3']:
                found_tags = soup.find_all(tag_name)
                for ft in found_tags:
                    t_cand = ft.get_text(" ", strip=True)
                    t_cand = clean_meeting_title(t_cand)
                    if not t_cand or len(t_cand) <= 3:
                        continue
                    # 事務的見出し（例: １ 日時、２ 場所、３ 議題、１．日時 等）をスキップ
                    if re.match(r'^[0-9０-９一二三四五六七八九十]+[．.、\s\u3000]*(?:開催日時|日時|開催日|場所|議題|出席者|出席者名簿|傍聴|募集要項)', t_cand):
                        continue
                    if is_generic_title_text(t_cand):
                        continue
                    title = t_cand
                    break
                if title:
                    break

        # それでもなければ <title> タグ
        if not title and soup.title and soup.title.string:
            cand_title = soup.title.string.strip()
            cand_title = clean_meeting_title(cand_title)
            if cand_title and not is_generic_title_text(cand_title):
                title = cand_title

        if title:
            title = clean_meeting_title(title)
            if is_generic_title_text(title):
                title = ""

        return title if title else fallback_url
    except Exception:
        # パース失敗やネットワーク異常時はフォールバックURLを安全に返却
        return fallback_url

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
