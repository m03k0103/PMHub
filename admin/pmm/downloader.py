#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
PMHub Materials Downloader (admin/pmm/downloader.py)
===================================================
Downloads and manages meeting materials and council permanent materials (00_会議体資料)
into local_docs/ following ministry-isolated sequential queuing and automatic migration.
Synchronizes download status with SQLite database (admin/pmhub.db).
"""

import argparse
import concurrent.futures
import json
import logging
import os
import shutil
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
    guess_extension_from_url_or_type,
    files_are_identical,
    safe_unlink,
    safe_move_file,
    get_council_materials_dir,
    get_meeting_dir,
)

# PMHub Database
try:
    from ..db.db_manager import (
        load_data_from_db,
        update_materials_download_batch,
        update_council_materials_download_batch,
    )
except ImportError:
    # Standalone execution fallback
    sys.path.insert(0, str(BASE_DIR))
    from admin.db.db_manager import (
        load_data_from_db,
        update_materials_download_batch,
        update_council_materials_download_batch,
    )


def resolve_existing_target_path(path: Path) -> Optional[Path]:
    """Check if target file exists and size > 0. Check .html fallback if path is .pdf."""
    try:
        if path.exists() and path.stat().st_size > 0:
            return path
        if path.suffix.lower() == ".pdf":
            html_path = path.with_suffix(".html")
            if html_path.exists() and html_path.stat().st_size > 0:
                return html_path
    except OSError:
        pass
    return None


class MaterialTask:
    def __init__(
        self,
        task_type: str,  # 'meeting' or 'council'
        parent_id: str,   # meeting_id or council_id
        council_id: str,
        ministry_name: str,
        council_name: str,
        folder_name: str,
        material_name: str,
        url: str,
        mat_type: Optional[str],
        dest_dir: Path,
        suffix_index: int = 1,
        preceding_paths: Optional[List[Path]] = None,
    ):
        self.task_type = task_type
        self.parent_id = parent_id
        self.council_id = council_id
        self.ministry_name = ministry_name
        self.council_name = council_name
        self.folder_name = folder_name
        self.material_name = material_name
        self.url = url
        self.mat_type = mat_type
        self.dest_dir = dest_dir
        self.suffix_index = suffix_index
        self.preceding_paths = preceding_paths or []

        cleaned = clean_material_name(material_name)
        ext = guess_extension_from_url_or_type(url, mat_type)
        sanitized_base = sanitize_filename(cleaned, max_len=120)
        self.base_name = sanitized_base
        self.ext = ext
        if suffix_index > 1:
            self.filename = f"{sanitized_base}_{suffix_index}{ext}"
        else:
            self.filename = f"{sanitized_base}{ext}"
        self.target_path = dest_dir / self.filename


def create_requests_session() -> requests.Session:
    """Create requests session with robust retries and standard Chrome headers."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 (PMHub-Downloader/2.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    })
    return session


def download_single_task(
    task: MaterialTask,
    session: requests.Session,
    logger: logging.Logger,
    dry_run: bool = False,
    output_base: Path = DEFAULT_OUTPUT_DIR,
) -> Tuple[str, str, Optional[str], Optional[int]]:
    """
    Download or verify a single task.
    Returns: (status, message, local_rel_path, file_size)
    status: 'DOWNLOADED' | 'SKIPPED' | 'FAILED'
    """
    existing_target = resolve_existing_target_path(task.target_path)
    if existing_target:
        rel_path = str(existing_target.relative_to(output_base)).replace("\\", "/")
        size = existing_target.stat().st_size
        return "SKIPPED", f"Already exists: {existing_target.name}", rel_path, size

    if dry_run:
        rel_path = str(task.target_path.relative_to(output_base)).replace("\\", "/")
        return "DOWNLOADED", f"[DRY-RUN] Would download: {task.url} -> {task.target_path.name}", rel_path, 0

    task.dest_dir.mkdir(parents=True, exist_ok=True)
    temp_path = task.target_path.with_name(f"{task.target_path.name}.tmp_{os.getpid()}_{int(time.time()*1000)%10000}")

    try:
        with session.get(task.url, stream=True, timeout=35) as response:
            response.raise_for_status()

            # Content-Type fallback check
            content_type = response.headers.get("Content-Type", "").lower()
            current_ext = task.target_path.suffix.lower()
            if current_ext == ".pdf" and "text/html" in content_type:
                task.target_path = task.target_path.with_suffix(".html")

            total_size = 0
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)

            if total_size == 0:
                safe_unlink(temp_path)
                return "FAILED", f"Downloaded 0 bytes from {task.url}", None, 0

            # If auto-numbered duplicate (_2, _3, ...), check if content matches preceding files
            if task.suffix_index > 1 and task.preceding_paths:
                for cand_path in task.preceding_paths:
                    existing_cand = resolve_existing_target_path(cand_path)
                    if existing_cand and files_are_identical(temp_path, existing_cand, total_size):
                        safe_unlink(temp_path)
                        rel_path = str(existing_cand.relative_to(output_base)).replace("\\", "/")
                        return "SKIPPED", f"Identical to {existing_cand.name} (Duplicate avoided): {task.filename}", rel_path, total_size

            # Move temp to final target
            if task.target_path.exists():
                safe_unlink(task.target_path)
            temp_path.rename(task.target_path)

        rel_path = str(task.target_path.relative_to(output_base)).replace("\\", "/")
        return "DOWNLOADED", f"Saved ({total_size / 1024:.1f} KB): {task.target_path.name}", rel_path, total_size

    except Exception as e:
        safe_unlink(temp_path)
        return "FAILED", f"Error downloading {task.url}: {e}", None, 0


def process_ministry_queue(
    ministry_name: str,
    tasks: List[MaterialTask],
    logger: logging.Logger,
    delay_seconds: float,
    dry_run: bool,
    output_base: Path,
) -> Tuple[Dict[str, int], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Process all tasks for a specific ministry sequentially with delay."""
    session = create_requests_session()
    stats = {"downloaded": 0, "skipped": 0, "failed": 0}
    meeting_db_updates = []
    council_db_updates = []

    logger.info(f"[{ministry_name}] Starting queue ({len(tasks)} items)")

    for i, task in enumerate(tasks, 1):
        status, msg, rel_path, fsize = download_single_task(
            task=task,
            session=session,
            logger=logger,
            dry_run=dry_run,
            output_base=output_base,
        )

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "url": task.url,
            "local_path": rel_path,
            "download_status": "downloaded" if status in ("DOWNLOADED", "SKIPPED") and rel_path else ("failed" if status == "FAILED" else "pending"),
            "file_size": fsize,
            "downloaded_at": now_str if status == "DOWNLOADED" else None
        }

        if task.task_type == "meeting":
            record["meeting_id"] = task.parent_id
            meeting_db_updates.append(record)
        else:
            record["council_id"] = task.parent_id
            council_db_updates.append(record)

        if status == "DOWNLOADED":
            stats["downloaded"] += 1
            logger.info(f"[{ministry_name}] [{i}/{len(tasks)}] [OK] {msg}")
        elif status == "SKIPPED":
            stats["skipped"] += 1
            logger.debug(f"[{ministry_name}] [{i}/{len(tasks)}] [SKIP] {msg}")
        else:
            stats["failed"] += 1
            logger.warning(f"[{ministry_name}] [{i}/{len(tasks)}] [FAIL] {msg}")

        if status != "SKIPPED" and i < len(tasks) and not dry_run:
            time.sleep(delay_seconds)

    logger.info(
        f"[{ministry_name}] Finished: {stats['downloaded']} downloaded, "
        f"{stats['skipped']} skipped, {stats['failed']} failed"
    )
    return stats, meeting_db_updates, council_db_updates


def download_materials(
    council_ids: Optional[List[str]] = None,
    meeting_ids: Optional[List[str]] = None,
    workers: int = 4,
    delay: float = 1.0,
    dry_run: bool = False,
    update_db: bool = True,
    output_base: Path = DEFAULT_OUTPUT_DIR,
    db_path: Path = DEFAULT_DB_PATH,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """
    Main entry point for downloading materials.
    Can be called directly from crawler.py, server.py, or CLI.
    """
    if logger is None:
        logger = setup_logger("downloader")

    logger.info(f"Loading data from database: {db_path}...")
    data = load_data_from_db(db_path)
    if not data or not data.get("councils"):
        logger.warning("No data found in database, falling back to data.json...")
        if DEFAULT_DATA_JSON.exists():
            with open(DEFAULT_DATA_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            logger.error("No data available to download.")
            return {"downloaded": 0, "skipped": 0, "failed": 0, "total": 0}

    ministries_dict = data.get("ministries", {})
    councils_dict = {c["id"]: c for c in data.get("councils", []) if "id" in c}
    meetings = data.get("meetings", [])

    target_council_set = set(council_ids) if council_ids else None
    target_meeting_set = set(meeting_ids) if meeting_ids else None

    # Step 1: Collect valid meeting folders to avoid moving active files
    valid_council_folders: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    for m in meetings:
        cid = m.get("councilId", "")
        c_info = councils_dict.get(cid, {})
        min_code = m.get("ministry") or c_info.get("ministry") or "UNKNOWN"
        min_name = ministries_dict.get(min_code, {}).get("name") or min_code
        c_name = c_info.get("name") or m.get("councilName") or "会議体不明"
        m_folder = format_meeting_folder_name(m, c_name)
        valid_council_folders[(min_name, c_name)].add(m_folder)

    # Step 2: Build tasks grouped by ministry
    tasks_by_ministry: Dict[str, List[MaterialTask]] = defaultdict(list)
    total_tasks = 0

    # 2-A: Council permanent materials (00_会議体資料)
    for c in data.get("councils", []):
        cid = c.get("id", "")
        if target_council_set and cid not in target_council_set:
            continue

        min_code = c.get("ministry", "UNKNOWN")
        min_name = ministries_dict.get(min_code, {}).get("name") or min_code
        c_name = c.get("name") or "会議体不明"
        council_dir = get_council_materials_dir(output_base, min_name, c_name)

        seen_urls = set()
        name_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        preceding_paths_map: Dict[str, List[Path]] = defaultdict(list)

        for mat in c.get("materials", []):
            url = (mat.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            mat_name = mat.get("name", "資料")
            mat_type = mat.get("type")
            cleaned = clean_material_name(mat_name)
            ext = guess_extension_from_url_or_type(url, mat_type)
            s_base = sanitize_filename(cleaned, max_len=120)

            name_counts[(s_base, ext)] += 1
            idx = name_counts[(s_base, ext)]
            precedings = list(preceding_paths_map[(s_base, ext)])

            task = MaterialTask(
                task_type="council",
                parent_id=cid,
                council_id=cid,
                ministry_name=min_name,
                council_name=c_name,
                folder_name=COUNCIL_MATERIALS_FOLDER,
                material_name=mat_name,
                url=url,
                mat_type=mat_type,
                dest_dir=council_dir,
                suffix_index=idx,
                preceding_paths=precedings,
            )
            preceding_paths_map[(s_base, ext)].append(task.target_path)
            tasks_by_ministry[min_name].append(task)
            total_tasks += 1

    # 2-B: Meeting materials
    for m in meetings:
        mid = m.get("id", "")
        cid = m.get("councilId", "")
        if target_meeting_set and mid not in target_meeting_set:
            continue
        if target_council_set and cid not in target_council_set:
            continue

        c_info = councils_dict.get(cid, {})
        min_code = m.get("ministry") or c_info.get("ministry") or "UNKNOWN"
        min_name = ministries_dict.get(min_code, {}).get("name") or min_code
        c_name = c_info.get("name") or m.get("councilName") or "会議体不明"
        meeting_dir = get_meeting_dir(output_base, min_name, c_name, m)
        m_folder = format_meeting_folder_name(m, c_name)

        seen_urls = set()
        name_counts = defaultdict(int)
        preceding_paths_map = defaultdict(list)

        for mat in m.get("materials", []):
            url = (mat.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            mat_name = mat.get("name", "資料")
            mat_type = mat.get("type")
            cleaned = clean_material_name(mat_name)
            ext = guess_extension_from_url_or_type(url, mat_type)
            s_base = sanitize_filename(cleaned, max_len=120)

            name_counts[(s_base, ext)] += 1
            idx = name_counts[(s_base, ext)]
            precedings = list(preceding_paths_map[(s_base, ext)])

            task = MaterialTask(
                task_type="meeting",
                parent_id=mid,
                council_id=cid,
                ministry_name=min_name,
                council_name=c_name,
                folder_name=m_folder,
                material_name=mat_name,
                url=url,
                mat_type=mat_type,
                dest_dir=meeting_dir,
                suffix_index=idx,
                preceding_paths=precedings,
            )
            preceding_paths_map[(s_base, ext)].append(task.target_path)

            # Check for existing file migration if target path does not exist
            if not resolve_existing_target_path(task.target_path):
                council_parent_dir = meeting_dir.parent
                valid_folders = valid_council_folders.get((min_name, c_name), set())
                # Search obsolete folders in same council directory
                if council_parent_dir.exists():
                    try:
                        for entry in os.scandir(council_parent_dir):
                            if not entry.is_dir() or entry.name == m_folder or entry.name == COUNCIL_MATERIALS_FOLDER or entry.name.startswith((".", "_")):
                                continue
                            if entry.name not in valid_folders:
                                old_cand = Path(entry.path) / task.filename
                                old_existing = resolve_existing_target_path(old_cand)
                                if old_existing:
                                    safe_move_file(old_existing, task.target_path)
                                    logger.info(f"[MIGRATED] Moved existing file: {old_existing} -> {task.target_path}")
                                    break
                    except OSError:
                        pass

            tasks_by_ministry[min_name].append(task)
            total_tasks += 1

    logger.info(f"Constructed {total_tasks} tasks across {len(tasks_by_ministry)} ministries.")
    overall_stats = {"downloaded": 0, "skipped": 0, "failed": 0, "total": total_tasks}
    all_meeting_updates = []
    all_council_updates = []

    # Step 3: Run multi-ministry parallel workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                process_ministry_queue,
                min_name,
                t_list,
                logger,
                delay,
                dry_run,
                output_base,
            ): min_name
            for min_name, t_list in tasks_by_ministry.items()
        }

        for fut in concurrent.futures.as_completed(futures):
            min_name = futures[fut]
            try:
                m_stats, m_meeting_updates, m_council_updates = fut.result()
                overall_stats["downloaded"] += m_stats["downloaded"]
                overall_stats["skipped"] += m_stats["skipped"]
                overall_stats["failed"] += m_stats["failed"]
                all_meeting_updates.extend(m_meeting_updates)
                all_council_updates.extend(m_council_updates)
            except Exception as e:
                logger.error(f"Worker for ministry '{min_name}' raised unhandled exception: {e}")

    # Step 4: Batch update SQLite database
    if update_db and not dry_run:
        logger.info(f"Syncing download status to database ({len(all_meeting_updates)} meeting materials, {len(all_council_updates)} council materials)...")
        update_materials_download_batch(all_meeting_updates, db_path=db_path)
        update_council_materials_download_batch(all_council_updates, db_path=db_path)

    logger.info(
        f"All tasks completed: {overall_stats['downloaded']} downloaded, "
        f"{overall_stats['skipped']} skipped, {overall_stats['failed']} failed (Total: {overall_stats['total']})"
    )
    return overall_stats


def main():
    parser = argparse.ArgumentParser(description="PMHub Materials Downloader (PMM)")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent ministry workers (default: 4)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests to same ministry (default: 1.0s)")
    parser.add_argument("--council-id", type=str, default=None, help="Filter to a specific councilId")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry-run without writing files")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Output directory path")
    args = parser.parse_args()

    c_ids = [args.council_id] if args.council_id else None
    download_materials(
        council_ids=c_ids,
        workers=args.workers,
        delay=args.delay,
        dry_run=args.dry_run,
        output_base=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
