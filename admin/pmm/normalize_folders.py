#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
PMM Folder Normalization & Deduplication Tool (admin/pmm/normalize_folders.py)
=============================================================================
Normalizes meeting folder names across all ministries in local_docs/
based strictly on `meetings.name` from database/data.json.
Merges non-canonical folders into canonical folders, protecting unique files
and preserving '00_会議体資料'.
"""

import argparse
import atexit
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# PMM Common
from .pmm_common import (
    BASE_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_DATA_JSON,
    DEFAULT_DB_PATH,
    COUNCIL_MATERIALS_FOLDER,
    setup_logger,
    sanitize_filename,
    clean_material_name,
    format_meeting_folder_name,
    files_are_identical,
    safe_unlink,
    safe_rmdir,
    safe_move_file,
)

# PMHub Database
try:
    from ..db.db_manager import load_data_from_db
except ImportError:
    sys.path.insert(0, str(BASE_DIR))
    from admin.db.db_manager import load_data_from_db

LOCK_FILE = BASE_DIR / "admin" / ".normalize.lock"


def acquire_lock():
    if LOCK_FILE.exists():
        try:
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            process = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if process != 0:
                kernel32.CloseHandle(process)
                print(f"[ERROR] Another normalize_folders process (PID {pid}) is already running!")
                sys.exit(1)
        except Exception:
            pass

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    def release_lock():
        if LOCK_FILE.exists():
            try:
                LOCK_FILE.unlink()
            except OSError:
                pass
    atexit.register(release_lock)


def clean_alt_duplicates(canon_dir: Path, logger: logging.Logger) -> int:
    """Remove any `*_alt*` files in the folder if they have identical content."""
    removed = 0
    if not canon_dir.is_dir():
        return 0

    try:
        files = [canon_dir / f for f in os.listdir(canon_dir) if (canon_dir / f).is_file()]
    except OSError:
        return 0

    alt_files = [f for f in files if "_alt" in f.name]
    if not alt_files:
        return 0

    normal_files_by_size = defaultdict(list)
    for f in files:
        if "_alt" not in f.name:
            try:
                normal_files_by_size[f.stat().st_size].append(f)
            except OSError:
                pass

    for alt_f in alt_files:
        try:
            alt_size = alt_f.stat().st_size
        except OSError:
            continue
        candidates = normal_files_by_size.get(alt_size, [])
        for cand in candidates:
            if files_are_identical(alt_f, cand, alt_size):
                if safe_unlink(alt_f):
                    removed += 1
                    logger.debug(f"Removed duplicate alt file: {alt_f.name}")
                break
    return removed


def build_canonical_map(
    data: Dict[str, Any],
    base_dir: Path
) -> Tuple[
    Dict[Tuple[str, str], Set[str]],
    Dict[Tuple[str, str], Dict[str, List[str]]],
    Dict[Tuple[str, str], Dict[str, Set[str]]],
    Set[Path]
]:
    ministries_dict = data.get("ministries", {})
    councils_dict = {c["id"]: c for c in data.get("councils", []) if "id" in c}
    meetings = data.get("meetings", [])

    canonical_folders_by_council = defaultdict(set)
    date_to_canons = defaultdict(lambda: defaultdict(list))
    canon_materials = defaultdict(lambda: defaultdict(set))
    canonical_paths = set()

    for m in meetings:
        cid = m.get("councilId", "")
        c_info = councils_dict.get(cid, {})

        min_code = m.get("ministry") or c_info.get("ministry") or "UNKNOWN"
        min_info = ministries_dict.get(min_code, {})
        min_name = min_info.get("name") or min_info.get("kanji") or min_code
        min_name_sanitized = sanitize_filename(min_name, max_len=60)

        c_name = c_info.get("name") or m.get("councilName") or "会議体不明"
        c_name_sanitized = sanitize_filename(c_name, max_len=80)

        folder = format_meeting_folder_name(m, c_name)
        key = (min_name_sanitized, c_name_sanitized)

        canonical_folders_by_council[key].add(folder)

        m_date = re.sub(r'[^0-9]', '', m.get("date", ""))[:8]
        if m_date:
            if folder not in date_to_canons[key][m_date]:
                date_to_canons[key][m_date].append(folder)

        for mat in m.get("materials", []):
            m_raw = mat.get("name", "")
            if m_raw:
                c_mat = clean_material_name(m_raw)
                canon_materials[key][folder].add(sanitize_filename(c_mat, max_len=100).lower())

        canon_dir = (base_dir / min_name_sanitized / c_name_sanitized / folder).resolve()
        canonical_paths.add(canon_dir)

    return canonical_folders_by_council, date_to_canons, canon_materials, canonical_paths


def choose_best_canonical(
    non_canon_folder_name: str,
    src_file_names: List[str],
    candidate_canons: List[str],
    council_path: Path,
    expected_materials: Dict[str, Set[str]]
) -> str:
    if len(candidate_canons) == 1:
        return candidate_canons[0]

    for cand in candidate_canons:
        cand_suffix = cand.split("_", 1)[1] if "_" in cand else ""
        if cand_suffix and cand_suffix in non_canon_folder_name:
            return cand

    scores = {}
    for cand in candidate_canons:
        score = 0
        cand_path = council_path / cand
        cand_existing = set()
        if cand_path.is_dir():
            cand_existing = {f.lower() for f in os.listdir(cand_path)}
        expected = expected_materials.get(cand, set())

        for sf in src_file_names:
            sf_clean = sf.lower()
            if sf_clean in cand_existing:
                score += 3
            for exp in expected:
                if exp and exp in sf_clean:
                    score += 2
            cand_suffix = cand.split("_", 1)[1] if "_" in cand else ""
            if cand_suffix and cand_suffix.lower() in sf_clean:
                score += 1
        scores[cand] = score

    best_cand = max(scores.keys(), key=lambda k: scores[k])
    return best_cand


def normalize_and_deduplicate(
    target_dir: Path,
    canonical_folders_by_council: Dict[Tuple[str, str], Set[str]],
    date_to_canons: Dict[Tuple[str, str], Dict[str, List[str]]],
    canon_materials: Dict[Tuple[str, str], Dict[str, Set[str]]],
    canonical_paths: Set[Path],
    dry_run: bool,
    logger: logging.Logger,
    ministry_filter: Optional[str] = None
) -> Dict[str, int]:
    stats = {
        "canonical_folders_checked": 0,
        "non_canonical_folders": 0,
        "merged_folders": 0,
        "duplicate_files_deleted": 0,
        "unique_files_moved": 0,
        "folders_removed": 0,
        "alt_duplicates_removed": 0,
        "errors": 0
    }

    target_dir = target_dir.resolve()
    if not target_dir.exists():
        logger.error(f"Target directory does not exist: {target_dir}")
        return stats

    try:
        ministry_entries = [e for e in os.scandir(target_dir) if e.is_dir()]
    except OSError as e:
        logger.error(f"Failed to scan target directory: {e}")
        return stats

    for min_entry in sorted(ministry_entries, key=lambda e: e.name):
        min_name = min_entry.name
        if ministry_filter and ministry_filter not in min_name:
            continue

        logger.info(f"Processing ministry: {min_name} ...")
        min_path = Path(min_entry.path)
        try:
            council_entries = [e for e in os.scandir(min_path) if e.is_dir()]
        except OSError:
            continue

        for council_entry in sorted(council_entries, key=lambda e: e.name):
            c_name = council_entry.name
            council_path = Path(council_entry.path)
            key = (min_name, c_name)

            valid_canonical_names = canonical_folders_by_council.get(key, set())
            date_map = date_to_canons.get(key, {})
            council_materials = canon_materials.get(key, {})

            try:
                meeting_dir_names = [f for f in os.listdir(council_path) if (council_path / f).is_dir()]
            except OSError:
                continue

            for m_name in sorted(meeting_dir_names):
                # Never touch 00_会議体資料 or system folders
                if m_name == COUNCIL_MATERIALS_FOLDER or m_name.startswith((".", "_")):
                    continue

                meeting_path = council_path / m_name
                if m_name in valid_canonical_names:
                    stats["canonical_folders_checked"] += 1
                    continue

                stats["non_canonical_folders"] += 1
                m_match = re.match(r'^(\d{8})(_|$)', m_name)
                date_prefix = m_match.group(1) if m_match else None
                candidate_canons = date_map.get(date_prefix, []) if date_prefix else []

                if not candidate_canons:
                    try:
                        if meeting_path.exists() and not os.listdir(meeting_path):
                            if not dry_run and safe_rmdir(meeting_path):
                                stats["folders_removed"] += 1
                                logger.info(f"Removed empty unknown folder: {meeting_path.relative_to(target_dir)}")
                            elif dry_run:
                                stats["folders_removed"] += 1
                    except OSError:
                        pass
                    continue

                try:
                    src_file_names = [f for f in os.listdir(meeting_path) if (meeting_path / f).is_file()]
                except OSError:
                    src_file_names = []

                if not src_file_names:
                    if not dry_run and meeting_path.exists():
                        if safe_rmdir(meeting_path):
                            stats["folders_removed"] += 1
                            logger.debug(f"Removed empty non-canonical folder: {meeting_path.relative_to(target_dir)}")
                    elif dry_run:
                        stats["folders_removed"] += 1
                    continue

                chosen_canon = choose_best_canonical(
                    non_canon_folder_name=m_name,
                    src_file_names=src_file_names,
                    candidate_canons=candidate_canons,
                    council_path=council_path,
                    expected_materials=council_materials
                )
                dest_canon_path = (council_path / chosen_canon).resolve()
                stats["merged_folders"] += 1

                if not dry_run:
                    dest_canon_path.mkdir(parents=True, exist_ok=True)

                dest_sizes = defaultdict(list)
                dest_files = {}
                if dest_canon_path.exists():
                    for f_name in os.listdir(dest_canon_path):
                        f_path = dest_canon_path / f_name
                        if f_path.is_file():
                            try:
                                dest_files[f_name] = f_path
                                dest_sizes[f_path.stat().st_size].append(f_path)
                            except Exception:
                                pass

                for f_name in src_file_names:
                    s_file = meeting_path / f_name
                    if not s_file.exists():
                        continue
                    try:
                        s_size = s_file.stat().st_size
                    except Exception as e:
                        logger.debug(f"Cannot stat file {s_file}: {e}")
                        stats["errors"] += 1
                        continue

                    target_file = dest_canon_path / s_file.name
                    is_dup = False
                    if target_file.name in dest_files:
                        dest_f = dest_files[target_file.name]
                        if files_are_identical(s_file, dest_f, s_size):
                            is_dup = True
                    else:
                        for candidate_dest in dest_sizes.get(s_size, []):
                            if files_are_identical(s_file, candidate_dest, s_size):
                                is_dup = True
                                break

                    if is_dup:
                        if not dry_run:
                            if safe_unlink(s_file):
                                stats["duplicate_files_deleted"] += 1
                                logger.debug(f"Deleted duplicate: {s_file.name}")
                            else:
                                stats["errors"] += 1
                        else:
                            stats["duplicate_files_deleted"] += 1
                    else:
                        final_dest = target_file
                        if final_dest.exists():
                            stem = final_dest.stem
                            ext = final_dest.suffix
                            idx = 1
                            while final_dest.exists():
                                final_dest = dest_canon_path / f"{stem}_alt{idx}{ext}"
                                idx += 1

                        if not dry_run:
                            if safe_move_file(s_file, final_dest):
                                stats["unique_files_moved"] += 1
                                dest_files[final_dest.name] = final_dest
                                dest_sizes[s_size].append(final_dest)
                                logger.info(f"Moved unique file: {s_file.name} -> {final_dest.name}")
                            else:
                                stats["errors"] += 1
                        else:
                            stats["unique_files_moved"] += 1

                try:
                    if not dry_run and meeting_path.exists():
                        rem_files = [f for f in os.listdir(meeting_path) if (meeting_path / f).is_file()]
                        if not rem_files:
                            if safe_rmdir(meeting_path):
                                stats["folders_removed"] += 1
                                logger.debug(f"Removed emptied folder: {meeting_path.name}")
                    elif dry_run:
                        stats["folders_removed"] += 1
                except OSError:
                    pass

                if not dry_run and dest_canon_path.exists():
                    stats["alt_duplicates_removed"] += clean_alt_duplicates(dest_canon_path, logger)

    return stats


def main():
    parser = argparse.ArgumentParser(description="PMM Folder Normalization & Deduplication Tool")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry-run without moving or deleting files")
    parser.add_argument("--ministry", type=str, default=None, help="Filter to a specific ministry")
    parser.add_argument("--target-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Target local_docs directory")
    args = parser.parse_args()

    acquire_lock()
    logger = setup_logger("normalize")
    data = load_data_from_db()
    target_dir = Path(args.target_dir)

    canon_by_council, date_map, canon_mats, canon_paths = build_canonical_map(data, target_dir)
    stats = normalize_and_deduplicate(
        target_dir=target_dir,
        canonical_folders_by_council=canon_by_council,
        date_to_canons=date_map,
        canon_materials=canon_mats,
        canonical_paths=canon_paths,
        dry_run=args.dry_run,
        logger=logger,
        ministry_filter=args.ministry
    )
    logger.info(f"Done: {stats}")


if __name__ == "__main__":
    main()
