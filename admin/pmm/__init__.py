# -*- coding: utf-8 -*-
"""
PMHub Materials Manager (PMM) Package
====================================
Local materials download, organization, normalization, and deduplication for PMHub.
"""

from .pmm_common import (
    DEFAULT_OUTPUT_DIR,
    COUNCIL_MATERIALS_FOLDER,
    clean_material_name,
    sanitize_filename,
    format_meeting_folder_name,
    guess_extension_from_url_or_type,
    files_are_identical,
    safe_unlink,
    safe_rmdir,
    safe_move_file,
    safe_rmtree,
)
