# -*- coding: utf-8 -*-
"""
name_cleaner.py:
会議体名称の正規化・コア名称抽出・カテゴリ推定・ニュースタイトル抽出 (Drop 116)
"""

import re
import unicodedata

try:
    from admin.utils import normalize_text
except ImportError:
    from utils import normalize_text

MINISTRY_CODE_NORMALIZATION = {
    "ENV": "MOE",
}

def normalize_ministry_code(code: str) -> str:
    if not code:
        return ""
    c = code.upper().strip()
    return MINISTRY_CODE_NORMALIZATION.get(c, c)


def infer_council_category(name_or_text, defined_categories=None):
    """
    会議体名称またはリンクテキストから、定義済み categories に合致するカテゴリIDを判定。
    戻り値: (category_id, is_default_fallback)
    """
    text = name_or_text or ""
    # 優先度の高い特定キーワードから順に判定
    if "専門調査会" in text or "専門委員会" in text or "専門審査会" in text:
        cat = "EXPERT_COMMITTEE"
    elif "特別委員会" in text:
        cat = "SPECIAL_COMMITTEE"
    elif "タスクフォース" in text or "TF" in text:
        cat = "TASKFORCE"
    elif "分科会" in text:
        cat = "SUBCOMMITTEE"
    elif "部会" in text:
        cat = "SECTION"
    elif "ワーキンググループ" in text or "ワーキング・グループ" in text or "作業部会" in text or "作業班" in text or "WG" in text:
        cat = "WORKING_GROUP"
    elif "有識者会議" in text:
        cat = "PANEL"
    elif "懇談会" in text:
        cat = "ROUNDTABLE"
    elif "スタディグループ" in text or "スタディ・グループ" in text or "SG" in text or "検討会" in text or "研究会" in text or "検討会議" in text or "協議会" in text:
        cat = "STUDY"
    elif "関係閣僚会議" in text or "連絡会議" in text:
        cat = "LIAISON"
    elif "推進本部" in text or "本部" in text or "推進会議" in text:
        cat = "HQ"
    elif "諮問会議" in text:
        cat = "ADVISORY"
    elif "審査会" in text or "委員会" in text:
        cat = "COMMITTEE"
    elif "審議会" in text or "会合" in text:
        cat = "COUNCIL"
    else:
        cat = "COUNCIL"
        return (cat, True)
    
    if defined_categories and cat not in defined_categories:
        return ("COUNCIL", True)
    return (cat, False)


def clean_council_name(name):
    """
    「第X回」や日付プレフィックス、末尾の「配布資料」「議事概要」などを除去して
    親会議体名（1つの会議体レコード）を抽出する。(CR-186)
    """
    if not name:
        return ""
    try:
        from crawler import normalize_text
    except ImportError:
        from admin.crawler import normalize_text
    n = normalize_text(name).strip()
    
    # 0. 省庁カテゴリ・ラベルプレフィックスの除去 (CR-186)
    n = re.sub(r'^(?:審議会等|報道発表|会議等|その他|国際政策|財総研|お知らせ|新着情報|トピックス|プレスリリース)[\s　:：]+', '', n)
    
    # 1. 日付・更新ラベル・年度・期数プレフィックスの除去 (CR-186)
    n = re.sub(r'^(?:〈[^〉]+〉|＜[^＞]+＞|【[^】]+】|\[[^\]]+\])(?:\s*[(（]更新[)）])?\s*', '', n)
    n = re.sub(r'^(?:令和|平成)\s*[0-9０-９一-九元]+\s*年\s*[0-9０-９一-九]+\s*月\s*[0-9０-９一-九]+\s*日(?:開催)?\s*', '', n)
    n = re.sub(r'^(?:令和|平成)\s*[0-9０-９一-九元]+\s*年度\s*', '', n)
    n = re.sub(r'^\b\d{4}\s*年度\s*', '', n)
    n = re.sub(r'^第\s*[0-9０-９一-九]+\s*期\s*', '', n)
    n = re.sub(r'^(?:第[0-9０-９一-九]+回|第[0-9０-９一-九]+回\s*)\s*', '', n)
    
    # 2. 括弧付き回数・開催案内の除去
    n = re.sub(r'[（(]第[0-9０-９一-九]+回.*?[）)]', '', n)
    n = re.sub(r'【\d+月\d+日開催】', '', n)
    n = re.sub(r'【\d{4}/\d{1,2}/\d{1,2}開催】', '', n)
    
    # 3. 中間・末尾の回数・議事概要の除去
    n = re.sub(r'\s*第[0-9０-９一-九]+回.*', '', n)
    n = re.sub(r'\s*(?:の開催について|開催について|の開催案内|開催案内).*', '', n)
    n = re.sub(r'\s*(?:報告書について|報告書).*', '', n)
    n = re.sub(r'\s*(?:配布資料|配付資料|取りまとめ.*|について|開催概要|議事要旨|議事録|議事次第|議事概要)$', '', n)

    # 4. 前後の孤立括弧・空白の補正
    # ※末尾の閉じていない括弧（例: "恩給審査会（平成21年度廃止前"）も除去できるように配慮
    n = re.sub(r'^[「『【\[\(（\s]+', '', n)
    n = re.sub(r'[」』】\]\)）\s]+$', '', n)
    
    return n.strip()


def get_core_council_name(name: str) -> str:
    """
    表記揺れ（空白、全角半角、年度、期数、「について」、括弧補足）を除去した
    正規化コア名称を生成する (CR-188)。
    """
    if not name:
        return ""
    try:
        from crawler import normalize_text
    except ImportError:
        from admin.crawler import normalize_text
    c = normalize_text(name).strip()
    # 括弧内の補足を除去 (例: （令和8年～）, (平成21年度廃止前), （京都コングレス）)
    c = re.sub(r'[（(][^）)]*[）)]?', '', c)
    c = clean_council_name(c)
    # 先頭の年度・期数
    c = re.sub(r'^(?:令和|平成|\d{4})\S*年度?\s*', '', c)
    c = re.sub(r'^第\s*\d+\s*期\s*', '', c)
    # 末尾の「について」
    c = re.sub(r'について$', '', c)
    # 空白、中黒、記号を除去
    c = re.sub(r'[\s　・~～―－\-_:：/／()（）]', '', c)
    return c.strip().lower()


def extract_council_name_from_news_title(title: str, keywords: list) -> str:
    """ニュース記事タイトルから会議体名称を抽出・クレンジング (CR-186)"""
    try:
        from crawler import normalize_text
    except ImportError:
        from admin.crawler import normalize_text
    t = normalize_text(title).strip()

    # 0. 省庁カテゴリラベルの除去 (CR-186)
    t = re.sub(r'^(?:審議会等|報道発表|会議等|その他|国際政策|財総研|お知らせ|新着情報|トピックス|プレスリリース)[\s　:：]+', '', t)

    # 0.5 サブタイトル・キャッチコピー区切りの分割 (CR-186)
    # 例: 「上下水道政策の基本的な方向性を議論します~上下水道政策の基本的なあり方検討会」 -> 後半を優先
    sub_delim_m = re.search(r'[~～―－](?=[^~～―－]+(?:' + '|'.join(re.escape(k) for k in keywords) + r'))', t)
    if sub_delim_m:
        t = t[sub_delim_m.end():].strip()

    # 1. 鉤括弧「」『』【】内の会議体名を優先抽出
    brackets = re.findall(r'[「『【]([^」』】]+)[」』】]', t)
    for b in brackets:
        b_clean = clean_council_name(b)
        if any(kw in b_clean for kw in keywords) and len(b_clean) >= 4:
            return b_clean

    # 2. 接尾辞や開催案内語句の除去
    t_clean = clean_council_name(t)

    # 3. 会議体キーワードを含む部分の切り出し (末尾までの探索)
    for kw in sorted(keywords, key=len, reverse=True):
        pos = t_clean.find(kw)
        if pos != -1:
            cand = t_clean[:pos + len(kw)].strip()
            cand = clean_council_name(cand)
            if len(cand) >= 4 and any(k in cand for k in keywords):
                return cand

    return ""

