# -*- coding: utf-8 -*-
"""
filters.py:
クローラーの各種フィルタリング判定 (Drop 115)
- SNS・PR URL判定 (is_sns_pr_url)
- 非PDFアンカー判定 (is_non_pdf_anchor_url)
- 汎用タイトル判定 (is_generic_title_text)
- 汎用資料名判定 (is_generic_material_name)
- 汎用インデックスURL判定 (is_generic_index_url)
- 開催案内ページ判定 (is_preliminary_notice_page)
- ナビゲーションURL判定 (_is_parent_or_nav_url)
- 静的アセット判定 (is_static_asset_url)
"""

import re
import urllib.parse
try:
    from admin.utils import normalize_ministry_code
except ImportError:
    from utils import normalize_ministry_code


GENERIC_TITLE_KEYWORDS = frozenset({
    '会議資料詳細', '資料詳細', '会議詳細', 'トップページ', '目次', 'ホーム', '配付資料一覧',
    '政策について', '国立国会図書館インターネット資料収集保存事業（WARP）',
    '国立国会図書館インターネット資料収集保存事業', '議事次第', '配付資料', '配布資料',
    '議題', '資料', '議事', '日時', 'メンバー', '会議資料一覧', '審議会・検討会・研究会等',
    '審議会、検討会、研究会等',
    'サイトマップ', '開催案内', '開催について', '１開催日時', '１．日', '●日時', 'お知らせ',
    '新着情報', '１．日時', '１　開催日時', '議事要旨等', 'Interim Report', '共同主催国際会議',
    '議事次第・資料一覧', '配布資料一覧', '配付資料一覧', '覚書等', '覚書',
    '開催日', '開催日時', '開催期間', '議事次第等', '資料一覧', '配付資料等', '配布資料等',
    '会議結果', '開催案内等', '配付資料について', '配布資料について', '会議概要',
    '報道・広報', '広報', '関連リンク', 'リンク集', '災害への対応', '施策紹介', '最近の話題',
    'オンライン利用率引上げ', '調査の概要', '御意見・御感想',
    'ご意見・ご感想', '大臣会見記録', '会見記録', '報道官会見記録', '広報印刷物',
    '個人情報保護について', '開催予定表',
    '検査方針・研修実績等', '対象者別メニュー', '提供可能となる食品の情報',
    '新型コロナウイルス感染症に関する情報一覧', '感染症に関する情報一覧',
    '審議会開催予定', '大臣等記者会見', '記者会見', '政策情報（会議・統計等）', '会議・委員会等',
    '調査の実施について', '問い合わせ先', '情報配信サービス', 'イベント概要',
    'セミナーのご案内', 'セミナー案内', '公募情報', '意見募集', 'パブリックコメント',
    '１ 日時', '１　日時', '日時', '場所', '議題', '出席者', '出席者名簿', '１ 場所', '１　場所', '２ 場所', '２　場所',
    '３ 議題', '３　議題', '傍聴', '傍聴案内', '傍聴について', '傍聴申込', '傍聴申し込み',
    '議事録・資料等'
})

GENERIC_EXACT_ONLY_KEYWORDS = frozenset({
    '開催について', '開催案内', '開催告知', '開催案内等', '開催日', '開催日時', '開催期間',
    '議事', '資料', '議題', '日時', '場所', '傍聴', '傍聴案内', '傍聴について', 'メンバー',
    '配付資料について', '配布資料について', '議事要旨等', '議事次第等', '会議概要', '会議結果',
    '１開催日時', '１．日', '●日時', '１．日時', '１　開催日時', '１ 日時', '１　日時',
    '１ 場所', '１　場所', '２ 場所', '２　場所', '３ 議題', '３　議題', '出席者', '出席者名簿'
})

def is_generic_title_text(text, ministry=None, rule=None):
    """
    会議名として不適切な汎用見出し（ジェネリックタイトル）であるかを判定。
    Drop 96: 汎用キーワード判定に加え、省庁別除外設定（admin_configs）および会議体ルール（scraping_rules）を動的照合。
    """
    if not text:
        return True
    t = text.strip()
    if t in GENERIC_EXACT_ONLY_KEYWORDS or t in GENERIC_TITLE_KEYWORDS:
        return True
    if re.match(r'^\d+\s*[\.．]\s*(概要|趣旨|経緯|意見公募|背景|諮問事項|料率検証)', t):
        return True
    if 'ご意見等連絡先' in t:
        return True
    for kw in GENERIC_TITLE_KEYWORDS:
        if kw in GENERIC_EXACT_ONLY_KEYWORDS:
            continue
        if len(kw) >= 3 and kw in t:
            return True

    # Drop 96: 省庁別除外タイトルキーワードの動的照合
    if ministry:
        m_code = normalize_ministry_code(ministry)
        m_cfg = _MINISTRY_EXCLUSIONS_MAP.get(m_code, {})
        for kw in m_cfg.get("exclude_title_keywords", ()):
            if kw in t or kw.lower() in t.lower():
                return True

    # Drop 96: 会議体別除外タイトルキーワードの動的照合
    if rule and isinstance(rule, dict):
        for kw in rule.get("exclude_subpage_title_keywords", ()):
            if kw in t or kw.lower() in t.lower():
                return True

    return False

COMMON_NAV_KEYWORDS = frozenset({
    '報道・広報', '広報', '関連リンク', 'リンク集', '災害への対応', '施策紹介', '最近の話題',
    'オンライン利用率引上げ', '調査の依頼方法', '調査の概要',
    '御意見・御感想', 'ご意見・ご感想', '大臣会見記録', '会見記録', '報道官会見記録', '広報印刷物',
    '個人情報保護について',
    '開催予定表', '検査方針・研修実績等', '対象者別メニュー', '提供可能となる食品の情報',
    '新型コロナウイルス感染症に関する情報一覧', '感染症に関する情報一覧',
    '審議会開催予定', '大臣等記者会見', '記者会見', '政策情報（会議・統計等）', '会議・委員会等',
    'パンフレット', 'リーフレット', 'メールマガジン', 'メルマガ', 'ポスター',
    '調査の実施について', '問い合わせ先', '情報配信サービス', 'イベント概要',
    'セミナーのご案内', 'セミナー案内',
    '議事録・資料等'
})

GENERIC_MATERIAL_NAMES = frozenset({
    'PDF', 'pdf', '資料', 'ダウンロード', 'リンク', 'こちら', '配付資料', '配布資料',
    '別紙', '別添', '添付', '添付資料', '一覧', '詳細'
})

def is_generic_material_name(name):
    """資料名が「PDF」「資料」等のジェネリック単体文字列であるかを判定"""
    if not name:
        return True
    n = name.strip()
    if n in GENERIC_MATERIAL_NAMES:
        return True
    # 括弧のみ、または括弧内がジェネリック語句
    clean_paren = re.sub(r'^[\[\(\（\［【\s]+|[\]\)\）\］】\s]+$', '', n).strip()
    if not clean_paren or clean_paren in GENERIC_MATERIAL_NAMES:
        return True
    # ［PDF形式：120KB］等の形式・容量のみ
    if re.match(r'^PDF(?:形式)?[\:：\s\u3000／/\d\.\,KBMBkbmb]+$', clean_paren, flags=re.IGNORECASE):
        return True
    return False

GOV_SUFFIX_REGEX = re.compile(
    r'[\s\u3000]*[｜\|：:\-–—―]\s*(?:厚生労働省|内閣府|内閣官房|財務省|国税庁|金融庁|法務省|出入国在留管理庁|公安審査委員会|公安調査庁|外務省|文部科学省|文化庁|スポーツ庁|農林水産省|水産庁|林野庁|経済産業省|資源エネルギー庁|特許庁|中小企業庁|国土交通省|観光庁|気象庁|海上保安庁|環境省|原子力規制委員会|防衛省|防衛装備庁|デジタル庁|こども家庭庁|食品安全委員会|消費者庁|警察庁|消防庁|首相官邸.*|WARP.*)(?:ホームページ|HP|公式ホームページ)?$'
)

_SNS_PR_DOMAINS = ('twitter.com', 'x.com', 'facebook.com', 'instagram.com', 'line.me')

def is_sns_pr_url(url):
    """
    SNS広報リンク（公式Twitter/X, Facebook等）および動画チャンネルトップであるかを判定。
    審議会中継等の動画リンク（youtube.com/live/..., watch?v=...）は除外しない。
    """
    if not url:
        return False
    u_lower = url.lower()
    for domain in _SNS_PR_DOMAINS:
        if domain in u_lower:
            return True
    if 'youtube.com' in u_lower:
        # YouTubeのチャンネル/ユーザー/トップページは除外（live/やwatch?v=は配付資料として許容）
        if any(p in u_lower for p in ['/user/', '/channel/', '/c/', '/@']) and not any(p in u_lower for p in ['/live/', 'watch?v=', '/embed/']):
            return True
    return False

def is_non_pdf_anchor_url(url):
    """
    配付資料URLが同一ページ内のアンカーリンク（#siryou, #contents 等）であるかを判定。
    PDF末尾の #page=1 等は正当なPDFへのアンカーのため除外しない。
    """
    if not url:
        return False
    u_clean = url.strip()
    if u_clean.startswith('#'):
        return True
    if '#' in u_clean:
        base, frag = u_clean.split('#', 1)
        base_lower = base.lower()
        if not base_lower.endswith(('.pdf', '.docx', '.xlsx', '.doc', '.xls')) and '/pdf/' not in base_lower:
            return True
    return False

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
    r'/int/kaisai/kako\.html|'
    r'policymeeting/(?:index\.html)?$|'
    r'menu_sosiki/singi/index\.html|'
    r'sonota_index\.html|'
    r'seisakusesaku_index\.html|'
    r'shingi_index\.html|'
    r'shingikai_index\.html|'
    r'iinkaisai/iinkaisai\.html|'
    r'bunkakaisai/bunkakaisai\.html|'
    r'yusei_kaisai\.html|'
    r'/kaisai/yusei/|'
    r'menu_news/s-news|'
    r'b_menu/houdou|'
    r'sitemap(?:\.html|\.xml|/)?$|'
    r'/sitemap/|'
    r'agenda/meeting/[^/]+/archive(?:_\d+-\d+)?\.html$|'
    r'archive_\d+-\d+\.html$|'
    r'base_gijiroku\.html|'
    r'top_gijiroku\.html|'
    r'bunkakai_index\.html|'
    r'member(?:\.html|/)?$|'
    r'meibo(?:\.html|/)?$|'
    r'_backno(?:\.html|/)?$|'
    r'index_backno(?:\.html|/)?$|'
    r'backnumber(?:\.html|/)?$|'
    r'b_menu/b004\.htm|'
    r'kaisai_yotei(?:/index\.html)?$|'
    r'/kaisai_yotei/|'
    r'/kaisaiyotei(?:\.html)?$|'
    r'shingi/kaisaiyotei(?:\.html)?|'
    r'/kaisai_yotei\.html$|'
    r'260915\.html|'
    r'/proceedings(?:_[a-z0-9_]+)?/(?:index\.html?)?$|'
    r'/proceedings/?$|'
    r'singi_kento/kento/\d{4}/(?:index\.html)?$',
    re.IGNORECASE
)

_GENERIC_INDEX_TITLE_KEYWORDS = frozenset({
    "覚書等", "覚書", "過去の国際会議",
    "研究会等一覧へのリンク", "会議資料詳細", "資料詳細", "会議詳細", "検討会等",
    "審議会等",
    "政策・審議会等", "省議・審議会等", "政策・審議会等トップへ", "審議会・研究会",
    "議事録・資料等", "目次",
    "会議開催予定", "開催予定一覧",
    "パブリックコメントの結果", "意見公募の趣旨", "ご意見等連絡先"
})

_GENERIC_INDEX_EXACT_TITLES = frozenset({
    "審議会", "政策・審議会等トップへ", "その他会議", "会議", "委員会",
    "目次", "<目次>", "議事録・資料等", "政策・審議会",
    "会議開催予定", "開催予定", "次回開催予定"
})

_FALLBACK_MINISTRY_EXCLUSIONS = {
    "FSC": {
        "exclude_url_patterns": ["fsc.go.jp/senmon/"],
        "exclude_title_keywords": ["食の安全、を科学する"]
    },
    "DIGITAL": {
        "exclude_url_patterns": ["digital.go.jp/en/", "digital.go.jp/councils/procurement-agile-opensource/"],
        "exclude_title_keywords": ["｜デジタル庁", "｜Digital Agency", "Digital Agency"]
    },
    "NPA": {
        "exclude_title_keywords": ["有識者会議｜警察庁"]
    },
    "FSA": {
        "exclude_url_patterns": ["strategic_priorities", "/ifiar/"],
        "exclude_title_keywords": ["金融行政方針", "事務年度金融行政方針", "監査監督機関国際フォーラム", "IFIAR"]
    },
    "MOJ": {
        "exclude_url_patterns": ["kanbou_library_library", "14th_congress_index"],
        "exclude_title_keywords": ["法務省の個人情報保護について", "赤れんが棟", "法制審議会開催予定表"]
    },
    "MOFA": {
        "exclude_title_keywords": ["外務省後援名義等の使用許可申請", "後援名義等の使用許可申請"]
    },
    "CAS": {
        "exclude_url_patterns": ["cas.go.jp/jp/s(?:i|hi)ryou", "cas.go.jp/jp/seisakukaigi/index.html"],
        "exclude_title_keywords": ["その他情報"]
    },
    "NRA": {
        "exclude_url_patterns": ["da.nra.go.jp/search"],
        "exclude_title_keywords": ["原子力規制委員会"]
    },
    "PPC": {
        "exclude_title_keywords": ["令和３年改正個人情報保護法について"]
    },
    "BUNKA": {
        "exclude_title_keywords": ["文化庁の紹介"]
    },
    "CAO": {
        "exclude_url_patterns": ["bousai.go.jp/kohou/oshirase/"]
    },
    "MHLW": {
        "exclude_url_patterns": ["topics/bukyoku/syakai/soren/", "kokurituken/gijiroku/attach/", "churoi/roushi"],
        "exclude_title_keywords": ["労使関係セミナー", "能力開発基本調査"]
    },
    "MIC": {
        "exclude_url_patterns": ["study/dai3sya/index.html"],
        "exclude_title_keywords": ["総務省の紹介"]
    }
}

_MINISTRY_EXCLUSIONS_MAP = {k: dict(v) for k, v in _FALLBACK_MINISTRY_EXCLUSIONS.items()}


_STATIC_ASSET_EXTS = frozenset({
    '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
    '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.mp3', '.zip', '.tar', '.gz'
})

def is_static_asset_url(url: str) -> bool:
    """画像、CSS、JSなどの静的アセットURLであるかを判定"""
    if not url:
        return False
    path = urllib.parse.urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in _STATIC_ASSET_EXTS)

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

NAV_EXCLUDE_TEXTS = frozenset({
    'ホーム', 'トップ', 'トップページ', 'トップへ', 'トップへ戻る', '目次', '政策について',
    '組織案内', 'プライバシーポリシー', 'サイトマップ', 'english', 'アクセス', 'リンク集',
    '戻る', '前のページへ戻る', '前のページへ', '次へ', '閉じる', 'メニュー', 'サイト内検索',
    '利用規約', 'ご意見・ご要望', '本文へ移動', 'フッターへ移動', 'page top', 'pagetop',
    '印刷', '印刷する', '文字サイズ', '拡大', '標準', '関連リンク', '施策紹介',
    '広報印刷物', '個人情報保護について',
    'オンライン利用率引上げ', '検査方針・研修実績等', '開催予定表',
    '調査の依頼方法', '調査の概要', '対象者別メニュー', '提供可能となる食品の情報',
    '新型コロナウイルス感染症に関する情報一覧', '感染症に関する情報一覧',
    '御意見・御感想', 'ご意見・ご感想', '会見記録', '記者会見',
    '開催通知', '開催案内', '開催告知', '開催通知等', '開催案内等', '開催告知等',
    '傍聴案内', '傍聴申込', '傍聴申込み', '傍聴について'
})

def is_generic_index_url(url, title="", ministry=None, rule=None):
    """
    報道発表インデックスやポータルトップ・開催状況一覧等の汎用インデックスURLかどうかを判定する。
    Drop 96: 汎用パターンに加え、省庁別除外設定（admin_configs）および会議体ルール（scraping_rules）を動的照合。
    """
    if not url:
        return True
    u_low = url.lower()
    if u_low.endswith(('.pdf', '.docx', '.xlsx', '.doc', '.xls')) or '/pdf/' in u_low:
        return False
    if _GENERIC_INDEX_URL_PATTERNS.search(u_low):
        return True
    if title:
        t_clean = title.strip()
        if t_clean in _GENERIC_INDEX_EXACT_TITLES:
            return True
        if any(k in t_clean for k in _GENERIC_INDEX_TITLE_KEYWORDS):
            return True

    # Drop 96: 省庁別除外URLパターンおよびタイトルキーワード照合
    matched_ministries = []
    if ministry:
        matched_ministries.append(normalize_ministry_code(ministry))
    else:
        try:
            parsed_host = urllib.parse.urlparse(url).netloc.lower()
            if parsed_host.startswith("www."):
                parsed_host = parsed_host[4:]
            for cand_code, doms in MINISTRY_DOMAINS.items():
                if any(parsed_host == d or parsed_host.endswith('.' + d) for d in doms):
                    matched_ministries.append(normalize_ministry_code(cand_code))
        except Exception:
            pass

    for m_code in matched_ministries:
        m_cfg = _MINISTRY_EXCLUSIONS_MAP.get(m_code, {})
        for pat in m_cfg.get("exclude_url_patterns", ()):
            if re.search(pat, u_low, re.IGNORECASE):
                return True
        if title:
            for kw in m_cfg.get("exclude_title_keywords", ()):
                if kw in title:
                    return True

    # Drop 96: 会議体別除外URLパターン照合
    if rule and isinstance(rule, dict):
        for pat in rule.get("exclude_subpage_url_patterns", ()):
            if pat.lower() in u_low:
                return True
        if title:
            for kw in rule.get("exclude_subpage_title_keywords", ()):
                if kw.lower() in title.lower():
                    return True

    return False

def is_preliminary_notice_page(url, title=""):
    """
    開催案内・事前告知ページ（例: .../kaisai/index.html, .../annai/..., .../kaisaiannai/..., 〜の開催について）や資料未添付の議事要旨・議事録単体ページであるかを判定。
    これらは資料が掲載される会議ページではないため、独立した会議として追加しない（AGENTS.md 第11条・第12条）。
    """
    if not url and not title:
        return False
    u_lower = (url or "").lower()
    # URLに /annai/ や /kaisaiannai/ や /online_kaisai, /event/, /seminar/, /kaisai_yotei/ 等が含まれる場合
    if re.search(r'/(?:kaisaiannai|online_kaisai|annai|event|seminar|kaisai_yotei|kaisaiyotei)/', u_lower) or \
       'kaisaiannai' in u_lower or '_annai_' in u_lower or \
       'annai_' in u_lower or 'kaisai_yotei' in u_lower or 'kaisaiyotei' in u_lower or \
       u_lower.endswith('/annai.html') or u_lower.endswith('/kaisai_annai.html') or \
       u_lower.endswith('/kaisai_yotei.html') or u_lower.endswith('/kaisaiyotei.html'):
        return True

    t_raw = (title or "").strip()
    # 1. 末尾の省庁・行政機関名サフィックスを安全に除去
    t_clean = GOV_SUFFIX_REGEX.sub('', t_raw).strip()
    # 2. 末尾の括弧表記（例: （非公開）、（WEB開催）、（ペーパーレス・Web併用）、（オンライン会議）等）を繰り返し安全に除去
    while True:
        m_paren = re.search(r'[\(（][^\)）]+[\)）]$', t_clean)
        if m_paren:
            t_clean = t_clean[:m_paren.start()].strip()
        else:
            break

    # 2.5 タイトル完全一致での開催予定・案内判定
    if t_clean in ['会議開催予定', '開催予定', '次回開催予定', '開催案内', '開催通知', '次回開催通知', '開催告知']:
        return True

    # 3. 末尾の開催案内・事前告知キーワード判定
    if re.search(r'(?:の開催予定について|開催予定について|の開催案内について|開催案内について|の開催通知について|開催通知について|の開催について|開催について|の開催告知について|開催告知について|の開催通知|開催通知|の開催告知|開催告知|の開催のお知らせについて|開催のお知らせについて|の開催案内|開催案内|の開催のお知らせ|開催のお知らせ|の開催|開催|傍聴の案内|傍聴について|傍聴される皆様への留意事項|の開催概要について|傍聴の受付|傍聴申込み|傍聴申込|傍聴の申込について|傍聴の申込みについて|議事要旨|議事録|のご案内|の案内|問い合わせ先|情報配信サービス|取材の案内について|取材について)$', t_clean):
        return True

    # 4. タイトル途中に「開催案内」「傍聴の案内」「開催告知」「会議開催予定」「標記の会議について」「下記のとおり開催」等が含まれる場合
    if any(kw in t_raw for kw in [
        '開催案内', '開催通知', 'の開催通知', '開催告知', '会議開催予定', '傍聴される皆様への留意事項', '傍聴留意事項', '傍聴申込', '傍聴の受付', '傍聴申込み',
        '傍聴の申込', '傍聴の申込み', '取材の案内', '取材申込み', '取材申込',
        '標記の会議について', '下記のとおり開催', '以下のとおり開催', 'を開催します', 'を開催いたします'
    ]):
        return True
    if re.search(r'[（\(](?:第\d+回)?開催案内[）\)]', t_raw) or '[開催案内]' in t_raw or '【開催案内】' in t_raw:
        return True
    if re.search(r'(?:[\s\u3000]+|（|\()(?:傍聴|取材)(?:の案内|について|希望|申込|申込み)?(?:[\s\u3000]+|）|\)|$)', t_raw):
        return True
    if re.search(r'を開催します[\s\u3000]*[\(（][^\)）]*案内', t_raw):
        return True

    # 5. 非会議タイトル（セミナー、調査、公表資料・告示・意見等 & 省庁別除外設定連動）
    if any(kw in t_raw for kw in [
        '調査の実施について', '問い合わせ先', '情報配信サービス',
        'イベント概要', 'セミナーのご案内',
        '指定研修機関の指定等について', '研修内容に関する意見', '基準に関する意見'
    ]):
        return True

    if url and is_generic_index_url(url, t_raw):
        return True

    return False
