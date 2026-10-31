# -*- coding: utf-8 -*-
"""
noise_filters.py:
新規会議体ディスカバリー時のノイズ判定・プレスURL判定・登録済判定 (Drop 116)
"""

import re
import urllib.parse
from typing import Tuple, List, Set, Optional

try:
    from admin.utils import normalize_url_for_matching
except ImportError:
    from utils import normalize_url_for_matching

try:
    from admin.discovery_modules.name_cleaner import clean_council_name, get_core_council_name, normalize_ministry_code
except ImportError:
    from discovery_modules.name_cleaner import clean_council_name, get_core_council_name, normalize_ministry_code

# 非会議体ノイズキーワード・パターン定義 (CR-187)
NOISE_PERSON_ROLES = r"(?:大臣|副大臣|政務官|長官|総理|知事|教授|名誉教授|代表|委員)"
NOISE_ACTION_PATTERNS = [
    re.compile(rf"{NOISE_PERSON_ROLES}が"),
    re.compile(rf"{NOISE_PERSON_ROLES}と.*(?:会談|面会|意見交換|表敬)"),
    re.compile(r"大臣発言"),
    re.compile(r"(?:意見交換|研究課題発表)を(?:実施|行い)"),
    re.compile(r"日本人初】"),
]

NOISE_INTERNATIONAL_AND_ORGS = [
    # 国際機関・国際会議・条約会合
    "世銀", "IMF", "FATF", "金融活動作業部会", "国際通貨金融委員会", "WTO", "CITES", "ワシントン条約",
    "生物多様性条約", "気候変動枠組条約", "締約国会議", "国連総会", "国連犯罪防止", "国連国際商取引",
    "国際かんがい排水", "日米合同委員会", "日米政府の戦略的投資", "日米サイバー", "日米加", "日・ベトナム",
    "日ロ漁業", "北太平洋漁業", "アジア・アフリカ法律", "アジア矯正", "海運先進国", "ウクライナ汚職",
    "世界保護司", "欧州委員会", "大韓民国", "フィンランド", "豪州政府", "プレCOP",
    # 国会・政党・一般法人
    "参議院", "衆議院", "自由民主党", "一般社団法人", "公益社団法人", "公益財団法人", "独立行政法人", "株式会社"
]
NOISE_INTERNATIONAL_REGEX = re.compile(
    r"(?:COP\d+|" + "|".join(re.escape(k) for k in NOISE_INTERNATIONAL_AND_ORGS) + r")"
)

NOISE_PORTAL_EXACT = {
    "政策・審議会", "省議・審議会", "審議会・委員会", "審議会等", "政策・審議会等", "省議・審議会等",
    "政策・審議会等トップへ", "各種本部・会議等の活動情報", "本審議会 トップページ", "公害等調整委員会",
    "中央環境審議会", "法制審議会会議", "審議会情報", "度"
}



PRESS_RELEASE_EXCLUSIVE_PATTERNS = [
    r'/report/press/',                # MLIT 報道発表
    r'/j/press/',                    # MOD, MAFF, Rinya, JFA 等 報道発表
    r'/menu_news/s-news/',           # MIC 報道資料
    r'/press/press_',                # MOE 報道発表
    r'/press/20\d{2}/',              # METI / その他 ニュースリリース
    r'/news/20\d{2}/',               # 各省庁 ニュースリリース
    r'/b_menu/houdou/',              # MEXT 報道発表
    r'/houdou/20\d{2}/',             # 報道発表アーカイブ
    r'/hisho/kouhou/',               # MOJ 記者会見・報道
    r'/kaiken/',                     # 記者会見
    r'/pressrelease/',               # プレスリリース
]
PRESS_RELEASE_EXCLUSIVE_REGEX = re.compile('|'.join(PRESS_RELEASE_EXCLUSIVE_PATTERNS), re.IGNORECASE)



def is_single_press_or_notice_url(url: str) -> bool:
    """単発報道発表・記者会見専用URLパターンを判定 (Drop 107)"""
    if not url:
        return False
    return bool(PRESS_RELEASE_EXCLUSIVE_REGEX.search(url))


def is_non_council_noise(name: str, raw_text: str = "", url: str = "") -> bool:
    """
    非会議体ノイズ（大臣動静・国際会議・条約会合・国会・一般法人・ナビ要素・PDF直リンク）を判定 (CR-187)
    """
    text_check = f"{name} {raw_text}".strip()
    clean_name = clean_council_name(name)

    # 1. 最小文字数ガード (4文字未満は除外, 例: '度')
    if len(clean_name) < 4:
        return True

    # 2. 完全一致ポータル・ナビ名称
    if clean_name in NOISE_PORTAL_EXACT or name.strip() in NOISE_PORTAL_EXACT:
        return True

    # 3. ナビゲーション・個別ヒアリング末尾・パターン
    if re.search(r"(?:トップページ|トップへ|活動情報|主査ヒアリング|公聴会|意見募集)$", clean_name):
        return True
    if re.search(r"^(?:政策・審議会|省議・審議会|審議会・委員会|審議会等)", clean_name):
        return True

    # 4. 人物・大臣動静・イベントアクション判定
    for pat in NOISE_ACTION_PATTERNS:
        if pat.search(text_check):
            return True

    # 5. 国際会議・条約会合・国会・一般法人判定
    if NOISE_INTERNATIONAL_REGEX.search(text_check):
        return True

    # 6. PDF/ドキュメント直リンクURLの除外
    if url and re.search(r"\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|zip)$", url, re.I):
        return True

    return False


def normalize_url(url):
    """URLの末尾スラッシュやフラグメント(#)を除去して正規化"""
    if not url:
        return ""
    p = urllib.parse.urlparse(url)
    clean_path = p.path.rstrip("/")
    return f"{p.scheme}://{p.netloc}{clean_path}"


def get_url_clean_key(url):
    """http/https や末尾スラッシュ、クエリ、フラグメントを除去したURLの比較キーを生成"""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        return f"{netloc}{path}"
    except Exception:
        return url.strip().lower()


def get_max_seq(councils):
    """既存COUNCILSから最大のID連番を取得する (例: cao-184 -> 184)"""
    max_num = 183
    for c in councils:
        cid = c.get("id", "")
        num_m = re.search(r"-(\d+)$", cid)
        if num_m:
            try:
                n = int(num_m.group(1))
                if n > max_num:
                    max_num = n
            except ValueError:
                pass
    return max_num


def is_already_registered_or_rejected(
    cand_name: str, cand_url: str, min_code: str,
    existing_names: set, existing_urls: set, existing_core_names: set, existing_councils_by_min: dict,
    rejected_names: set, rejected_urls: set, rejected_core_names: set, rejected_clean_keys: set
) -> bool:
    """
    完全一致に加え、正規化コア名称および同一省庁内の部会サフィックス一致で既存・却下判定 (CR-188, Drop 75)
    """
    clean_name = clean_council_name(cand_name)
    core_name = get_core_council_name(cand_name)
    norm_url = normalize_url(cand_url)
    clean_key = get_url_clean_key(cand_url)

    # 1. URLによる突合
    if norm_url in existing_urls or (clean_key and clean_key in rejected_clean_keys):
        return True
    if norm_url in rejected_urls:
        return True

    # 2. 完全一致名称による突合
    if cand_name in existing_names or clean_name in existing_names:
        return True
    if cand_name in rejected_names or clean_name in rejected_names:
        return True

    # 3. 正規化コア名称（Core Name）による突合
    if core_name:
        if core_name in existing_core_names:
            return True
        if core_name in rejected_core_names:
            return True

    # 4. 同一省庁内の「親審議会名＋部会・分科会・委員会名」サフィックス一致判定 (Check 14準拠)
    # 例: cand_name = 'イノベーション小委員会' vs '研究開発・イノベーション小委員会'
    sub_keywords = ('部会', '分科会', '小委員会', '委員会', 'ワーキンググループ', '検討会', '研究会', '審査会', '専門家会合', 'タスクフォース')
    if min_code:
        n1 = re.sub(r'\s+', '', cand_name)
        n1_clean = re.sub(r'\s+', '', clean_name)
        min_existing = existing_councils_by_min.get(min_code.upper(), [])
        for c in min_existing:
            ex_name = c.get("name", "")
            n2 = re.sub(r'\s+', '', ex_name)
            if n1 == n2 or n1_clean == n2:
                return True
            for cand_cand in (n1, n1_clean):
                if len(cand_cand) >= 4 and len(n2) >= 4:
                    if any(k in cand_cand for k in sub_keywords) and any(k in n2 for k in sub_keywords):
                        if (n2.endswith(cand_cand) and not n2.startswith(cand_cand)) or (cand_cand.endswith(n2) and not cand_cand.startswith(n2)):
                            return True

    return False

