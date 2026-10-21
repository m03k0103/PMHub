#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
PMM Cleanup Tool (admin/pmm/cleanup.py)
======================================
Scans local_docs/ and removes meeting folders that are no longer
present in pmhub.db/data.json, strictly preserving '00_会議体資料'.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# PMM Common
from .pmm_common import (
    BASE_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_DATA_JSON,
    DEFAULT_DB_PATH,
    COUNCIL_MATERIALS_FOLDER,
    setup_logger,
    sanitize_filename,
    format_meeting_folder_name,
    safe_rmtree,
)

# PMHub Database
try:
    from ..db.db_manager import load_data_from_db
except ImportError:
    sys.path.insert(0, str(BASE_DIR))
    from admin.db.db_manager import load_data_from_db


def build_valid_meeting_paths(data: Dict[str, Any], base_dir: Path) -> Set[Path]:
    """Extract set of valid meeting directory paths from data dictionary."""
    ministries_dict = data.get("ministries", {})
    councils_dict = {c["id"]: c for c in data.get("councils", []) if "id" in c}
    meetings = data.get("meetings", [])

    valid_paths = set()

    for m in meetings:
        cid = m.get("councilId", "")
        c_info = councils_dict.get(cid, {})

        min_code = m.get("ministry") or c_info.get("ministry") or "UNKNOWN"
        min_info = ministries_dict.get(min_code, {})
        min_name = min_info.get("name") or min_info.get("kanji") or min_code
        min_name_sanitized = sanitize_filename(min_name, max_len=60)

        c_name = c_info.get("name") or m.get("councilName") or "会議体不明"
        c_name_sanitized = sanitize_filename(c_name, max_len=80)

        m_folder = format_meeting_folder_name(m, c_name)

        meeting_dir = (base_dir / min_name_sanitized / c_name_sanitized / m_folder).resolve()
        valid_paths.add(meeting_dir)

    return valid_paths


def scan_cleanup_targets(
    target_dir: Path,
    valid_paths: Set[Path]
) -> List[Tuple[Path, int, int, str]]:
    cleanup_targets = []
    target_dir = target_dir.resolve()

    if not target_dir.exists():
        return []

    for min_entry in os.scandir(target_dir):
        if not min_entry.is_dir() or min_entry.name.startswith((".", "_")):
            continue

        for council_entry in os.scandir(min_entry.path):
            if not council_entry.is_dir() or council_entry.name.startswith((".", "_")):
                continue

            for meeting_entry in os.scandir(council_entry.path):
                # Strictly protect 00_会議体資料 and system folders
                if not meeting_entry.is_dir() or meeting_entry.name == COUNCIL_MATERIALS_FOLDER or meeting_entry.name.startswith((".", "_")):
                    continue

                meeting_path = Path(meeting_entry.path).resolve()
                f_count = 0
                t_bytes = 0
                for root, _, files in os.walk(meeting_path):
                    for f in files:
                        f_count += 1
                        try:
                            t_bytes += os.path.getsize(os.path.join(root, f))
                        except OSError:
                            pass

                is_obsolete = meeting_path not in valid_paths
                is_empty = (f_count == 0)

                if is_obsolete and is_empty:
                    cleanup_targets.append((meeting_path, f_count, t_bytes, "未定義かつ空フォルダ"))
                elif is_obsolete:
                    cleanup_targets.append((meeting_path, f_count, t_bytes, "未定義フォルダ（data.jsonに無し）"))
                elif is_empty:
                    cleanup_targets.append((meeting_path, f_count, t_bytes, "空フォルダ（ファイル0件）"))

    return cleanup_targets


def clean_empty_parent_dirs(target_dir: Path, logger: logging.Logger, dry_run: bool):
    """Clean up empty council and ministry directories."""
    target_dir = target_dir.resolve()
    if not target_dir.exists():
        return

    for min_entry in os.scandir(target_dir):
        if not min_entry.is_dir() or min_entry.name.startswith((".", "_")):
            continue
        for council_entry in os.scandir(min_entry.path):
            if not council_entry.is_dir() or council_entry.name.startswith((".", "_")):
                continue
            council_path = Path(council_entry.path)
            try:
                if not any(os.scandir(council_path)):
                    if not dry_run:
                        council_path.rmdir()
                        logger.info(f"Removed empty council folder: {council_path.name}")
                    else:
                        logger.info(f"[DRY-RUN] Would remove empty council folder: {council_path.name}")
            except OSError:
                pass

        min_path = Path(min_entry.path)
        try:
            if not any(os.scandir(min_path)):
                if not dry_run:
                    min_path.rmdir()
                    logger.info(f"Removed empty ministry folder: {min_path.name}")
                else:
                    logger.info(f"[DRY-RUN] Would remove empty ministry folder: {min_path.name}")
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description="PMM Cleanup Tool - Remove obsolete or empty meeting folders")
    parser.add_argument("--target", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Target local_docs directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview folders to be removed without deleting")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt and execute deletion")
    args = parser.parse_args()

    target_dir = Path(args.target)
    logger = setup_logger("cleanup")
    data = load_data_from_db()

    valid_paths = build_valid_meeting_paths(data, target_dir)
    cleanup_targets = scan_cleanup_targets(target_dir, valid_paths)

    if not cleanup_targets:
        logger.info("No obsolete or empty meeting folders found.")
        clean_empty_parent_dirs(target_dir, logger, dry_run=args.dry_run)
        return

    total_files = sum(count for _, count, _, _ in cleanup_targets)
    total_bytes = sum(b for _, _, b, _ in cleanup_targets)
    logger.warning(f"Found {len(cleanup_targets)} meeting folder(s) to cleanup ({total_files} files, {total_bytes / (1024 * 1024):.2f} MB).")

    if args.dry_run:
        logger.info("[DRY-RUN] Simulation complete.")
        return

    if not args.yes:
        print("\n上記のフォルダを完全に削除しますか？ (y/N): ", end="", flush=True)
        choice = input().strip().lower()
        if choice not in ("y", "yes"):
            logger.info("Cleanup cancelled by user.")
            return

    deleted = 0
    for p, _, _, _ in cleanup_targets:
        if safe_rmtree(p):
            deleted += 1
            logger.info(f"[DELETED] {p.name}")

    clean_empty_parent_dirs(target_dir, logger, dry_run=False)
    logger.info(f"Cleanup completed: {deleted} deleted.")


if __name__ == "__main__":
    main()
