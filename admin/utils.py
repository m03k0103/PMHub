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
import shutil
from datetime import datetime

# パス定義
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DEFAULT_DATA_JSON_PATH = os.path.join(PROJECT_ROOT, "docs", "data.json")
DEFAULT_BACKUP_DIR = os.path.join(BASE_DIR, "backups")


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
