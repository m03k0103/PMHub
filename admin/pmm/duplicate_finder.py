#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Duplicate File Finder for PMM (admin/pmm/duplicate_finder.py)
=============================================================
Scans local_docs/ to detect duplicate files using a 3-stage high performance
algorithm (Size -> Quick Hash -> Full SHA-256). Generates summary, CSV, and JSON reports.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# PMM Common
from .pmm_common import BASE_DIR, DEFAULT_OUTPUT_DIR

DEFAULT_SCAN_DIR = DEFAULT_OUTPUT_DIR
DEFAULT_REPORT_DIR = BASE_DIR / "admin" / "reports"
CHUNK_SIZE = 64 * 1024  # 64 KB
QUICK_HASH_SIZE = 8 * 1024  # 8 KB


def format_bytes(size: int) -> str:
    """Format bytes to human readable string (KB, MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def get_quick_hash(path: Path) -> Optional[str]:
    """Calculate hash of the first 8KB of a file."""
    try:
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            chunk = f.read(QUICK_HASH_SIZE)
            hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, PermissionError):
        return None


def get_full_sha256(path: Path) -> Optional[str]:
    """Calculate full SHA-256 hash of a file."""
    try:
        hasher = hashlib.sha256()
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, PermissionError):
        return None


class DuplicateFinder:
    def __init__(
        self,
        target_dir: Path,
        min_size: int = 1,
        max_size: Optional[int] = None,
        threads: int = 8
    ):
        self.target_dir = target_dir
        self.min_size = min_size
        self.max_size = max_size
        self.threads = threads

    def scan_files(self) -> Tuple[List[Path], Dict[int, List[Path]]]:
        print(f"[*] 走査中: {self.target_dir}")
        all_files: List[Path] = []
        size_to_files: Dict[int, List[Path]] = defaultdict(list)

        count = 0
        for root, _, filenames in os.walk(self.target_dir):
            for fname in filenames:
                fpath = Path(root) / fname
                try:
                    if fpath.is_symlink():
                        continue
                    sz = fpath.stat().st_size
                    if sz < self.min_size:
                        continue
                    if self.max_size and sz > self.max_size:
                        continue
                    all_files.append(fpath)
                    size_to_files[sz].append(fpath)
                    count += 1
                    if count % 10000 == 0:
                        print(f"    - {count} ファイル走査完了...")
                except (OSError, PermissionError):
                    continue

        print(f"[+] 対象ファイル数: {len(all_files):,} 件 (ユニークサイズ候補: {len(size_to_files):,} 種)")
        return all_files, size_to_files

    def find_duplicates(self) -> Dict[str, List[Path]]:
        _, size_to_files = self.scan_files()
        potential_size_groups = [files for size, files in size_to_files.items() if len(files) > 1]
        candidates_stage1 = sum(len(f) for f in potential_size_groups)
        print(f"[*] ステージ1完了: 同一サイズを持つ候補ファイル {candidates_stage1:,} 件 ({len(potential_size_groups):,} グループ)")

        if not potential_size_groups:
            return {}

        flat_candidates = [f for grp in potential_size_groups for f in grp]
        quick_hash_map: Dict[Tuple[int, str], List[Path]] = defaultdict(list)

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            results = executor.map(lambda p: (p, p.stat().st_size, get_quick_hash(p)), flat_candidates)
            for path, sz, qhash in results:
                if qhash:
                    quick_hash_map[(sz, qhash)].append(path)

        potential_quick_groups = [files for k, files in quick_hash_map.items() if len(files) > 1]
        candidates_stage2 = sum(len(f) for f in potential_quick_groups)
        print(f"[*] ステージ2完了: 高速ハッシュ一致候補 {candidates_stage2:,} 件 ({len(potential_quick_groups):,} グループ)")

        if not potential_quick_groups:
            return {}

        flat_stage2 = [f for grp in potential_quick_groups for f in grp]
        full_hash_map: Dict[str, List[Path]] = defaultdict(list)

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            results = executor.map(lambda p: (p, get_full_sha256(p)), flat_stage2)
            for path, fhash in results:
                if fhash:
                    full_hash_map[fhash].append(path)

        duplicates = {h: files for h, files in full_hash_map.items() if len(files) > 1}
        return duplicates


def main():
    parser = argparse.ArgumentParser(description="PMM Duplicate File Finder")
    parser.add_argument("--target", type=str, default=str(DEFAULT_SCAN_DIR), help="Directory to scan")
    parser.add_argument("--threads", type=int, default=8, help="Worker threads")
    args = parser.parse_args()

    finder = DuplicateFinder(Path(args.target), threads=args.threads)
    dups = finder.find_duplicates()
    total_dup_files = sum(len(f) for f in dups.values())
    wasted = sum((len(f) - 1) * f[0].stat().st_size for f in dups.values())
    print(f"\n[+] 重複検知結果: {len(dups):,} 種の重複グループ ({total_dup_files:,} ファイル, 削減可能容量: {format_bytes(wasted)})")


if __name__ == "__main__":
    main()
