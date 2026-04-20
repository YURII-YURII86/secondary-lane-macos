from __future__ import annotations

import os
import sys
from pathlib import Path

from macos_bundle.payload import sync_payload


def resource_root() -> Path:
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parents[1]


def default_install_dir() -> Path:
    custom = os.environ.get("SECOND_LANE_INSTALL_TARGET_DIR", "").strip()
    if custom:
        return Path(custom).expanduser().resolve()
    return (Path.home() / "Applications" / "Second Lane").resolve()


def prepare_project_dir() -> Path:
    source_payload = resource_root() / "payload"
    install_dir = default_install_dir()
    sync_payload(source_payload, install_dir)
    return install_dir


def main() -> None:
    project_dir = prepare_project_dir()
    os.environ["SECOND_LANE_PROJECT_DIR"] = str(project_dir)
    if os.environ.get("SECOND_LANE_BUNDLED_ENTRY_SMOKE") == "1":
        print(f"BUNDLE-SMOKE-OK:{project_dir}")
        return
    from second_lane_installer import main as installer_main

    installer_main()


if __name__ == "__main__":
    main()
