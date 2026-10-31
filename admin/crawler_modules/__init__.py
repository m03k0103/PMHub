# -*- coding: utf-8 -*-
"""
admin.crawler_modules package
PMHub クローラーモジュール群 (Drop 115)
責務ごとに分離されたサブモジュール:
- host_manager: ホスト抽出・分散 (interleave_by_host_and_ministry, get_council_host, extract_host)
- filters: 各種URL・タイトル・ナビ・不要アセットフィルタリング
- extractors: タイトル正規化・文脈復元・日付・議事録テキスト抽出
"""

import sys
import os

_this_dir = os.path.dirname(os.path.abspath(__file__))
_admin_dir = os.path.dirname(_this_dir)
_root_dir = os.path.dirname(_admin_dir)
for p in (_root_dir, _admin_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

from .host_manager import (
    interleave_by_host_and_ministry,
    interleave_by_ministry,
    get_council_host,
    extract_host,
    _extract_council_host,
)

from .filters import (
    is_sns_pr_url,
    is_non_pdf_anchor_url,
    is_generic_index_url,
    is_generic_material_name,
    is_generic_title_text,
    is_preliminary_notice_page,
    is_static_asset_url,
    _is_parent_or_nav_url,
    _SNS_PR_DOMAINS,
    _GENERIC_INDEX_URL_PATTERNS,
    _GENERIC_INDEX_TITLE_KEYWORDS,
    _GENERIC_INDEX_EXACT_TITLES,
    GENERIC_MATERIAL_NAMES,
    GENERIC_TITLE_KEYWORDS,
    GENERIC_EXACT_ONLY_KEYWORDS,
    COMMON_NAV_KEYWORDS,
    NAV_EXCLUDE_TEXTS,
    GOV_SUFFIX_REGEX,
    _FALLBACK_MINISTRY_EXCLUSIONS,
    _MINISTRY_EXCLUSIONS_MAP,
)

from .extractors import (
    DEFAULT_DATE_REGEX,
    clean_meeting_title,
    recover_material_context,
    parse_txt_minutes,
    extract_page_title,
    _extract_date_from_url,
    _resolve_meeting_date,
)

# 後方互換性エイリアス
_GENERIC_MATERIAL_NAMES = GENERIC_MATERIAL_NAMES
_GENERIC_TITLE_PATTERNS = GENERIC_TITLE_KEYWORDS

__all__ = [
    "interleave_by_host_and_ministry",
    "interleave_by_ministry",
    "get_council_host",
    "extract_host",
    "_extract_council_host",
    "is_sns_pr_url",
    "is_non_pdf_anchor_url",
    "is_generic_index_url",
    "is_generic_material_name",
    "is_generic_title_text",
    "is_preliminary_notice_page",
    "is_static_asset_url",
    "_is_parent_or_nav_url",
    "_SNS_PR_DOMAINS",
    "_GENERIC_INDEX_URL_PATTERNS",
    "_GENERIC_INDEX_TITLE_KEYWORDS",
    "_GENERIC_INDEX_EXACT_TITLES",
    "GENERIC_MATERIAL_NAMES",
    "GENERIC_TITLE_KEYWORDS",
    "GENERIC_EXACT_ONLY_KEYWORDS",
    "COMMON_NAV_KEYWORDS",
    "NAV_EXCLUDE_TEXTS",
    "GOV_SUFFIX_REGEX",
    "_FALLBACK_MINISTRY_EXCLUSIONS",
    "_MINISTRY_EXCLUSIONS_MAP",
    "_GENERIC_MATERIAL_NAMES",
    "_GENERIC_TITLE_PATTERNS",
    "DEFAULT_DATE_REGEX",
    "clean_meeting_title",
    "recover_material_context",
    "parse_txt_minutes",
    "extract_page_title",
    "_extract_date_from_url",
    "_resolve_meeting_date",
]
