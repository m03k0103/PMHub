#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 共通ユーティリティ (admin/utils.py)

プロジェクト内の各 Python スクリプトから共通利用するユーティリティ関数を定義する。
"""

import sys
import os
import io


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
