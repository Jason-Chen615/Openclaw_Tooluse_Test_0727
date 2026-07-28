#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QwenPaw native memory reset — wipe ReMe Light memory subdirs between runs.

Locates the agent workspace and removes the ReMe Light memory subdirectories
(memory/ digest/ mem_metadata/ mem_session/ mem_agent/ resource/) so each
bench case starts from a clean memory state.

Safety: only deletes directories located UNDER the resolved WORKING_DIR.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional


# ReMe Light memory subdir defaults (config.py ReMeLightMemoryConfig).
DEFAULT_MEMORY_SUBDIRS = {
    "daily_dir": "memory",
    "digest_dir": "digest",
    "metadata_dir": "mem_metadata",
    "session_dir": "mem_session",
    "mem_session_dir": "mem_agent",
    "resource_dir": "resource",
}


def resolve_working_dir(explicit: Optional[str] = None) -> Path:
    """Resolve QwenPaw WORKING_DIR.

    Priority:
      1. explicit --working-dir
      2. QWENPAW_WORKING_DIR / COPAW_WORKING_DIR env var
      3. ~/.copaw (legacy) if it exists
      4. ~/.qwenpaw
    """
    if explicit:
        return Path(explicit).expanduser().resolve()
    for env_var in ("QWENPAW_WORKING_DIR", "COPAW_WORKING_DIR"):
        val = os.environ.get(env_var)
        if val:
            return Path(val).expanduser().resolve()
    legacy = Path("~/.copaw").expanduser()
    if legacy.exists():
        return legacy.resolve()
    return Path("~/.qwenpaw").expanduser().resolve()


def resolve_agent_workspace(working_dir: Path, agent: str) -> Path:
    """Resolve the agent workspace dir.

    Default layout: <WORKING_DIR>/workspaces/<agent>.
    """
    return (working_dir / "workspaces" / agent).resolve()


def load_memory_subdir_names(workspace_dir: Path) -> Dict[str, str]:
    """Read subdir overrides from agent.json, fall back to defaults."""
    names = dict(DEFAULT_MEMORY_SUBDIRS)
    agent_json = workspace_dir / "agent.json"
    if not agent_json.exists():
        return names
    try:
        with open(agent_json, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        reme_cfg = (
            cfg.get("running", {})
            .get("reme_light_memory_config", {})
        )
        for key in names:
            if key in reme_cfg and isinstance(reme_cfg[key], str) and reme_cfg[key].strip():
                names[key] = reme_cfg[key].strip()
    except Exception as e:
        print(f"[reset-memory] WARN: failed to read agent.json ({e}); using defaults", file=sys.stderr)
    return names


def ensure_within(target: Path, base: Path) -> None:
    """Raise if target is not under base (path-traversal safety)."""
    try:
        target.resolve().relative_to(base.resolve())
    except ValueError:
        raise ValueError(
            f"Refusing to delete '{target}': not under WORKING_DIR '{base}'"
        )


def reset_memory(
    agent: str,
    working_dir: Optional[str] = None,
    dry_run: bool = False,
) -> List[str]:
    """Remove ReMe Light memory subdirs for the given agent.

    Returns the list of removed (or would-be-removed) directory paths.
    """
    wd = resolve_working_dir(working_dir)
    workspace = resolve_agent_workspace(wd, agent)

    if not workspace.exists():
        print(f"[reset-memory] workspace not found: {workspace}", file=sys.stderr)
        return []

    subdir_names = load_memory_subdir_names(workspace)
    removed: List[str] = []

    for key, subdir in subdir_names.items():
        target = workspace / subdir
        if not target.exists():
            continue
        # Safety: must be under WORKING_DIR.
        ensure_within(target, wd)
        if dry_run:
            print(f"[reset-memory] (dry-run) would remove: {target}")
            removed.append(str(target))
            continue
        try:
            shutil.rmtree(target)
            print(f"[reset-memory] removed: {target}")
            removed.append(str(target))
        except OSError as e:
            print(f"[reset-memory] ERROR removing {target}: {e}", file=sys.stderr)

    if not removed:
        print(f"[reset-memory] nothing to remove under {workspace}")

    return removed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset QwenPaw native (ReMe Light) memory for an agent"
    )
    parser.add_argument("--agent", default="default", help="QwenPaw agent ID")
    parser.add_argument(
        "--working-dir",
        help="QwenPaw WORKING_DIR (or use QWENPAW_WORKING_DIR env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without deleting",
    )
    args = parser.parse_args()

    reset_memory(
        agent=args.agent,
        working_dir=args.working_dir,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
