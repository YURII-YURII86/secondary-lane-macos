from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import second_lane_installer as installer


class _Completed:
    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


class _Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value


def test_download_file_writes_through_partial(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "ngrok.zip"

    def fake_run(argv: list[str], **_kwargs) -> _Completed:
        partial = Path(argv[argv.index("-o") + 1])
        partial.write_bytes(b"zip-data")
        return _Completed()

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    installer.download_file("https://example.test/ngrok.zip", target, timeout=1)

    assert target.read_bytes() == b"zip-data"
    assert not target.with_suffix(".zip.partial").exists()


def test_download_file_removes_partial_after_failed_curl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "ngrok.zip"

    def fake_run(argv: list[str], **_kwargs) -> _Completed:
        partial = Path(argv[argv.index("-o") + 1])
        partial.write_bytes(b"broken")
        return _Completed(returncode=28, stdout="curl: (28) Operation too slow")

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    with pytest.raises(installer.StepFailed):
        installer.download_file("https://example.test/ngrok.zip", target, timeout=1)

    assert not target.exists()
    assert not target.with_suffix(".zip.partial").exists()


def test_find_ngrok_ignores_unusable_manual_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bad_ngrok = tmp_path / "ngrok"
    bad_ngrok.write_text("not-ngrok", "utf-8")
    app = installer.InstallerApp.__new__(installer.InstallerApp)
    app.ngrok_path_var = _Var(str(bad_ngrok))

    monkeypatch.setattr(installer, "LOCAL_NGROK_BIN", tmp_path / "missing-local-ngrok")
    monkeypatch.setattr(installer.shutil, "which", lambda _name: "")
    monkeypatch.setattr(app, "_ngrok_binary_is_usable", lambda _path: (False, "bad"))

    assert app._find_ngrok_bin() is None


def test_manual_ngrok_rejects_zip(tmp_path: Path) -> None:
    app = installer.InstallerApp.__new__(installer.InstallerApp)
    archive = tmp_path / "ngrok.zip"
    archive.write_bytes(b"zip")

    with pytest.raises(installer.StepFailed, match="zip"):
        app._install_manual_ngrok(archive)


def test_control_panel_does_not_recover_unknown_ngrok_startup_crash() -> None:
    import gpts_agent_control as control

    panel = control.ControlPanel.__new__(control.ControlPanel)
    failure = panel._classify_ngrok_output("ERROR: something unexpected")

    assert failure.code == "startup_crashed"
    assert not failure.recoverable


def test_control_panel_uses_domain_flag_for_older_ngrok_help(monkeypatch: pytest.MonkeyPatch) -> None:
    import gpts_agent_control as control

    class _Help:
        returncode = 0
        stdout = "Usage: ngrok http [address] [--domain string]"

    monkeypatch.setattr(control.subprocess, "run", lambda *args, **kwargs: _Help())

    panel = control.ControlPanel.__new__(control.ControlPanel)

    assert panel._ngrok_domain_arg("ngrok", "demo.ngrok-free.app") == "--domain=demo.ngrok-free.app"
