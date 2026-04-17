"""Shared helpers for gpts-mac-autopilot skill scripts.

The central helper here is ``find_branch_root`` — every Python script
in this directory needs to locate the Second Lane macOS branch root
regardless of whether the user unpacked the archive into:

  ~/SecondLane/                         (ideal case)
  ~/SecondLane/Версия для Мак/          (original repo layout)
  ~/Downloads/secondary-lane-main/Версия для Мак/
  ~/Projects/secondary-lane-macos/
  …или любую другую комбинацию, включая переименованные папки.

The previous hardcoded [raw_root, raw_root / "Версия для Мак"] pair
bailed out immediately on any of these layouts and left the Codex
skill convinced the project was broken. This helper:

  1. checks a list of common folder names in order of likelihood,
  2. walks up / down a few levels looking for ``.env.example``,
  3. finally delegates to ``discover_secondarylane_layout.py`` which
     does a bounded scored scan with penalties for obvious junk
     paths (``__pycache__``, ``.git``, ``backup``).

Every adaptive miss is logged to stderr with a human-readable hint so
Codex can surface it to the user instead of silently proceeding with
a wrong root.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


# Common folder names under which users extract the macOS branch.
# Ordered most-specific first so a literal match wins over a fuzzy one.
_KNOWN_BRANCH_NAMES = (
    "Версия для Мак",
    "secondary-lane-macos",
    "Secondary-LANE-macOS",
    "SecondaryLANE-macOS",
    "SecondLane",
    "Second Lane",
)

_MARKER = ".env.example"
_SIDE_MARKERS = ("gpts_agent_control.py", "openapi.gpts.yaml")


def _looks_like_branch(candidate: Path) -> bool:
    """A folder is the branch root if it has .env.example AND at
    least one of the side-marker files. Using a single marker alone
    sometimes matches unrelated folders (e.g. a backup ``.env.example``
    in a parent directory)."""
    if not (candidate / _MARKER).exists():
        return False
    return any((candidate / side).exists() for side in _SIDE_MARKERS)


def _log(msg: str) -> None:
    sys.stderr.write(f"[find_branch_root] {msg}\n")


def _walk_known_names(root: Path) -> Path | None:
    for name in _KNOWN_BRANCH_NAMES:
        candidate = root / name
        if _looks_like_branch(candidate):
            return candidate
    return None


def _walk_up(start: Path, max_hops: int = 4) -> Path | None:
    """If the user passed a path inside the branch (e.g. the scripts
    dir), walk up a few levels to find the real root."""
    current = start
    for _ in range(max_hops):
        if _looks_like_branch(current):
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def _walk_down(root: Path, max_depth: int = 4) -> Path | None:
    """Bounded BFS looking for a branch root beneath ``root``. We stop
    at the first marker hit to keep this fast."""
    frontier: list[tuple[Path, int]] = [(root, 0)]
    while frontier:
        current, depth = frontier.pop(0)
        try:
            if _looks_like_branch(current):
                return current
            if depth >= max_depth:
                continue
            for child in current.iterdir():
                if not child.is_dir():
                    continue
                name = child.name
                # Skip obvious junk / sensitive system dirs.
                if name.startswith(".") and name not in (".",):
                    continue
                if name in (
                    "__pycache__", "node_modules", ".venv", "venv",
                    "Library", "Pictures", "Movies", "Music",
                ):
                    continue
                frontier.append((child, depth + 1))
        except (PermissionError, OSError):
            # macOS TCC-protected folders (Downloads, Desktop) and
            # iCloud/Time Machine mounts throw here — skip instead of
            # aborting the whole scan.
            continue
    return None


def _walk_via_layout_script(root: Path) -> Path | None:
    """Last resort: shell out to the dedicated layout discoverer."""
    layout_script = Path(__file__).resolve().parent / "discover_secondarylane_layout.py"
    if not layout_script.exists():
        return None
    try:
        completed = subprocess.run(
            [sys.executable, str(layout_script), str(root), "--max-depth", "5"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    best = payload.get("best_match") or {}
    candidate_root = best.get("candidate_root")
    if not candidate_root:
        return None
    candidate = Path(candidate_root)
    if _looks_like_branch(candidate):
        return candidate
    return None


def find_branch_root(raw_root: Path | str) -> Path:
    """Locate the Second Lane macOS branch root adaptively.

    Order of attempts (each cheaper than the next):
      1. is raw_root itself the branch?
      2. is one of the known-named subfolders the branch?
      3. walk up from raw_root — maybe user pointed at a subdirectory
      4. bounded walk down from raw_root skipping junk folders
      5. hand over to discover_secondarylane_layout.py for a full scan

    Raises ``SystemExit`` with a beginner-friendly message if nothing
    worked — the message names the folder that *was* searched so the
    user can double-check they unzipped the right archive.
    """
    if raw_root is None:
        raise SystemExit("find_branch_root: project_root argument is empty.")
    root = Path(raw_root).expanduser().resolve()

    if _looks_like_branch(root):
        return root

    found = _walk_known_names(root)
    if found is not None:
        _log(f"matched known branch folder name under {root}: {found.name}")
        return found

    found = _walk_up(root)
    if found is not None:
        _log(f"walked up from {root} to branch root: {found}")
        return found

    found = _walk_down(root)
    if found is not None:
        _log(f"walked down from {root} to branch root: {found}")
        return found

    found = _walk_via_layout_script(root)
    if found is not None:
        _log(f"layout script picked branch root: {found}")
        return found

    raise SystemExit(
        "Could not find the macOS project branch root.\n"
        f"  Searched under: {root}\n"
        f"  Looked for: {_MARKER} together with one of {_SIDE_MARKERS}\n"
        "  Checked known folder names: " + ", ".join(_KNOWN_BRANCH_NAMES) + "\n"
        "  Also ran discover_secondarylane_layout.py as a fallback.\n"
        "\n"
        "Fix: make sure you unpacked the Second Lane archive, and that\n"
        "the path you passed either IS the macOS branch folder or a\n"
        "folder that directly contains it."
    )


__version__ = "1.0.0"
