#!/usr/bin/env python3.13
from __future__ import annotations

import ast
import json
import os
import queue
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import gpts_agent_control as gac
import second_lane_installer as sli
from app.core import config as runtime_config


class DummyVar:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class DummyEntry:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.cursor = len(text)
        self.selection: tuple[int, int] | None = None

    def bind(self, *_args, **_kwargs) -> None:
        return None

    def index(self, key: str) -> int:
        if key == "insert":
            return self.cursor
        if key == "sel.first" and self.selection:
            return self.selection[0]
        if key == "sel.last" and self.selection:
            return self.selection[1]
        raise sli.tk.TclError()

    def delete(self, start: int, end: int) -> None:
        self.text = self.text[:start] + self.text[end:]
        self.cursor = start
        self.selection = None

    def insert(self, index: int, value: str) -> None:
        self.text = self.text[:index] + value + self.text[index:]
        self.cursor = index + len(value)
        self.selection = None

    def icursor(self, index: int) -> None:
        self.cursor = len(self.text) if index == sli.END else index

    def focus_set(self) -> None:
        return None

    def selection_get(self) -> str:
        if not self.selection:
            raise sli.tk.TclError()
        start, end = self.selection
        return self.text[start:end]

    def selection_range(self, start: int, end) -> None:
        end_index = len(self.text) if end == sli.END else int(end)
        self.selection = (start, end_index)


def make_headless_app() -> sli.InstallerApp:
    app = sli.InstallerApp.__new__(sli.InstallerApp)
    app.worker_queue = queue.Queue()
    app.current_step_index = 0
    app.step_status = {step.key: "pending" for step in sli.STEP_SPECS}
    app.ngrok_domain_var = DummyVar("")
    app.ngrok_token_var = DummyVar("")
    app.workspace_root_var = DummyVar("")
    app.busy = False
    return app


def drain_events(app: sli.InstallerApp) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    while True:
        try:
            out.append(app.worker_queue.get_nowait())
        except queue.Empty:
            break
    return out


class InstallerSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = self.root / ".env"
        self.env_example = self.root / ".env.example"
        self.state = self.root / ".installer_state.json"
        self.venv = self.root / ".venv"
        self.tools = self.root / "tools"
        self.local_ngrok = self.tools / "ngrok" / "ngrok"
        self.req = self.root / "requirements.txt"
        self.control_panel = self.root / "gpts_agent_control.py"
        self.connect_guide = self.root / "CONNECT_GPT_ACTIONS_RU.md"
        self.req.write_text("fastapi\nuvicorn\n", "utf-8")
        self.control_panel.write_text("print('ok')\n", "utf-8")
        self.connect_guide.write_text(
            "Actions — это кнопки-действия для GPT.\n"
            "Схема — это список доступных действий.\n"
            "Bearer означает: пускать только того, кто знает секретный ключ.\n"
            "Knowledge-файлы — это справочные материалы для GPT.\n",
            "utf-8",
        )
        self.env_example.write_text(
            "AGENT_TOKEN=replace-this-with-a-long-random-secret-token\n"
            "NGROK_DOMAIN=your-domain.ngrok-free.dev\n"
            "WORKSPACE_ROOTS=/Users/your-name/Documents:/workspace:/projects\n",
            "utf-8",
        )

        self.patches = [
            patch.object(sli, "PROJECT_DIR", self.root),
            patch.object(sli, "ENV_FILE", self.env),
            patch.object(sli, "ENV_EXAMPLE_FILE", self.env_example),
            patch.object(sli, "STATE_FILE", self.state),
            patch.object(sli, "VENV_DIR", self.venv),
            patch.object(sli, "TOOLS_DIR", self.tools),
            patch.object(sli, "LOCAL_NGROK_BIN", self.local_ngrok),
            patch.object(sli, "REQUIREMENTS_FILE", self.req),
            patch.object(sli, "CONTROL_PANEL_FILE", self.control_panel),
            patch.object(sli, "CONNECT_GUIDE_FILE", self.connect_guide),
            patch.object(gac, "LOCAL_NGROK_BIN", self.local_ngrok),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_classic_tk_widgets_do_not_receive_tuple_padding_in_constructor(self) -> None:
        files = [
            Path(sli.__file__),
            Path(gac.__file__),
        ]

        def is_classic_tk_widget(call: ast.Call) -> bool:
            func = call.func
            if isinstance(func, ast.Attribute):
                return isinstance(func.value, ast.Name) and func.value.id == "tk" and func.attr in {"Label", "Button"}
            if isinstance(func, ast.Name):
                return func.id in {"Label", "Button"}
            return False

        offenders: list[str] = []
        for file_path in files:
            tree = ast.parse(file_path.read_text("utf-8"), filename=str(file_path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not is_classic_tk_widget(node):
                    continue
                for keyword in node.keywords:
                    if keyword.arg not in {"padx", "pady"}:
                        continue
                    if isinstance(keyword.value, ast.Tuple):
                        offenders.append(f"{file_path}:{node.lineno} uses {keyword.arg}=tuple on classic tk widget")

        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_system_check_success(self) -> None:
        app = make_headless_app()
        with (
            patch("second_lane_installer.platform.system", return_value="Darwin"),
            patch("second_lane_installer.urllib.request.urlopen", return_value=object()),
            patch("second_lane_installer.shutil.disk_usage", return_value=(10, 1, 5 * 1024 * 1024 * 1024)),
            patch("second_lane_installer.os.access", return_value=True),
        ):
            app._step_system_check()
        events = drain_events(app)
        self.assertTrue(any(kind == "hint" and "Система готова" in payload["text"] for kind, payload in events))

    def test_system_check_offline_fails(self) -> None:
        app = make_headless_app()
        with (
            patch("second_lane_installer.platform.system", return_value="Darwin"),
            patch("second_lane_installer.urllib.request.urlopen", side_effect=sli.urllib.error.URLError("offline")),
            patch("second_lane_installer.shutil.disk_usage", return_value=(10, 1, 5 * 1024 * 1024 * 1024)),
            patch("second_lane_installer.os.access", return_value=True),
        ):
            with self.assertRaises(sli.StepFailed):
                app._step_system_check()

    def test_system_check_accepts_internet_when_first_probe_fails(self) -> None:
        app = make_headless_app()
        with (
            patch("second_lane_installer.platform.system", return_value="Darwin"),
            patch(
                "second_lane_installer.urllib.request.urlopen",
                side_effect=[sli.urllib.error.URLError("apple blocked"), object()],
            ),
            patch("second_lane_installer.shutil.disk_usage", return_value=(10, 1, 5 * 1024 * 1024 * 1024)),
            patch("second_lane_installer.os.access", return_value=True),
        ):
            app._step_system_check()
        events = drain_events(app)
        self.assertTrue(any(kind == "hint" and "интернет работает" in payload["text"].lower() for kind, payload in events))

    def test_system_check_offline_message_names_existing_retry_button(self) -> None:
        app = make_headless_app()
        with (
            patch("second_lane_installer.platform.system", return_value="Darwin"),
            patch("second_lane_installer.urllib.request.urlopen", side_effect=sli.urllib.error.URLError("offline")),
            patch("second_lane_installer.shutil.disk_usage", return_value=(10, 1, 5 * 1024 * 1024 * 1024)),
            patch("second_lane_installer.os.access", return_value=True),
        ):
            with self.assertRaisesRegex(sli.StepFailed, "Проверить снова") as ctx:
                app._step_system_check()
        self.assertNotIn("Продолжить", str(ctx.exception))

    def test_system_check_wrong_os_fails_clearly(self) -> None:
        app = make_headless_app()
        with patch("second_lane_installer.platform.system", return_value="Linux"):
            with self.assertRaisesRegex(sli.StepFailed, "macOS"):
                app._step_system_check()

    def test_system_check_low_disk_fails(self) -> None:
        app = make_headless_app()
        with (
            patch("second_lane_installer.platform.system", return_value="Darwin"),
            patch("second_lane_installer.urllib.request.urlopen", return_value=object()),
            patch("second_lane_installer.shutil.disk_usage", return_value=(10, 9, 100)),
            patch("second_lane_installer.os.access", return_value=True),
        ):
            with self.assertRaisesRegex(sli.StepFailed, "места"):
                app._step_system_check()

    def test_full_new_mac_flow_with_required_user_actions(self) -> None:
        app = make_headless_app()
        install_log: list[list[str]] = []
        brew_installed = False
        python_installed = False
        ngrok_installed = False
        has_auth = False

        def fake_run(argv: list[str], attempts: int = 1) -> str:
            nonlocal has_auth, brew_installed, python_installed, ngrok_installed
            install_log.append(argv)
            if argv[:2] == ["/bin/bash", "-c"] and "Homebrew/install" in argv[2]:
                brew_installed = True
            if argv[:3] == ["/opt/homebrew/bin/brew", "install", "python@3.13"]:
                python_installed = True
            if argv[:3] == ["/usr/local/bin/ngrok", "config", "add-authtoken"]:
                has_auth = True
            if argv[:3] == ["/opt/homebrew/bin/python3.13", "-m", "venv"]:
                (self.venv / "bin").mkdir(parents=True, exist_ok=True)
                (self.venv / "bin" / "python").write_text("#!/bin/sh\n", "utf-8")
                os.chmod(self.venv / "bin" / "python", 0o755)
            return "ok"

        def fake_find_brew() -> str | None:
            return "/opt/homebrew/bin/brew" if brew_installed else None

        def fake_find_python() -> str | None:
            return "/opt/homebrew/bin/python3.13" if python_installed else None

        def fake_find_ngrok() -> str | None:
            return "/usr/local/bin/ngrok" if ngrok_installed else None

        def fake_install_ngrok() -> None:
            nonlocal ngrok_installed
            ngrok_installed = True

        with (
            patch.object(app, "_find_brew_bin", side_effect=fake_find_brew),
            patch.object(app, "_find_python_bin", side_effect=fake_find_python),
            patch.object(app, "_find_ngrok_bin", side_effect=fake_find_ngrok),
            patch.object(app, "_install_ngrok_direct", side_effect=fake_install_ngrok),
            patch.object(app, "_run_command", side_effect=fake_run),
            patch.object(app, "_has_ngrok_auth", side_effect=lambda: has_auth),
            patch("second_lane_installer.platform.system", return_value="Darwin"),
            patch("second_lane_installer.urllib.request.urlopen", return_value=object()),
            patch("second_lane_installer.shutil.disk_usage", return_value=(10, 1, 5 * 1024 * 1024 * 1024)),
            patch("second_lane_installer.os.access", return_value=True),
        ):
            app._step_system_check()
            app._step_homebrew()
            app._step_python()
            app._step_ngrok()
            with self.assertRaises(sli.StepActionRequired):
                app._step_ngrok_auth()

            app.current_step_index = 4
            app._action_save_ngrok_token("token-from-user")
            self.assertEqual(app.step_status["ngrok_auth"], "pending")

            # emulate queue processing like UI loop
            events = drain_events(app)
            self.assertTrue(any(k == "step_status" and p["key"] == "ngrok_auth" and p["status"] == "done" for k, p in events))

            with self.assertRaises(sli.StepActionRequired):
                app._step_project_env()
            app.current_step_index = 5
            app._action_save_env_domain("my-team.ngrok-free.dev")
            events = drain_events(app)
            self.assertTrue(any(k == "step_status" and p["key"] == "project_env" and p["status"] == "done" for k, p in events))

            app._step_python_env()
            app._step_finish()

        self.assertTrue(self.env.exists())
        env_text = self.env.read_text("utf-8")
        self.assertIn("NGROK_DOMAIN=my-team.ngrok-free.dev", env_text)
        self.assertIn("WORKSPACE_ROOTS=", env_text)
        token = app._read_env_value("AGENT_TOKEN")
        self.assertRegex(token, r"^[0-9a-f]{64}$")
        self.assertTrue(sli.token_is_safe(token))
        self.assertTrue(any(cmd[:2] == ["/opt/homebrew/bin/brew", "install"] for cmd in install_log))
        self.assertFalse(any(cmd[:3] == ["/opt/homebrew/bin/brew", "install", "ngrok/ngrok/ngrok"] for cmd in install_log))
        self.assertTrue(any(cmd[:2] == ["/usr/local/bin/ngrok", "config"] for cmd in install_log))

    def test_existing_configured_machine_needs_no_user_action(self) -> None:
        app = make_headless_app()
        self.env.write_text(
            "AGENT_TOKEN=abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890\n"
            "NGROK_DOMAIN=stable.ngrok-free.dev\n"
            "WORKSPACE_ROOTS=/Users/test/Documents:/workspace:/projects\n",
            "utf-8",
        )
        with (
            patch.object(app, "_find_brew_bin", return_value="/opt/homebrew/bin/brew"),
            patch.object(app, "_find_python_bin", return_value="/opt/homebrew/bin/python3.13"),
            patch.object(app, "_find_ngrok_bin", return_value="/usr/local/bin/ngrok"),
            patch.object(app, "_run_command") as run_mock,
            patch.object(app, "_has_ngrok_auth", return_value=True),
            patch("second_lane_installer.platform.system", return_value="Darwin"),
            patch("second_lane_installer.urllib.request.urlopen", return_value=object()),
            patch("second_lane_installer.shutil.disk_usage", return_value=(10, 1, 5 * 1024 * 1024 * 1024)),
            patch("second_lane_installer.os.access", return_value=True),
        ):
            app._step_system_check()
            app._step_homebrew()
            app._step_python()
            app._step_ngrok()
            app._step_ngrok_auth()
            app._step_project_env()
        run_mock.assert_called_once_with(["/usr/local/bin/ngrok", "config", "check"])

    def test_intel_mac_paths_are_supported(self) -> None:
        app = make_headless_app()
        self.env.write_text(
            "AGENT_TOKEN=abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890\n"
            "NGROK_DOMAIN=intel.ngrok-free.dev\n"
            "WORKSPACE_ROOTS=/Users/test/Documents:/workspace:/projects\n",
            "utf-8",
        )
        with (
            patch.object(app, "_find_brew_bin", return_value="/usr/local/bin/brew"),
            patch.object(app, "_find_python_bin", return_value="/usr/local/opt/python@3.13/bin/python3.13"),
            patch.object(app, "_find_ngrok_bin", return_value="/usr/local/bin/ngrok"),
            patch.object(app, "_run_command", return_value="ok") as run_mock,
            patch.object(app, "_has_ngrok_auth", return_value=True),
        ):
            app._step_homebrew()
            app._step_python()
            app._step_ngrok()
            app._step_ngrok_auth()
            app._step_project_env()
        run_mock.assert_called_once_with(["/usr/local/bin/ngrok", "config", "check"])

    def test_autopilot_stops_at_first_human_action(self) -> None:
        app = make_headless_app()
        with (
            patch.object(app, "_find_brew_bin", return_value="/opt/homebrew/bin/brew"),
            patch.object(app, "_find_python_bin", return_value="/opt/homebrew/bin/python3.13"),
            patch.object(app, "_find_ngrok_bin", return_value="/usr/local/bin/ngrok"),
            patch.object(app, "_run_command", return_value="ok"),
            patch.object(app, "_has_ngrok_auth", return_value=False),
            patch("second_lane_installer.platform.system", return_value="Darwin"),
            patch("second_lane_installer.urllib.request.urlopen", return_value=object()),
            patch("second_lane_installer.shutil.disk_usage", return_value=(10, 1, 5 * 1024 * 1024 * 1024)),
            patch("second_lane_installer.os.access", return_value=True),
        ):
            app._run_steps_until_blocked(0)
        events = drain_events(app)
        done_keys = [p["key"] for k, p in events if k == "step_status" and p["status"] == "done"]
        action_keys = [p["key"] for k, p in events if k == "step_status" and p["status"] == "action"]
        self.assertEqual(done_keys, ["system_check", "homebrew", "python", "ngrok"])
        self.assertEqual(action_keys, ["ngrok_auth"])

    def test_autopilot_continues_after_ngrok_token_until_domain_action(self) -> None:
        app = make_headless_app()
        app.current_step_index = 4
        self.env_example.write_text(
            "AGENT_TOKEN=replace-this-with-a-long-random-secret-token\n"
            "NGROK_DOMAIN=your-domain.ngrok-free.dev\n"
            "WORKSPACE_ROOTS=/Users/your-name/Documents:/workspace:/projects\n",
            "utf-8",
        )

        def fake_run(argv: list[str], attempts: int = 1) -> str:
            return "ok"

        with (
            patch.object(app, "_find_ngrok_bin", return_value="/usr/local/bin/ngrok"),
            patch.object(app, "_run_command", side_effect=fake_run),
            patch.object(app, "_has_ngrok_auth", return_value=True),
        ):
            app._action_save_ngrok_token("token-from-user")

        events = drain_events(app)
        action_keys = [p["key"] for k, p in events if k == "step_status" and p["status"] == "action"]
        self.assertIn("project_env", action_keys)

    def test_autopilot_finishes_after_domain_when_everything_ready(self) -> None:
        app = make_headless_app()
        app.current_step_index = 5
        self.venv.joinpath("bin").mkdir(parents=True)
        self.venv.joinpath("bin", "python").write_text("#!/bin/sh\n", "utf-8")
        os.chmod(self.venv / "bin" / "python", 0o755)

        with (
            patch.object(app, "_find_python_bin", return_value="/opt/homebrew/bin/python3.13"),
            patch.object(app, "_run_command", return_value="ok"),
        ):
            app._action_save_env_domain("ready.ngrok-free.dev")

        events = drain_events(app)
        done_keys = [p["key"] for k, p in events if k == "step_status" and p["status"] == "done"]
        self.assertIn("project_env", done_keys)
        self.assertIn("python_env", done_keys)
        self.assertIn("finish", done_keys)

    def test_friendly_network_command_error(self) -> None:
        app = make_headless_app()
        message = app._friendly_command_error(["brew", "install", "python@3.13"], 1, "Failed to connect")
        self.assertIn("соединение", message.lower())

    def test_friendly_command_errors_cover_common_install_failures(self) -> None:
        app = make_headless_app()
        self.assertIn("Command Line Tools", app._friendly_command_error(["brew"], 1, "xcode-select missing"))
        self.assertIn("прав", app._friendly_command_error(["brew"], 1, "Permission denied"))
        self.assertIn("ключ", app._friendly_command_error(["ngrok"], 1, "invalid authtoken").lower())

    def test_ngrok_download_ssl_failure_gets_retry_and_clear_message(self) -> None:
        app = make_headless_app()
        output = (
            "Error: Download failed on Cask 'ngrok'\n"
            "curl: (35) LibreSSL SSL_connect: SSL_ERROR_SYSCALL in connection to bin.ngrok.com:443\n"
        )
        self.assertTrue(app._is_transient_download_error(output))
        message = app._friendly_command_error(["/usr/local/bin/brew", "install", "ngrok/ngrok/ngrok"], 1, output)
        self.assertIn("скачать ngrok", message.lower())
        self.assertIn("Проверить снова", message)

    def test_direct_ngrok_install_uses_official_archive_without_brew_cask(self) -> None:
        app = make_headless_app()
        archive_bytes = BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("ngrok", "#!/bin/sh\n")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self) -> bytes:
                return archive_bytes.getvalue()

        with (
            patch("second_lane_installer.platform.machine", return_value="x86_64"),
            patch("second_lane_installer.urllib.request.urlopen", return_value=FakeResponse()) as open_mock,
            patch.object(app, "_run_command", return_value="ngrok version 3\n") as run_mock,
        ):
            app._install_ngrok_direct()

        self.assertTrue(self.local_ngrok.exists())
        self.assertTrue(os.access(self.local_ngrok, os.X_OK))
        requested_url = open_mock.call_args.args[0].full_url
        self.assertIn("bin.equinox.io", requested_url)
        self.assertIn("darwin-amd64", requested_url)
        run_mock.assert_called_once_with([str(self.local_ngrok), "version"])

    def test_step_ngrok_prefers_direct_local_install_over_homebrew_cask(self) -> None:
        app = make_headless_app()
        installed = False

        def fake_find_ngrok() -> str | None:
            return str(self.local_ngrok) if installed else None

        def fake_install() -> None:
            nonlocal installed
            self.local_ngrok.parent.mkdir(parents=True, exist_ok=True)
            self.local_ngrok.write_text("#!/bin/sh\n", "utf-8")
            os.chmod(self.local_ngrok, 0o755)
            installed = True

        with (
            patch.object(app, "_find_ngrok_bin", side_effect=fake_find_ngrok),
            patch.object(app, "_install_ngrok_direct", side_effect=fake_install) as install_mock,
            patch.object(app, "_run_command") as run_mock,
        ):
            app._step_ngrok()

        install_mock.assert_called_once()
        run_mock.assert_not_called()
        events = drain_events(app)
        self.assertTrue(any(kind == "hint" and "ngrok установлен" in payload["text"] for kind, payload in events))

    def test_control_panel_uses_project_local_ngrok(self) -> None:
        self.local_ngrok.parent.mkdir(parents=True, exist_ok=True)
        self.local_ngrok.write_text("#!/bin/sh\n", "utf-8")
        os.chmod(self.local_ngrok, 0o755)
        app = gac.ControlPanel.__new__(gac.ControlPanel)
        self.assertEqual(app.ngrok_bin(), str(self.local_ngrok))

    def test_run_command_retries_transient_download_failures(self) -> None:
        app = make_headless_app()
        calls = 0

        class FakeStdout:
            def __init__(self, lines: list[str]) -> None:
                self.lines = lines

            def __iter__(self):
                return iter(self.lines)

        class FakeProc:
            def __init__(self, code: int, lines: list[str]) -> None:
                self.stdout = FakeStdout(lines)
                self.code = code

            def wait(self) -> int:
                return self.code

        def fake_popen(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return FakeProc(1, ["curl: (35) SSL_ERROR_SYSCALL\n"])
            return FakeProc(0, ["ok\n"])

        with (
            patch("second_lane_installer.subprocess.Popen", side_effect=fake_popen),
            patch("second_lane_installer.time.sleep"),
        ):
            result = app._run_command(["brew", "install", "ngrok/ngrok/ngrok"], attempts=2)
        self.assertEqual(calls, 2)
        self.assertEqual(result, "ok\n")
        events = drain_events(app)
        self.assertTrue(any(kind == "hint" and "попробует ещё раз" in payload["text"] for kind, payload in events))

    def test_save_ngrok_token_without_ngrok_gives_error_event(self) -> None:
        app = make_headless_app()
        app.current_step_index = 4
        with patch.object(app, "_find_ngrok_bin", return_value=None):
            app._action_save_ngrok_token("abc")
        events = drain_events(app)
        self.assertTrue(any(k == "step_status" and p["status"] == "error" for k, p in events))

    def test_entry_paste_uses_clipboard_and_replaces_selection(self) -> None:
        app = make_headless_app()
        app.root = type(
            "Root",
            (),
            {
                "clipboard_get": lambda *_: "token-from-clipboard",
                "clipboard_clear": lambda *_: None,
                "clipboard_append": lambda *_: None,
            },
        )()
        entry = DummyEntry("old value")
        entry.selection = (0, len(entry.text))
        event = type("Event", (), {"widget": entry})()
        result = app._paste_into_entry(event)
        self.assertEqual(result, "break")
        self.assertEqual(entry.text, "token-from-clipboard")

    def test_entry_select_all_and_copy_work(self) -> None:
        app = make_headless_app()
        copied: list[str] = []
        app.root = type(
            "Root",
            (),
            {
                "clipboard_get": lambda *_: "",
                "clipboard_clear": lambda *_: copied.clear(),
                "clipboard_append": lambda *_args: copied.append(_args[-1]),
            },
        )()
        entry = DummyEntry("abc123")
        event = type("Event", (), {"widget": entry})()
        self.assertEqual(app._select_all_entry(event), "break")
        self.assertEqual(entry.selection, (0, 6))
        self.assertEqual(app._copy_from_entry(event), "break")
        self.assertEqual(copied, ["abc123"])

    def test_paste_button_fills_ngrok_token_from_clipboard(self) -> None:
        app = make_headless_app()
        app.root = type("Root", (), {"clipboard_get": lambda *_: "ngrok config add-authtoken abc_123"})()
        app.ngrok_token_var = DummyVar("")
        app.ngrok_token_entry = DummyEntry("")
        app._paste_ngrok_token_from_clipboard()
        self.assertEqual(app.ngrok_token_var.get(), "abc_123")

    def test_paste_button_fills_ngrok_domain_without_https_prefix(self) -> None:
        app = make_headless_app()
        app.root = type("Root", (), {"clipboard_get": lambda *_: "https://my-name.ngrok-free.dev/"})()
        app.ngrok_domain_var = DummyVar("")
        app.ngrok_domain_entry = DummyEntry("")
        app._paste_ngrok_domain_from_clipboard()
        self.assertEqual(app.ngrok_domain_var.get(), "my-name.ngrok-free.dev")

    def test_ngrok_token_paste_helpers_accept_full_command(self) -> None:
        self.assertEqual(sli.normalize_ngrok_token("ngrok config add-authtoken abc_123"), "abc_123")
        self.assertEqual(sli.normalize_ngrok_token("NGROK_AUTHTOKEN=abc_123"), "abc_123")
        self.assertEqual(sli.normalize_ngrok_token("'abc_123'"), "abc_123")

    def test_ngrok_help_buttons_open_account_token_and_domain_pages(self) -> None:
        app = make_headless_app()
        app.current_step_index = 4
        app.step_status["ngrok_auth"] = "action"
        with patch("second_lane_installer.subprocess.Popen") as popen_mock:
            app._on_secondary()
        self.assertEqual(popen_mock.call_args.args[0], ["open", sli.NGROK_AUTHTOKEN_URL])

        app.current_step_index = 5
        app.step_status["project_env"] = "action"
        with patch("second_lane_installer.subprocess.Popen") as popen_mock:
            app._on_secondary()
        self.assertEqual(popen_mock.call_args.args[0], ["open", sli.NGROK_DOMAINS_URL])

    def test_state_file_corrupted_fallback(self) -> None:
        app = make_headless_app()
        self.state.write_text("{broken", "utf-8")
        loaded = app._load_state()
        self.assertEqual(loaded["current_step_index"], 0)
        self.assertEqual(loaded["step_status"]["system_check"], "pending")

    def test_state_file_round_trip_keeps_progress_and_domain(self) -> None:
        app = make_headless_app()
        app.current_step_index = 5
        app.step_status["system_check"] = "done"
        app.ngrok_domain_var.set("saved.ngrok-free.dev")
        app.workspace_root_var.set("/Users/test/Documents")
        app._save_state()
        loaded = app._load_state()
        self.assertEqual(loaded["current_step_index"], 5)
        self.assertEqual(loaded["step_status"]["system_check"], "done")
        self.assertEqual(loaded["inputs"]["ngrok_domain"], "saved.ngrok-free.dev")
        self.assertEqual(loaded["inputs"]["workspace_root"], "/Users/test/Documents")

    def test_ngrok_domain_validation(self) -> None:
        app = make_headless_app()
        self.assertTrue(app._valid_ngrok_domain("my-team.ngrok-free.dev"))
        self.assertTrue(app._valid_ngrok_domain("myteam.ngrok.app"))
        self.assertFalse(app._valid_ngrok_domain("your-domain.ngrok-free.dev"))
        self.assertFalse(app._valid_ngrok_domain("myteam.example.com"))
        self.assertFalse(app._valid_ngrok_domain("my.team.ngrok-free.dev"))

    def test_env_generation_preserves_existing_workspace_roots(self) -> None:
        app = make_headless_app()
        self.env.write_text(
            "AGENT_TOKEN=short\n"
            "NGROK_DOMAIN=ok.ngrok-free.dev\n"
            "WORKSPACE_ROOTS=/custom/root:/another/root\n",
            "utf-8",
        )
        app._step_project_env()
        env_text = self.env.read_text("utf-8")
        self.assertIn("WORKSPACE_ROOTS=/custom/root:/another/root", env_text)
        self.assertNotIn("AGENT_TOKEN=short", env_text)
        self.assertTrue(sli.token_is_safe(app._read_env_value("AGENT_TOKEN")))

    def test_selected_workspace_root_is_saved_into_env(self) -> None:
        app = make_headless_app()
        workspace = self.root / "Chosen Workspace"
        workspace.mkdir()
        app.workspace_root_var.set(str(workspace))
        self.env.write_text(
            "AGENT_TOKEN=short\n"
            "NGROK_DOMAIN=ok.ngrok-free.dev\n",
            "utf-8",
        )
        app._step_project_env()
        self.assertEqual(app._read_env_value("WORKSPACE_ROOTS"), str(workspace.resolve()))

    def test_generated_agent_tokens_are_cryptographic_shape_and_unique(self) -> None:
        app = make_headless_app()
        tokens = {app._generate_token() for _ in range(100)}
        self.assertEqual(len(tokens), 100)
        for token in tokens:
            self.assertRegex(token, r"^[0-9a-f]{64}$")
            self.assertTrue(sli.token_is_safe(token))
            self.assertTrue(runtime_config.token_is_safe(token))

    def test_installer_replaces_long_but_obviously_weak_agent_token(self) -> None:
        app = make_headless_app()
        self.env.write_text(
            "AGENT_TOKEN=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
            "NGROK_DOMAIN=ok.ngrok-free.dev\n",
            "utf-8",
        )
        app._step_project_env()
        token = app._read_env_value("AGENT_TOKEN")
        self.assertRegex(token, r"^[0-9a-f]{64}$")
        self.assertNotEqual(token, "a" * 64)
        self.assertTrue(sli.token_is_safe(token))

    def test_installer_preserves_existing_safe_agent_token(self) -> None:
        app = make_headless_app()
        existing_token = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        self.env.write_text(
            f"AGENT_TOKEN={existing_token}\n"
            "NGROK_DOMAIN=ok.ngrok-free.dev\n"
            "WORKSPACE_ROOTS=/custom/root\n",
            "utf-8",
        )

        app._step_project_env()
        self.assertEqual(app._read_env_value("AGENT_TOKEN"), existing_token)

        with patch.object(app, "_run_steps_until_blocked"):
            app._action_save_env_domain("stable.ngrok-free.dev")
        self.assertEqual(app._read_env_value("AGENT_TOKEN"), existing_token)

    def test_runtime_rejects_placeholder_and_repeated_agent_tokens(self) -> None:
        self.assertFalse(runtime_config.token_is_safe("REPLACE-THIS-WITH-A-LONG-RANDOM-SECRET-TOKEN"))
        self.assertFalse(runtime_config.token_is_safe("a" * 64))
        self.assertFalse(runtime_config.token_is_safe("abcabcabcabcabcabcabcabcabcabcabcabc"))
        self.assertTrue(runtime_config.token_is_safe("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"))

    def test_missing_env_example_is_clear_failure(self) -> None:
        app = make_headless_app()
        self.env_example.unlink()
        with self.assertRaisesRegex(sli.StepFailed, ".env.example"):
            app._prepare_env_file()

    def test_ngrok_config_check_failure_blocks_success(self) -> None:
        app = make_headless_app()
        with patch.object(app, "_run_command", side_effect=sli.StepFailed("ngrok config broken")):
            with self.assertRaisesRegex(sli.StepFailed, "конфиг"):
                app._check_ngrok_config("/usr/local/bin/ngrok")

    def test_python_env_reuses_existing_venv(self) -> None:
        app = make_headless_app()
        self.venv.joinpath("bin").mkdir(parents=True)
        self.venv.joinpath("bin", "python").write_text("#!/bin/sh\n", "utf-8")
        os.chmod(self.venv / "bin" / "python", 0o755)
        with (
            patch.object(app, "_find_python_bin", return_value="/opt/homebrew/bin/python3.13"),
            patch.object(app, "_run_command", return_value="ok") as run_mock,
        ):
            app._step_python_env()
        calls = [call.args[0] for call in run_mock.call_args_list]
        self.assertFalse(any(cmd[:3] == ["/opt/homebrew/bin/python3.13", "-m", "venv"] for cmd in calls))
        self.assertTrue(any(cmd[1:4] == ["-m", "pip", "install"] for cmd in calls))

    def test_launch_control_panel_uses_venv_python(self) -> None:
        app = make_headless_app()
        app.log_text = type("Log", (), {"insert": lambda *_: None, "see": lambda *_: None})()
        self.venv.joinpath("bin").mkdir(parents=True)
        self.venv.joinpath("bin", "python").write_text("#!/bin/sh\n", "utf-8")
        os.chmod(self.venv / "bin" / "python", 0o755)
        with patch("second_lane_installer.subprocess.Popen") as popen_mock:
            app._launch_control_panel()
        popen_mock.assert_called_once()
        argv = popen_mock.call_args.args[0]
        self.assertEqual(argv[0], str(self.venv / "bin" / "python"))
        self.assertIn("--auto-start", argv)

    def test_finish_secondary_opens_local_connect_guide(self) -> None:
        app = make_headless_app()
        app.current_step_index = 7
        app.step_status["finish"] = "done"
        with patch("second_lane_installer.subprocess.Popen") as popen_mock:
            app._on_secondary()
        argv = popen_mock.call_args.args[0]
        self.assertEqual(argv, ["open", str(self.connect_guide)])

    def test_step_copy_explains_required_technical_words(self) -> None:
        all_copy = "\n".join(
            f"{step.title}\n{step.description}\n{step.why}"
            for step in sli.STEP_SPECS
        ).lower()
        self.assertIn("homebrew", all_copy)
        self.assertIn("установщик программ", all_copy)
        self.assertIn("python", all_copy)
        self.assertIn("двигатель second lane", all_copy)
        self.assertIn("ngrok", all_copy)
        self.assertIn("адрес", all_copy)
        self.assertIn("ключ", all_copy)
        self.assertIn("файл настроек", all_copy)

    def test_installer_copy_never_asks_user_to_type_terminal_commands(self) -> None:
        user_copy = "\n".join(
            [
                "Добро пожаловать в установщик Second Lane.",
                "Важно: ничего не нужно вводить в Terminal вручную.",
                *[
                    f"{step.title}\n{step.description}\n{step.why}"
                    for step in sli.STEP_SPECS
                ],
                (
                    "Нужно одно ручное действие: получить ключ ngrok и вставить его в поле ниже.\n"
                    "Если аккаунта ngrok нет, нажми «Открыть ngrok и получить ключ». Откроется сайт ngrok: создай бесплатный аккаунт через Google, GitHub или email.\n"
                    "После входа открой страницу Your Authtoken, скопируй длинный ключ и вставь его сюда. В Terminal ничего вставлять не нужно."
                ),
            ]
        ).lower()
        forbidden = [
            "ngrok config add-authtoken",
            "brew install",
            "pip install",
            "chmod +x",
            "выполни",
            "вставь в terminal",
            "вставь в терминал",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, user_copy)

    def test_control_panel_bad_token_message_sends_user_back_to_installer(self) -> None:
        app = gac.ControlPanel.__new__(gac.ControlPanel)
        messages: list[str] = []
        app.write_log = messages.append
        app.explain_unsafe_token()
        text = "\n".join(messages).lower()
        self.assertIn("установщик сам создаст безопасный ключ", text)
        self.assertIn("ничего не вставляй в terminal", text)
        self.assertNotIn("найди строку agent_token", text)
        self.assertNotIn("вставь после =", text)

    def test_connect_guide_explains_jargon_before_user_uses_it(self) -> None:
        text = self.connect_guide.read_text("utf-8").lower()
        self.assertIn("actions — это кнопки-действия", text)
        self.assertIn("схема — это список доступных действий", text)
        self.assertIn("bearer означает", text)
        self.assertIn("knowledge-файлы — это справочные материалы", text)


class BootstrapScriptSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = Path(__file__).resolve().parent / "Установить Second Lane.command"
        self.script = self.root / "Установить Second Lane.command"
        shutil.copyfile(self.source, self.script)
        os.chmod(self.script, 0o755)
        (self.root / "second_lane_installer.py").write_text("print('gui')\n", "utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_script(self, path_prefix: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATH"] = f"{path_prefix}:/usr/bin:/bin:/usr/sbin:/sbin"
        env["SECOND_LANE_INSTALLER_BOOTSTRAP_CHECK_ONLY"] = "1"
        env["SECOND_LANE_INSTALLER_FORCE_BOOTSTRAP"] = "1"
        env["SECOND_LANE_INSTALLER_TEST_SKIP_ABSOLUTE_PYTHON"] = "1"
        return subprocess.run(
            ["/bin/zsh", str(self.script)],
            cwd=self.root,
            env=env,
            input="\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )

    def test_bootstrap_uses_python_with_tkinter_when_available(self) -> None:
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake_python = bin_dir / "python3.13"
        fake_python.write_text("#!/bin/sh\nexit 0\n", "utf-8")
        os.chmod(fake_python, 0o755)
        result = subprocess.run(
            ["/bin/zsh", str(self.script)],
            cwd=self.root,
            env={**os.environ, "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)

    def test_bootstrap_check_only_does_not_open_gui_when_python_ready(self) -> None:
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake_python = bin_dir / "python3.13"
        fake_python.write_text("#!/bin/sh\nexit 0\n", "utf-8")
        os.chmod(fake_python, 0o755)
        result = subprocess.run(
            ["/bin/zsh", str(self.script)],
            cwd=self.root,
            env={
                **os.environ,
                "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin",
                "SECOND_LANE_INSTALLER_BOOTSTRAP_CHECK_ONLY": "1",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Bootstrap self-check", result.stdout)
        self.assertIn("Подходящий Python", result.stdout)

    def test_bootstrap_prepares_with_fake_brew_and_python(self) -> None:
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake_curl = bin_dir / "curl"
        fake_brew = bin_dir / "brew"
        fake_python = bin_dir / "python3.13"
        fake_curl.write_text("#!/bin/sh\nexit 0\n", "utf-8")
        fake_brew.write_text("#!/bin/sh\nexit 0\n", "utf-8")
        fake_python.write_text("#!/bin/sh\nexit 1\n", "utf-8")
        for path in (fake_curl, fake_brew, fake_python):
            os.chmod(path, 0o755)

        result = self.run_script(str(bin_dir))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Подготовка Python 3.13", result.stdout)
        self.assertIn("Нужен официальный Python для графического окна", result.stdout)

    def test_bootstrap_installs_python_tk_when_python_exists_without_tkinter(self) -> None:
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        marker = self.root / "tk-ready"
        install_log = self.root / "brew.log"
        fake_curl = bin_dir / "curl"
        fake_brew = bin_dir / "brew"
        fake_python = bin_dir / "python3.13"
        fake_python3 = bin_dir / "python3"
        fake_curl.write_text("#!/bin/sh\nexit 0\n", "utf-8")
        fake_brew.write_text(
            "#!/bin/sh\n"
            f"echo \"$@\" >> {install_log!s}\n"
            "if [ \"$1\" = \"install\" ] && [ \"$2\" = \"python-tk@3.13\" ]; then\n"
            f"  touch {marker!s}\n"
            "fi\n"
            "exit 0\n",
            "utf-8",
        )
        fake_python.write_text(
            "#!/bin/sh\n"
            f"if [ -f {marker!s} ]; then exit 0; fi\n"
            "exit 1\n",
            "utf-8",
        )
        shutil.copyfile(fake_python, fake_python3)
        for path in (fake_curl, fake_brew, fake_python, fake_python3):
            os.chmod(path, 0o755)

        result = self.run_script(str(bin_dir))
        self.assertEqual(result.returncode, 0, result.stdout)
        log_text = install_log.read_text("utf-8")
        self.assertIn("install python@3.13", log_text)
        self.assertIn("install python-tk@3.13", log_text)
        self.assertIn("Подготовка окна установщика", result.stdout)

    def test_bootstrap_finds_absolute_python_candidate_outside_path(self) -> None:
        hidden_dir = self.root / "hidden-python"
        hidden_dir.mkdir()
        fake_python = hidden_dir / "python3.13"
        fake_python.write_text("#!/bin/sh\nexit 0\n", "utf-8")
        os.chmod(fake_python, 0o755)

        result = subprocess.run(
            ["/bin/zsh", str(self.script)],
            cwd=self.root,
            env={
                **os.environ,
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "SECOND_LANE_INSTALLER_BOOTSTRAP_CHECK_ONLY": "1",
                "SECOND_LANE_INSTALLER_FORCE_BOOTSTRAP": "1",
                "SECOND_LANE_INSTALLER_TEST_SKIP_ABSOLUTE_PYTHON": "1",
                "SECOND_LANE_INSTALLER_TEST_ABSOLUTE_PYTHON_CANDIDATE": str(fake_python),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Подходящий Python для GUI найден", result.stdout)

    def test_bootstrap_exports_homebrew_paths_for_finder_launches(self) -> None:
        script_text = self.script.read_text("utf-8")
        self.assertIn('export PATH="${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"', script_text)
        self.assertIn('INSTALLER_PY="$SCRIPT_DIR/second_lane_installer.py"', script_text)
        self.assertIn('exec "$PY_BIN" "$INSTALLER_PY"', script_text)
        self.assertIn('PYTHON_ORG_MACOS_URL="https://www.python.org/downloads/latest/python3.13/"', script_text)
        self.assertIn("root = tk.Tk()", script_text)
        self.assertNotIn("for PY_BIN in python3.13 python3", script_text)
        self.assertNotIn("python3)", script_text)

    def test_bootstrap_opens_python_org_when_tkinter_imports_but_gui_crashes(self) -> None:
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        install_log = self.root / "brew.log"
        fake_curl = bin_dir / "curl"
        fake_brew = bin_dir / "brew"
        fake_python = bin_dir / "python3.13"
        fake_python3 = bin_dir / "python3"
        fake_curl.write_text("#!/bin/sh\nexit 0\n", "utf-8")
        fake_brew.write_text(
            "#!/bin/sh\n"
            f"echo \"$@\" >> {install_log!s}\n"
            "exit 0\n",
            "utf-8",
        )
        fake_python.write_text(
            "#!/bin/sh\n"
            "payload=$(cat)\n"
            "printf '%s' \"$payload\" | grep -q 'root = tk.Tk()' && exit 134\n"
            "printf '%s' \"$payload\" | grep -q 'import tkinter' && exit 0\n"
            "exit 1\n",
            "utf-8",
        )
        shutil.copyfile(fake_python, fake_python3)
        for path in (fake_curl, fake_brew, fake_python, fake_python3):
            os.chmod(path, 0o755)

        result = subprocess.run(
            ["/bin/zsh", str(self.script)],
            cwd=self.root,
            env={
                **os.environ,
                "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin",
                "SECOND_LANE_INSTALLER_FORCE_BOOTSTRAP": "1",
                "SECOND_LANE_INSTALLER_TEST_SKIP_ABSOLUTE_PYTHON": "1",
                "SECOND_LANE_INSTALLER_TEST_DISABLE_OPEN": "1",
            },
            input="\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Нужен официальный Python для графического окна", result.stdout)
        self.assertIn("официальный Python installer", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
