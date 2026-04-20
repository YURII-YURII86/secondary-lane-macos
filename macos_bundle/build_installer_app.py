from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from PyInstaller.__main__ import run as pyinstaller_run

from macos_bundle.payload import sync_payload

BUILD_ROOT = PROJECT_DIR / "build" / "bundled-installer"
DIST_ROOT = PROJECT_DIR / "dist"
APP_NAME = "Second Lane Installer"


def build() -> Path:
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="second-lane-payload-") as tmp_dir:
        payload_dir = Path(tmp_dir) / "payload"
        sync_payload(PROJECT_DIR, payload_dir)

        args = [
            "--noconfirm",
            "--clean",
            "--windowed",
            "--name",
            APP_NAME,
            "--target-arch",
            "universal2",
            "--distpath",
            str(DIST_ROOT),
            "--workpath",
            str(BUILD_ROOT / "work"),
            "--specpath",
            str(BUILD_ROOT / "spec"),
            "--paths",
            str(PROJECT_DIR),
            "--hidden-import",
            "_tkinter",
            "--hidden-import",
            "tkinter",
            "--hidden-import",
            "tkinter.ttk",
            "--hidden-import",
            "tkinter.scrolledtext",
            "--hidden-import",
            "tkinter.filedialog",
            "--hidden-import",
            "tkinter.messagebox",
            "--hidden-import",
            "tkinter.font",
            "--add-data",
            f"{payload_dir}:payload",
            str(PROJECT_DIR / "macos_bundle" / "bundled_installer_entry.py"),
        ]
        pyinstaller_run(args)

    return DIST_ROOT / f"{APP_NAME}.app"


if __name__ == "__main__":
    app_path = build()
    print(app_path)
