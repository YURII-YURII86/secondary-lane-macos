from __future__ import annotations

import shutil
from pathlib import Path


PAYLOAD_ITEMS = (
    ".env.example",
    "AUTHORS",
    "CHANGELOG.md",
    "CONNECT_GPT_ACTIONS_RU.md",
    "LICENSE",
    "NOTICE",
    "README.md",
    "SECURITY.md",
    "openapi.gpts.yaml",
    "requirements.txt",
    "Запустить Second Lane.command",
    "gpts_agent_control.py",
    "second_lane_installer.py",
    "ui_brand.py",
    "runtime_paths.py",
    "app",
    "assets",
    "data",
)

MUTABLE_TOP_LEVEL = {
    ".env",
    ".installer_state.json",
    ".venv",
    "tools",
    "workspace",
}

IGNORED_NAMES = {
    ".DS_Store",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def payload_items(project_dir: Path) -> list[Path]:
    out: list[Path] = []
    for item in PAYLOAD_ITEMS:
        candidate = project_dir / item
        if candidate.exists():
            out.append(candidate)
    return out


def _ignore_names(_src: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_NAMES}


def sync_payload(source_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for item in payload_items(source_dir):
        destination = target_dir / item.name
        if item.name in MUTABLE_TOP_LEVEL and destination.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True, ignore=_ignore_names)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)
    launcher = target_dir / "Запустить Second Lane.command"
    if launcher.exists():
        launcher.chmod(0o755)
