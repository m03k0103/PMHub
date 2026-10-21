# -*- coding: utf-8 -*-
"""
PMM Common Utilities & Domain Rules (admin/pmm/pmm_common.py)
=============================================================
Centralizes path resolution, filename sanitization, meeting folder naming,
Windows NTFS resilient file operations, and logging across PMHub Materials Manager tools.
"""

import logging
import os
import re
import shutil
import stat
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure standard UTF-8 stream handling on Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_DIR = BASE_DIR / "local_docs"
DEFAULT_DATA_JSON = BASE_DIR / "docs" / "data.json"
DEFAULT_DB_PATH = BASE_DIR / "admin" / "pmhub.db"
DEFAULT_LOG_DIR = BASE_DIR / "admin" / "logs"

# Standard folder name for council permanent materials (名簿・設置根拠等)
COUNCIL_MATERIALS_FOLDER = "00_会議体資料"


def setup_logger(tool_name: str, log_dir: Optional[Path] = None) -> logging.Logger:
    """Setup dual logging to console and execution-unique log file in admin/logs/."""
    target_dir = log_dir or DEFAULT_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = target_dir / f"{tool_name}_{now_str}.log"

    idx = 1
    while log_file.exists():
        log_file = target_dir / f"{tool_name}_{now_str}_{idx}.log"
        idx += 1

    logger = logging.getLogger(f"PMM_{tool_name}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # Console Handler
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.INFO)
    c_format = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

    # File Handler
    f_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    f_handler.setLevel(logging.DEBUG)
    f_format = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s")
    f_handler.setFormatter(f_format)
    logger.addHandler(f_handler)

    return logger


def sanitize_filename(name: str, max_len: int = 150) -> str:
    """Sanitize string for Windows filename replacing invalid characters with full-width equivalents."""
    if not name:
        return "untitled"
    replacements = {
        '\\': '￥',
        '/': '／',
        ':': '：',
        '*': '＊',
        '?': '？',
        '"': '”',
        '<': '＜',
        '>': '＞',
        '|': '｜',
    }
    for char, rep in replacements.items():
        name = name.replace(char, rep)

    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    name = name.strip(" .")
    if len(name) > max_len:
        name = name[:max_len].rstrip(" .")
    return name if name else "untitled"


def clean_material_name(raw_name: str) -> str:
    """Remove file type and size indicators (e.g. '(PDF : 190KB)', '[PDF 1.2MB]') from material name."""
    if not raw_name:
        return "資料"

    name = raw_name
    open_b = r'[\(（\[［【〔〈《]'
    close_b = r'[\)）\]］】〕〉》]'
    bracket_patterns = [
        rf'{open_b}\s*(?:PDF|HTML|DOC|DOCX|XLS|XLSX|PPT|PPTX|ZIP|TXT)?\s*(?:形式|ファイル|版)?\s*[:：／/・\s-]?\s*(?:[\d,]+(?:\.\d+)?\s*(?:KB|MB|GB|B|キロバイト|メガバイト|バイト))?\s*{close_b}',
        rf'{open_b}\s*[\d,]+(?:\.\d+)?\s*(?:KB|MB|GB|B|キロバイト|メガバイト|バイト)\s*{close_b}',
        r'[-－–]\s*(?:PDF|HTML|DOC|DOCX|XLS|XLSX|PPT|PPTX|ZIP)\s*(?:[\d,]+(?:\.\d+)?\s*(?:KB|MB|GB|B))?$',
    ]

    for pat in bracket_patterns:
        name = re.sub(pat, '', name, flags=re.IGNORECASE)

    name = re.sub(r'[\s\u3000]+', ' ', name).strip()
    return name if name else "資料"


def format_meeting_folder_name(meeting: Dict[str, Any], council_name: str) -> str:
    """
    Generate meeting folder name:
    meetings.date(yyyymmdd) + meetings.name without council_name and unnecessary spaces.
    e.g.: "20251213_第16回"
    """
    raw_date = meeting.get("date", "") or ""
    digits_date = re.sub(r'[^0-9]', '', raw_date)
    if len(digits_date) >= 8:
        date_str = digits_date[:8]
    elif digits_date:
        date_str = digits_date
    else:
        date_str = "00000000"

    meeting_name = meeting.get("name", "") or ""
    cleaned_title = meeting_name
    if council_name:
        cleaned_title = cleaned_title.replace(council_name, "")

    cleaned_title = re.sub(r'[\s\u3000]+', '', cleaned_title)
    cleaned_title = cleaned_title.strip("-_・")

    if cleaned_title:
        folder_name = f"{date_str}_{cleaned_title}"
    else:
        folder_name = date_str

    return sanitize_filename(folder_name, max_len=100)


def guess_extension_from_url_or_type(url: str, mat_type: Optional[str] = None) -> str:
    """Determine file extension from URL, material type, or fallback to .pdf."""
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        _, ext = os.path.splitext(path)
        ext = ext.lower()
        if ext in [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".zip", ".html", ".htm", ".txt", ".csv"]:
            return ext
    except Exception:
        pass

    if mat_type:
        mtype = mat_type.upper()
        if "HTML" in mtype:
            return ".html"
        if "PDF" in mtype:
            return ".pdf"
        if "EXCEL" in mtype or "XLS" in mtype:
            return ".xlsx"
        if "WORD" in mtype or "DOC" in mtype:
            return ".docx"
        if "ZIP" in mtype:
            return ".zip"

    return ".pdf"


def get_council_materials_dir(output_dir: Path, ministry_name: str, council_name: str) -> Path:
    """Return directory path for council permanent materials (00_会議体資料)."""
    min_name_sanitized = sanitize_filename(ministry_name, max_len=60)
    c_name_sanitized = sanitize_filename(council_name, max_len=80)
    return (output_dir / min_name_sanitized / c_name_sanitized / COUNCIL_MATERIALS_FOLDER).resolve()


def get_meeting_dir(output_dir: Path, ministry_name: str, council_name: str, meeting: Dict[str, Any]) -> Path:
    """Return directory path for meeting materials."""
    min_name_sanitized = sanitize_filename(ministry_name, max_len=60)
    c_name_sanitized = sanitize_filename(council_name, max_len=80)
    m_folder = format_meeting_folder_name(meeting, council_name)
    return (output_dir / min_name_sanitized / c_name_sanitized / m_folder).resolve()


def files_are_identical(path1: Path, path2: Path, size: Optional[int] = None) -> bool:
    """Fast binary comparison: size check, head/tail 64KB check, and stream check only if needed."""
    try:
        if size is None:
            size1 = path1.stat().st_size
            size2 = path2.stat().st_size
            if size1 != size2:
                return False
            size = size1

        if size == 0:
            return True

        if size <= 1024 * 1024:
            with open(path1, "rb") as f1, open(path2, "rb") as f2:
                return f1.read() == f2.read()

        with open(path1, "rb") as f1, open(path2, "rb") as f2:
            if f1.read(65536) != f2.read(65536):
                return False
            f1.seek(max(0, size - 65536))
            f2.seek(max(0, size - 65536))
            if f1.read(65536) != f2.read(65536):
                return False
            f1.seek(65536)
            f2.seek(65536)
            while chunk1 := f1.read(65536):
                chunk2 = f2.read(65536)
                if chunk1 != chunk2:
                    return False
        return True
    except Exception:
        return False


def safe_unlink(p: Path) -> bool:
    """Safely unlink a file with Windows NTFS ReadOnly attribute removal and kernel fallback."""
    try:
        if not p.exists():
            return True
        try:
            os.chmod(p, stat.S_IWRITE)
        except OSError:
            pass
        p.unlink()
        return True
    except OSError:
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)  # FILE_ATTRIBUTE_NORMAL
            p.unlink()
            return True
        except OSError:
            return False


def safe_rmdir(p: Path) -> bool:
    """Safely remove an empty directory with Windows NTFS ReadOnly attribute removal."""
    try:
        if not p.exists():
            return True
        try:
            os.chmod(p, stat.S_IWRITE)
        except OSError:
            pass
        p.rmdir()
        return True
    except OSError:
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)  # FILE_ATTRIBUTE_NORMAL
            p.rmdir()
            return True
        except OSError:
            return False


def safe_move_file(src: Path, dst: Path) -> bool:
    """Move file with retry and copy+delete fallback to handle Windows file locking."""
    try:
        if not src.exists():
            return False
        try:
            os.chmod(src, stat.S_IWRITE)
        except OSError:
            pass
        for attempt in range(5):
            try:
                shutil.move(str(src), str(dst))
                return True
            except OSError:
                time.sleep(0.05 * (2 ** attempt))

        # Fallback: copy2 and safe unlink
        shutil.copy2(str(src), str(dst))
        safe_unlink(src)
        return True
    except Exception:
        return False


def safe_rmtree(p: Path) -> bool:
    """Safely remove directory tree handling ReadOnly files."""
    def _on_error(func, path, exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    try:
        if not p.exists():
            return True
        shutil.rmtree(str(p), onerror=_on_error)
        return not p.exists()
    except Exception:
        return False
