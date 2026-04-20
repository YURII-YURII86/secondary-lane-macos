from __future__ import annotations

import os
from pathlib import Path


PROJECT_DIR_ENV = "SECOND_LANE_PROJECT_DIR"


def resolve_project_dir(anchor_file: str, parent_levels: int = 0) -> Path:
    override = os.environ.get(PROJECT_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(anchor_file).resolve().parents[parent_levels]
