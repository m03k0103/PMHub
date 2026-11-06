#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMHub Git Hooks Setup Utility (setup_git_hooks.py)
==================================================
Sets up Git hooks to automatically synchronize the local SQLite master DB
(admin/pmhub.db) whenever 'git pull' brings in updated JSON datasets.
"""

import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows CP932
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent.parent
GIT_HOOKS_DIR = BASE_DIR / ".git" / "hooks"
POST_MERGE_HOOK = GIT_HOOKS_DIR / "post-merge"


def install_post_merge_hook():
    """Install post-merge hook into .git/hooks/."""
    if not GIT_HOOKS_DIR.parent.exists():
        print("⚠️ [WARNING] Not a git repository (.git folder not found).", file=sys.stderr)
        return False

    GIT_HOOKS_DIR.mkdir(parents=True, exist_ok=True)

    hook_content = """#!/bin/sh
# PMHub post-merge hook
# Automatically synchronize SQLite master DB when JSON datasets are updated via git pull

echo ""
echo "=================================================="
echo " [PMHub Hook] Synchronizing SQLite master DB..."
echo "=================================================="

# Check if JSON files changed in this merge
CHANGED_JSON=$(git diff-tree -r --name-only --no-commit-id ORIG_HEAD HEAD | grep -E '^(docs/data.*\\.json|admin/admin_data\\.json)')

if [ -n "$CHANGED_JSON" ]; then
    echo "Changes detected in JSON datasets:"
    echo "$CHANGED_JSON"
    echo ""
    python admin/db/sync_from_json.py
    echo "=================================================="
else
    echo "No JSON dataset changes detected. Skipping DB sync."
    echo "=================================================="
fi
"""

    with open(POST_MERGE_HOOK, "w", encoding="utf-8", newline="\n") as f:
        f.write(hook_content)

    # Make executable on Unix-like systems
    try:
        current_mode = os.stat(POST_MERGE_HOOK).st_mode
        os.chmod(POST_MERGE_HOOK, current_mode | 0o755)
    except Exception:
        pass

    print(f"✅ [SUCCESS] Git post-merge hook installed successfully: {POST_MERGE_HOOK}")
    print("   Now 'git pull' will automatically synchronize admin/pmhub.db whenever JSON datasets change!")
    return True


if __name__ == "__main__":
    install_post_merge_hook()
