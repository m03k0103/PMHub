# -*- coding: utf-8 -*-
"""
admin.discovery_modules package
PMHub 新規会議体ディスカバリーモジュール群 (Drop 116)
- name_cleaner: 会議体名正規化・コア名抽出・カテゴリ判定・タイトル抽出
- noise_filters: ノイズ判定・単一プレスURL判定・登録済判定
- parent_resolver: プレスリリースから常設親ページURL逆引き
"""

import sys
import os

_this_dir = os.path.dirname(os.path.abspath(__file__))
_admin_dir = os.path.dirname(_this_dir)
_root_dir = os.path.dirname(_admin_dir)
for p in (_root_dir, _admin_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

from .name_cleaner import (
    normalize_ministry_code,
    infer_council_category,
    clean_council_name,
    get_core_council_name,
    extract_council_name_from_news_title,
    MINISTRY_CODE_NORMALIZATION,
)

from .noise_filters import (
    NOISE_PERSON_ROLES,
    NOISE_ACTION_PATTERNS,
    NOISE_INTERNATIONAL_AND_ORGS,
    NOISE_INTERNATIONAL_REGEX,
    NOISE_PORTAL_EXACT,
    PRESS_RELEASE_EXCLUSIVE_PATTERNS,
    PRESS_RELEASE_EXCLUSIVE_REGEX,
    is_single_press_or_notice_url,
    is_non_council_noise,
    normalize_url,
    get_url_clean_key,
    get_max_seq,
    is_already_registered_or_rejected,
)

from .parent_resolver import (
    fetch_page_and_final_url,
    resolve_parent_url_from_press_release,
)

__all__ = [
    "normalize_ministry_code",
    "infer_council_category",
    "clean_council_name",
    "get_core_council_name",
    "extract_council_name_from_news_title",
    "MINISTRY_CODE_NORMALIZATION",
    "NOISE_PERSON_ROLES",
    "NOISE_ACTION_PATTERNS",
    "NOISE_INTERNATIONAL_AND_ORGS",
    "NOISE_INTERNATIONAL_REGEX",
    "NOISE_PORTAL_EXACT",
    "PRESS_RELEASE_EXCLUSIVE_PATTERNS",
    "PRESS_RELEASE_EXCLUSIVE_REGEX",
    "is_single_press_or_notice_url",
    "is_non_council_noise",
    "normalize_url",
    "get_url_clean_key",
    "get_max_seq",
    "is_already_registered_or_rejected",
    "fetch_page_and_final_url",
    "resolve_parent_url_from_press_release",
]
