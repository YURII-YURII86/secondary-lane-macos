# Second Lane
# Copyright (c) 2026 Yurii Slepnev
# Licensed under the Apache License, Version 2.0.
# Official: https://t.me/yurii_yurii86 | https://youtube.com/@yurii_yurii86 | https://instagram.com/yurii_yurii86
# /// CONTEXT_BLOCK
# ID: ufa_local_control_panel
# TYPE: interface
# PURPOSE: Local operator panel for starting, stopping, and observing the daemon and public tunnel.
# DEPENDS_ON: [.env, openapi.gpts.yaml, .venv/bin/uvicorn]
# USED_BY: [Запустить Second Lane.command]
# STATE: active
# /// ---
from __future__ import annotations

import os
import re
import shutil
import signal
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import json
from dataclasses import dataclass
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, Button, Frame, Label, StringVar, Text, Tk
import tkinter.font as tkfont
from tkinter.scrolledtext import ScrolledText

from app.core.config import token_is_safe
from ui_brand import (
    BRAND_AUTHOR,
    BRAND_CONTROL_BLURB,
    BRAND_COPYRIGHT,
    BRAND_LICENSE,
    BRAND_LINKS,
    BRAND_NAME,
    BRAND_PRODUCT,
    BRAND_TAGLINE,
    PALETTE,
    open_external,
)
from runtime_paths import resolve_project_dir

try:
    import certifi
except ImportError:  # pragma: no cover - optional dependency at runtime
    certifi = None


PROJECT_DIR = resolve_project_dir(__file__)
ENV_FILE = PROJECT_DIR / ".env"
OPENAPI_FILES = [
    PROJECT_DIR / "openapi.gpts.yaml",
]
DEFAULT_VENV_UVICORN = PROJECT_DIR / ".venv" / "bin" / "uvicorn"
LOCAL_NGROK_BIN = PROJECT_DIR / "tools" / "ngrok" / "ngrok"
PYTHON = "python3.13"
LOCAL_URL = "http://127.0.0.1:8787"

# --- Tunnel defaults ---
DEFAULT_NGROK_DOMAIN = ""
TUNNEL_HEALTH_ATTEMPTS = 4
TUNNEL_HEALTH_DELAY_SEC = 2.0
TUNNEL_HEALTH_TIMEOUT_SEC = 6
TUNNEL_RESTART_COOLDOWN_SEC = 5
TUNNEL_MONITOR_INTERVAL_MS = 10_000
NGROK_BLOCKED_IP_ERROR = "ERR_NGROK_9040"
PUBLIC_CHECK_INTERVAL_SEC = 25
PUBLIC_CHECK_MAX_FAILURES = 2
RECOVERY_BACKOFF_STEPS_SEC = [3, 10, 30]


@dataclass
class TunnelFailure:
    code: str
    summary: str
    recoverable: bool


@dataclass
class LocalDaemonProcess:
    pid: int
    cwd: Path | None
    command: str


class ControlPanel:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(f"{BRAND_NAME} Control")
        self.root.geometry("1120x760")
        self.root.minsize(980, 680)
        self.root.configure(bg=PALETTE["app_bg"])
        self.heading_font = self._native_font("TkDefaultFont", 8, "bold")
        self.section_font = self._native_font("TkDefaultFont", 4, "bold")
        self.body_font = self._native_font("TkDefaultFont", 0, "normal")
        self.small_font = self._native_font("TkDefaultFont", -1, "normal")
        self.log_font = self._native_font("TkFixedFont", 0, None)

        self.agent_proc: subprocess.Popen | None = None
        self.tunnel_proc: subprocess.Popen | None = None
        self._using_external_daemon = False
        self.tunnel_url = StringVar(value="Туннель: не запущен")
        self.agent_status = StringVar(value="Демон: не запущен")
        self.last_url: str | None = None
        self._tunnel_restart_count = 0
        self._tunnel_max_restarts = 5
        self._tunnel_blocked_reason: str | None = None
        self._last_tunnel_failure: TunnelFailure | None = None
        self._recovering_tunnel = False
        self._public_check_running = False
        self._last_public_check_ts = 0.0
        self._public_check_failures = 0

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._poll_status()

    def _native_font(self, font_name: str, size_delta: int, weight: str | None) -> tuple[str, int, str]:
        base = tkfont.nametofont(font_name)
        family = str(base.actual("family"))
        size = int(base.actual("size")) + size_delta
        resolved_weight = str(weight or base.actual("weight"))
        return (family, max(size, 10), resolved_weight)

    # --- UI ---

    def _build_ui(self) -> None:
        shell = Frame(self.root, bg=PALETTE["app_bg"], padx=18, pady=18)
        shell.pack(fill=BOTH, expand=True)

        hero = Frame(shell, bg=PALETTE["surface"], highlightbackground=PALETTE["border"], highlightthickness=1, padx=20, pady=18)
        hero.pack(fill="x", pady=(0, 14))
        left = Frame(hero, bg=PALETTE["surface"])
        left.pack(side=LEFT, fill="x", expand=True)
        Label(left, text=f"{BRAND_NAME} Control", font=self.heading_font, bg=PALETTE["surface"], fg=PALETTE["text"]).pack(anchor="w")
        Label(left, text=BRAND_CONTROL_BLURB, font=self.body_font, bg=PALETTE["surface"], fg=PALETTE["muted"], wraplength=760, justify=LEFT).pack(anchor="w", pady=(8, 0))
        status_strip = Frame(left, bg=PALETTE["surface"])
        status_strip.pack(anchor="w", pady=(12, 0))
        self._make_status_chip(status_strip, "Локальный демон", self.agent_status, PALETTE["panel"], PALETTE["text"]).pack(side=LEFT, padx=(0, 10))
        self._make_status_chip(status_strip, "Публичный адрес", self.tunnel_url, PALETTE["panel"], PALETTE["text"]).pack(side=LEFT)

        controls = Frame(shell, bg=PALETTE["surface"], highlightbackground=PALETTE["border"], highlightthickness=1, padx=16, pady=14)
        controls.pack(fill="x")

        row_top = Frame(controls, bg=PALETTE["surface"])
        row_top.pack(anchor="w", pady=(0, 10))
        row_bottom = Frame(controls, bg=PALETTE["surface"])
        row_bottom.pack(anchor="w")

        self._make_action_button(row_top, "Запустить", self.start_all, PALETTE["accent"], PALETTE["surface"]).pack(side=LEFT, padx=8)
        self._make_action_button(row_top, "Перезапустить демон", self.restart_daemon, PALETTE["accent_soft"], PALETTE["accent_deep"]).pack(side=LEFT, padx=8)
        self._make_action_button(row_top, "Выключить", self.stop_all, PALETTE["surface"], PALETTE["text"], border=True).pack(side=LEFT, padx=8)

        self._make_action_button(row_bottom, "Скопировать URL", self.copy_url, PALETTE["surface"], PALETTE["text"], border=True).pack(side=LEFT, padx=8)
        self._make_action_button(row_bottom, "Проверить", self.check_now, PALETTE["surface"], PALETTE["text"], border=True).pack(side=LEFT, padx=8)
        self._make_action_button(row_bottom, "Открыть .env", self.open_env_file, PALETTE["surface"], PALETTE["text"], border=True).pack(side=LEFT, padx=8)

        log_wrap = Frame(shell, bg=PALETTE["surface"], highlightbackground=PALETTE["border"], highlightthickness=1, padx=16, pady=14)
        log_wrap.pack(fill=BOTH, expand=True, pady=(14, 0))
        top_row = Frame(log_wrap, bg=PALETTE["surface"])
        top_row.pack(fill="x", pady=(0, 8))
        Label(top_row, text="Живой журнал работы", font=self.section_font, bg=PALETTE["surface"], fg=PALETTE["text"]).pack(side=LEFT)
        Button(
            top_row,
            text="Скопировать лог",
            command=self.copy_log,
            font=self.body_font,
            padx=10,
            pady=3,
        ).pack(side=RIGHT)

        self.log = ScrolledText(
            log_wrap,
            height=20,
            wrap="word",
            font=self.log_font,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            relief="flat",
            borderwidth=0,
            insertbackground=PALETTE["text"],
        )
        self.log.pack(fill=BOTH, expand=True)
        self.log.configure(highlightthickness=1, highlightbackground=PALETTE["border"], highlightcolor=PALETTE["accent"])
        self.write_log(
            f"{BRAND_NAME} by {BRAND_AUTHOR}\n"
            f"{BRAND_TAGLINE}\n\n"
            "Открой это окно и нажми «Запустить».\n"
            "Важно: импортируй openapi.gpts.yaml в GPT Actions только после строки "
            "«Туннель активен». До этого в файле может быть учебный адрес-заглушка.\n"
        )

        footer = Frame(shell, bg=PALETTE["app_bg"])
        footer.pack(fill="x", pady=(10, 0))
        Label(footer, text=f"{BRAND_COPYRIGHT} · {BRAND_LICENSE}", font=self.small_font, bg=PALETTE["app_bg"], fg=PALETTE["muted"]).pack(side=LEFT)
        links = Frame(footer, bg=PALETTE["app_bg"])
        links.pack(side=RIGHT)
        for link in BRAND_LINKS:
            Button(
                links,
                text=link.label,
                command=lambda url=link.url: open_external(url),
                relief="flat",
                bd=0,
                cursor="hand2",
                font=self.small_font,
                bg=PALETTE["app_bg"],
                fg=PALETTE["muted"],
                activebackground=PALETTE["app_bg"],
                activeforeground=PALETTE["text"],
                padx=4,
                pady=2,
            ).pack(side=LEFT, padx=(8, 0))

    def _make_action_button(self, parent: Frame, text: str, command, bg: str, fg: str, border: bool = False) -> Button:
        return Button(
            parent,
            text=text,
            command=command,
            font=self.body_font,
            padx=12,
            pady=4,
        )

    def _make_status_chip(self, parent: Frame, title: str, textvariable: StringVar, bg: str, fg: str) -> Frame:
        card = Frame(parent, bg=bg, padx=10, pady=8, highlightbackground=PALETTE["border"], highlightthickness=1)
        Label(card, text=title, font=self.small_font, bg=bg, fg=PALETTE["muted"]).pack(anchor="w")
        Label(card, textvariable=textvariable, font=self.small_font, bg=bg, fg=fg, wraplength=250, justify=LEFT).pack(anchor="w", pady=(4, 0))
        return card

    def write_log(self, text: str) -> None:
        self.log.insert(END, text)
        self.log.see(END)

    # --- Env / config ---

    def load_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text("utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
        env["ENABLED_PROVIDER_MANIFESTS"] = str(PROJECT_DIR / "app" / "providers")
        env["STATE_DB_PATH"] = str(PROJECT_DIR / "data" / "agent.db")
        default_workspace = f"{Path.home() / 'Documents'}:/workspace:/projects"
        env.setdefault("WORKSPACE_ROOTS", default_workspace)
        return env

    def agent_token(self) -> str:
        return self.load_env().get("AGENT_TOKEN", "")

    def agent_token_is_safe(self) -> bool:
        return token_is_safe(self.agent_token())

    def explain_unsafe_token(self) -> None:
        self.write_log(
            "Не могу безопасно запустить агента: токен защиты не заполнен или выглядит как временная заглушка.\n\n"
            "Что это значит простыми словами:\n"
            "- этот токен работает как секретный ключ для доступа к агенту через интернет;\n"
            "- если оставить пустое значение или что-то вроде change-me, защиту легко угадать;\n"
            "- поэтому запуск сейчас специально остановлен.\n\n"
            "Что сделать:\n"
            "1. Закрой эту панель.\n"
            "2. Запусти файл «Установить Second Lane.command».\n"
            "3. Установщик сам создаст безопасный ключ и сохранит его в файл настроек.\n"
            "4. После этого снова нажми «Запустить Second Lane».\n\n"
            "Важно:\n"
            "- не придумывай ключ вручную;\n"
            "- ничего не вставляй в Terminal;\n"
            "- не публикуй этот токен в скриншотах и сообщениях.\n"
        )

    def ngrok_domain(self) -> str:
        return self.load_env().get("NGROK_DOMAIN", DEFAULT_NGROK_DOMAIN).strip()

    def _classify_ngrok_output(self, text: str) -> TunnelFailure:
        lowered = text.lower()
        if NGROK_BLOCKED_IP_ERROR.lower() in lowered:
            return TunnelFailure(
                code="ip_blocked",
                summary="ngrok заблокировал запуск с текущего IP",
                recoverable=False,
            )
        if "authentication failed" in lowered or "invalid authtoken" in lowered:
            return TunnelFailure(
                code="auth_failed",
                summary="ngrok отклонил токен или доступ аккаунта",
                recoverable=False,
            )
        if "reserved domain" in lowered or "domain" in lowered and ("invalid" in lowered or "not found" in lowered):
            return TunnelFailure(
                code="domain_invalid",
                summary="ngrok не принял указанный домен",
                recoverable=False,
            )
        if "address already in use" in lowered:
            return TunnelFailure(
                code="port_busy",
                summary="порт 8787 уже занят",
                recoverable=True,
            )
        if "timeout" in lowered or "eof" in lowered or "failed to reconnect session" in lowered:
            return TunnelFailure(
                code="network_temporary",
                summary="временная проблема сети или сессии ngrok",
                recoverable=True,
            )
        return TunnelFailure(
            code="process_crashed",
            summary="ngrok завершился до готовности туннеля",
            recoverable=True,
        )

    def _describe_tunnel_failure(self, failure: TunnelFailure) -> str:
        if failure.code == "ip_blocked":
            return (
                "ngrok не пустил этот IP. "
                "Это внешняя блокировка со стороны ngrok, сервис сам её не снимет."
            )
        if failure.code == "auth_failed":
            return "ngrok не принял токен или права аккаунта."
        if failure.code == "domain_invalid":
            return "ngrok не смог использовать домен из .env."
        if failure.code == "port_busy":
            return "локальный порт 8787 занят другим процессом."
        if failure.code == "network_temporary":
            return "временный сетевой сбой при подключении к ngrok."
        return failure.summary

    def _preflight_tunnel_check(self) -> tuple[bool, str]:
        ngrok_bin = self.ngrok_bin()
        if not ngrok_bin:
            return False, "ngrok не найден. Запусти установщик Second Lane ещё раз, он сам докачает ngrok."
        domain = self.ngrok_domain().strip()
        if not domain:
            return False, "в .env не задан NGROK_DOMAIN"
        try:
            result = subprocess.run(
                [ngrok_bin, "config", "check"],
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
            )
        except Exception as exc:
            return False, f"не смог проверить конфиг ngrok: {exc}"
        if result.returncode != 0:
            output = (result.stdout or "").strip()
            return False, f"конфиг ngrok невалиден: {output or 'неизвестная ошибка'}"
        if not self._local_daemon_ready():
            return False, "локальный демон не отвечает на /health"
        return True, "OK"

    def ngrok_bin(self) -> str | None:
        if LOCAL_NGROK_BIN.exists():
            return str(LOCAL_NGROK_BIN)
        return shutil.which("ngrok")

    # --- Python env ---

    def uvicorn_bin(self) -> Path:
        return DEFAULT_VENV_UVICORN

    def ensure_uvicorn(self) -> bool:
        if self.uvicorn_bin().exists():
            return True
        if not shutil.which(PYTHON):
            self.write_log(
                "Не найден python3.13. Локальный запуск и pytest в этом проекте сейчас подтверждены именно на Python 3.13; "
                "Python 3.14 для этого pinned stack не считается поддержанным.\n"
            )
            return False
        self.write_log("Не нашёл готовый uvicorn. Создаю окружение и ставлю зависимости через python3.13...\n")
        try:
            uvicorn_bin = self.uvicorn_bin()
            subprocess.run([PYTHON, "-m", "venv", str(uvicorn_bin.parent.parent)], cwd=PROJECT_DIR, check=True)
            subprocess.run(
                [str(uvicorn_bin.parent / "pip"), "install", "-r", str(PROJECT_DIR / "requirements.txt")],
                cwd=PROJECT_DIR,
                check=True,
            )
            return True
        except Exception as exc:
            self.write_log(f"Не смог подготовить Python-окружение через {PYTHON}: {exc}\n")
            return False

    # --- Start / stop ---

    def start_all(self) -> None:
        self._tunnel_restart_count = 0
        self._last_tunnel_failure = None
        threading.Thread(target=self._start_all_worker, daemon=True).start()

    def restart_daemon(self) -> None:
        self._tunnel_restart_count = 0
        self._last_tunnel_failure = None
        threading.Thread(target=self._restart_daemon_worker, daemon=True).start()

    def _local_daemon_ready(self) -> bool:
        ok, _ = self._url_ok(f"{LOCAL_URL}/health")
        return ok

    def _stream_process(self, proc: subprocess.Popen, label: str) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            short = line.rstrip()
            if short:
                self.write_log(f"[{label}] {short}\n")
        exit_code = proc.poll()
        if exit_code not in (None, 0):
            self.write_log(f"[{label}] процесс завершился с кодом {exit_code}\n")

    def _find_listener_pid(self, port: int) -> int | None:
        try:
            result = subprocess.run(
                ["lsof", "-tiTCP:%s" % port, "-sTCP:LISTEN"],
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
        except Exception:
            return None
        raw = (result.stdout or "").strip().splitlines()
        if not raw:
            return None
        try:
            return int(raw[0].strip())
        except ValueError:
            return None

    def _describe_local_daemon_process(self) -> LocalDaemonProcess | None:
        pid = self._find_listener_pid(8787)
        if pid is None:
            return None
        cwd: Path | None = None
        command = ""
        try:
            cwd_result = subprocess.run(
                ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
            for line in (cwd_result.stdout or "").splitlines():
                if line.startswith("n"):
                    cwd = Path(line[1:]).resolve()
                    break
        except Exception:
            cwd = None
        try:
            cmd_result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
            command = (cmd_result.stdout or "").strip()
        except Exception:
            command = ""
        return LocalDaemonProcess(pid=pid, cwd=cwd, command=command)

    def _current_project_owns_port_8787(self) -> bool:
        info = self._describe_local_daemon_process()
        if info is None or info.cwd is None:
            return False
        return info.cwd == PROJECT_DIR

    def _wait_for_port_8787_to_clear(self, attempts: int = 10, delay_sec: float = 0.5) -> bool:
        for _ in range(attempts):
            time.sleep(delay_sec)
            if self._find_listener_pid(8787) is None:
                return True
        return self._find_listener_pid(8787) is None

    def _stop_foreign_daemon_on_8787(self) -> bool:
        info = self._describe_local_daemon_process()
        if info is None:
            return False
        if info.cwd == PROJECT_DIR:
            return False
        self.write_log(
            "На порту 8787 найден чужой демон от другого проекта.\n"
            f"PID: {info.pid}\n"
            f"CWD: {info.cwd or 'не удалось определить'}\n"
            "Останавливаю его, чтобы поднять текущий проект.\n"
        )
        try:
            os.kill(info.pid, signal.SIGINT)
        except ProcessLookupError:
            return True
        except Exception as exc:
            self.write_log(f"Не смог остановить чужой демон автоматически: {exc}\n")
            return False
        if self._wait_for_port_8787_to_clear():
            return True
        try:
            os.kill(info.pid, signal.SIGTERM)
        except Exception:
            pass
        time.sleep(1.0)
        return self._find_listener_pid(8787) is None

    def _stop_current_project_daemon_on_8787(self) -> bool:
        info = self._describe_local_daemon_process()
        if info is None:
            self.write_log("На порту 8787 нет живого демона текущего проекта.\n")
            return True
        if info.cwd != PROJECT_DIR:
            self.write_log(
                "На порту 8787 сейчас не текущий проект, а другой процесс.\n"
                "Для жёсткого рестарта этого проекта сначала освобожу порт обычным сценарием запуска.\n"
            )
            return self._stop_foreign_daemon_on_8787()
        self.write_log(
            "Перезапускаю текущий демон проекта на порту 8787.\n"
            f"PID: {info.pid}\n"
        )
        try:
            os.kill(info.pid, signal.SIGINT)
        except ProcessLookupError:
            return True
        except Exception as exc:
            self.write_log(f"Не смог остановить текущий демон автоматически: {exc}\n")
            return False
        if self._wait_for_port_8787_to_clear():
            return True
        try:
            os.kill(info.pid, signal.SIGTERM)
        except Exception:
            pass
        time.sleep(1.0)
        return self._find_listener_pid(8787) is None

    def _restart_daemon_worker(self) -> None:
        if not self.agent_token_is_safe():
            self.explain_unsafe_token()
            return
        self._tunnel_restart_count = self._tunnel_max_restarts
        self._stop_process(self.tunnel_proc, "туннель")
        self.tunnel_proc = None
        self.last_url = None
        self._tunnel_blocked_reason = None
        self._last_tunnel_failure = None
        self._recovering_tunnel = False
        self._public_check_failures = 0
        self.tunnel_url.set("Туннель: не запущен")
        if self.agent_proc is not None and self.agent_proc.poll() is None:
            self._stop_process(self.agent_proc, "демон")
            self.agent_proc = None
        if not self._stop_current_project_daemon_on_8787():
            self.write_log("Не смог освободить порт 8787 для жёсткого рестарта демона.\n")
            return
        self._using_external_daemon = False
        self.agent_status.set("Демон: перезапуск...")
        self.write_log("Поднимаю новый процесс демона для текущего проекта...\n")
        self._tunnel_restart_count = 0
        self._last_tunnel_failure = None
        self._start_all_worker()

    def _start_all_worker(self) -> None:
        # --- Daemon ---
        if self.agent_proc and self.agent_proc.poll() is None:
            self.write_log("Демон уже запущен.\n")
        elif not self.agent_token_is_safe():
            self.explain_unsafe_token()
            return
        elif self._local_daemon_ready() and not self._current_project_owns_port_8787():
            if not self._stop_foreign_daemon_on_8787():
                self.write_log(
                    "Не смог освободить порт 8787 от старого проекта.\n"
                    "Закрой старый демон вручную и нажми «Запустить» ещё раз.\n"
                )
                return
        elif self._local_daemon_ready():
            self._using_external_daemon = True
            self.write_log("На 127.0.0.1:8787 уже отвечает живой демон. Использую его и не запускаю второй экземпляр.\n")
        else:
            if not self.ensure_uvicorn():
                return
            env = self.load_env()
            self._using_external_daemon = False
            self.write_log("Запускаю демона на http://127.0.0.1:8787 ...\n")
            self.agent_proc = subprocess.Popen(
                [str(self.uvicorn_bin()), "app.main:app", "--host", "127.0.0.1", "--port", "8787"],
                cwd=PROJECT_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            threading.Thread(target=self._stream_process, args=(self.agent_proc, "agent"), daemon=True).start()
            time.sleep(1.5)
            if self.agent_proc.poll() is not None and self._local_daemon_ready():
                self.agent_proc = None
                self._using_external_daemon = True
                self.write_log("Новый процесс демона не закрепился, но локальный health уже отвечает. Продолжаю с существующим демоном.\n")

        # --- Tunnel ---
        self._start_tunnel()

    def _start_tunnel(self) -> None:
        if self.tunnel_proc and self.tunnel_proc.poll() is None:
            self.write_log("Туннель уже запущен.\n")
            return

        ok, detail = self._preflight_tunnel_check()
        if not ok:
            self.write_log(f"Не запускаю туннель: {detail}\n")
            return

        domain = self.ngrok_domain()
        public_url = f"https://{domain}"
        self._tunnel_blocked_reason = None
        self._last_tunnel_failure = None
        self.write_log(f"Запускаю ngrok туннель → {public_url} ...\n")
        ngrok_bin = self.ngrok_bin()
        if not ngrok_bin:
            self.write_log("Не запускаю туннель: ngrok не найден. Запусти установщик Second Lane ещё раз.\n")
            return

        self.tunnel_proc = subprocess.Popen(
            [ngrok_bin, "http", "8787", f"--url={domain}", "--log=stdout", "--log-format=logfmt"],
            cwd=PROJECT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        threading.Thread(target=self._stream_ngrok, args=(self.tunnel_proc,), daemon=True).start()

    def _stream_ngrok(self, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        tunnel_ready = False
        captured_lines: list[str] = []
        for line in proc.stdout:
            captured_lines.append(line)
            if len(captured_lines) > 40:
                captured_lines.pop(0)
            # Show important lines in log, skip noisy ones
            if any(k in line for k in ("msg=", "err=", "lvl=warn", "lvl=err")):
                short = line.strip()
                if len(short) > 200:
                    short = short[:200] + "..."
                self.write_log(f"[ngrok] {short}\n")

            if NGROK_BLOCKED_IP_ERROR in line:
                self._last_tunnel_failure = self._classify_ngrok_output(line)
                self._tunnel_blocked_reason = self._describe_tunnel_failure(self._last_tunnel_failure)
                self.tunnel_url.set("Туннель: ngrok заблокировал IP")
                self.write_log(
                    "ngrok не пустил агент с текущего IP (ERR_NGROK_9040).\n"
                    "Простыми словами: токен и проект в порядке, но сам сервис ngrok "
                    "не разрешает подключение из этой сети/IP.\n"
                    "Что поможет: другая сеть, другой внешний IP, VPN/VPS вне заблокированного диапазона.\n"
                )

            # Detect tunnel is up
            if "started tunnel" in line or "url=https://" in line:
                domain = self.ngrok_domain()
                self.last_url = f"https://{domain}"
                self.tunnel_url.set(f"Туннель: {self.last_url}")
                self.update_openapi_url(self.last_url)
                self.write_log(f"Туннель активен: {self.last_url}\n")
                self.write_log("URL обновлён в openapi.gpts.yaml. Теперь этот файл можно импортировать в GPT Actions.\n")
                tunnel_ready = True
                threading.Thread(target=self._validate_tunnel_after_start, daemon=True).start()

        # Process exited — tunnel is dead
        exit_code = proc.poll()
        if self._tunnel_blocked_reason:
            self.last_url = None
            return
        if not tunnel_ready:
            failure_text = "".join(captured_lines)
            self._last_tunnel_failure = self._classify_ngrok_output(failure_text)
            detail = self._describe_tunnel_failure(self._last_tunnel_failure)
            self.last_url = None
            self.tunnel_url.set("Туннель: ошибка запуска")
            self.write_log(f"Туннель не поднялся: {detail}\n")
            self._schedule_tunnel_recovery(self._last_tunnel_failure)
            return
        if tunnel_ready or self.last_url:
            self.write_log(f"ngrok завершился (exit code: {exit_code})\n")
            self.last_url = None
            self.tunnel_url.set("Туннель: упал")
            self._last_tunnel_failure = TunnelFailure(
                code="process_crashed",
                summary=f"ngrok завершился с кодом {exit_code}",
                recoverable=True,
            )
            self._schedule_tunnel_recovery(self._last_tunnel_failure)

    def _validate_tunnel_after_start(self) -> None:
        if not self.last_url:
            return
        tunnel_ok, detail = self._check_public_gpts_ready()
        self.write_log(f"Автопроверка туннеля: {'OK ✓' if tunnel_ok else detail}\n")
        if not tunnel_ok:
            self.write_log(f"Туннель поднялся, но проверка не прошла: {detail}\n")

    def update_openapi_url(self, url: str) -> None:
        for openapi_file in OPENAPI_FILES:
            if not openapi_file.exists():
                continue
            text = openapi_file.read_text("utf-8")
            text = re.sub(r"  - url: https://[^\n]+", f"  - url: {url}", text, count=1)
            openapi_file.write_text(text, "utf-8")

    def stop_all(self) -> None:
        self._tunnel_restart_count = self._tunnel_max_restarts  # prevent auto-restart during shutdown
        self._stop_process(self.tunnel_proc, "туннель")
        if self.agent_proc is not None:
            self._stop_process(self.agent_proc, "демон")
        elif self._using_external_daemon:
            self.write_log("Внешний демон оставляю запущенным: панель его не запускала.\n")
        self.tunnel_proc = None
        self.agent_proc = None
        self._using_external_daemon = False
        self.last_url = None
        self._tunnel_blocked_reason = None
        self._last_tunnel_failure = None
        self._recovering_tunnel = False
        self._public_check_failures = 0
        self.tunnel_url.set("Туннель: не запущен")
        self.agent_status.set("Демон: не запущен")

    def _stop_process(self, proc: subprocess.Popen | None, label: str) -> None:
        if not proc or proc.poll() is not None:
            return
        self.write_log(f"Останавливаю {label}...\n")
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=5)

    # --- Health checks ---

    def check_now(self) -> None:
        threading.Thread(target=self._check_worker, daemon=True).start()

    def _check_worker(self) -> None:
        local_ok, local_detail = self._url_ok(f"{LOCAL_URL}/health")
        self.write_log(f"Локальный демон: {'OK ✓' if local_ok else local_detail}\n")
        if self.last_url:
            tunnel_ok, tunnel_detail = self._check_public_gpts_ready()
            self.write_log(f"Публичный URL: {'OK ✓' if tunnel_ok else tunnel_detail}\n")
        elif self._tunnel_blocked_reason:
            self.write_log(f"Публичный URL: {self._tunnel_blocked_reason}\n")
        elif self._last_tunnel_failure:
            self.write_log(f"Публичный URL: {self._describe_tunnel_failure(self._last_tunnel_failure)}\n")
        else:
            self.write_log("Туннель: не запущен\n")

    def _schedule_tunnel_recovery(self, failure: TunnelFailure | None) -> None:
        if self._recovering_tunnel:
            return
        if failure and not failure.recoverable:
            self.write_log(f"Автовосстановление остановлено: {self._describe_tunnel_failure(failure)}\n")
            return
        if self._tunnel_restart_count >= self._tunnel_max_restarts:
            self.write_log("Автовосстановление остановлено: достигнут лимит попыток.\n")
            return
        self._tunnel_restart_count += 1
        delay = RECOVERY_BACKOFF_STEPS_SEC[min(self._tunnel_restart_count - 1, len(RECOVERY_BACKOFF_STEPS_SEC) - 1)]
        self._recovering_tunnel = True
        self.tunnel_url.set("Туннель: восстановление...")
        self.write_log(
            f"Пробую восстановить туннель ({self._tunnel_restart_count}/{self._tunnel_max_restarts}) через {delay} сек...\n"
        )
        threading.Thread(target=self._recover_tunnel_worker, args=(delay,), daemon=True).start()

    def _recover_tunnel_worker(self, delay: int) -> None:
        try:
            time.sleep(delay)
            daemon_alive = self._local_daemon_ready()
            if not daemon_alive:
                self.write_log("Перед восстановлением туннеля локальный демон не отвечает. Пробую поднять всё заново.\n")
                self._start_all_worker()
                return
            self._stop_process(self.tunnel_proc, "туннель")
            self.tunnel_proc = None
            self.last_url = None
            self._public_check_failures = 0
            self._start_tunnel()
        finally:
            self._recovering_tunnel = False

    def _verify_public_url_in_background(self) -> None:
        if self._public_check_running or not self.last_url:
            return
        self._public_check_running = True
        threading.Thread(target=self._public_check_worker, daemon=True).start()

    def _public_check_worker(self) -> None:
        try:
            tunnel_ok, tunnel_detail = self._check_public_gpts_ready()
            if tunnel_ok:
                if self._public_check_failures > 0:
                    self.write_log("Публичный URL снова отвечает.\n")
                self._public_check_failures = 0
                return
            self._public_check_failures += 1
            self.write_log(
                f"Проверка публичного URL не прошла ({self._public_check_failures}/{PUBLIC_CHECK_MAX_FAILURES}): {tunnel_detail}\n"
            )
            if self._public_check_failures >= PUBLIC_CHECK_MAX_FAILURES:
                self._last_tunnel_failure = TunnelFailure(
                    code="public_probe_failed",
                    summary=f"публичный URL не отвечает: {tunnel_detail}",
                    recoverable=True,
                )
                self._schedule_tunnel_recovery(self._last_tunnel_failure)
        finally:
            self._last_public_check_ts = time.time()
            self._public_check_running = False

    def _check_public_gpts_ready(self) -> tuple[bool, str]:
        if not self.last_url:
            return False, "нет URL туннеля"
        return self._url_ok(
            f"{self.last_url}/v1/capabilities",
            attempts=TUNNEL_HEALTH_ATTEMPTS,
            delay_sec=TUNNEL_HEALTH_DELAY_SEC,
            expect_json_key="workspace",
        )

    def _url_ok(
        self,
        url: str,
        attempts: int = 1,
        delay_sec: float = 0.0,
        expect_json_key: str | None = None,
    ) -> tuple[bool, str]:
        last_error = "не отвечает"
        ssl_context = ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()
        for attempt in range(1, attempts + 1):
            try:
                request = urllib.request.Request(url)
                token = self.agent_token()
                if token:
                    request.add_header("Authorization", f"Bearer {token}")
                # ngrok free tier shows interstitial page to browsers;
                # setting a non-browser User-Agent + ngrok-skip-browser-warning header bypasses it.
                request.add_header("User-Agent", "GPTAgent/1.0")
                request.add_header("ngrok-skip-browser-warning", "true")
                with urllib.request.urlopen(request, timeout=TUNNEL_HEALTH_TIMEOUT_SEC, context=ssl_context) as response:
                    body = response.read(2000).decode("utf-8", errors="replace")
                    if not (200 <= response.status < 300):
                        last_error = f"HTTP {response.status}"
                    elif expect_json_key:
                        try:
                            payload = json.loads(body)
                        except json.JSONDecodeError:
                            last_error = "ответ не похож на JSON (возможно interstitial-страница ngrok)"
                        else:
                            if expect_json_key in payload:
                                return True, "OK"
                            last_error = f"нет поля {expect_json_key}"
                    else:
                        return True, "OK"
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", None)
                last_error = f"ошибка сети: {reason or exc}"
            except TimeoutError:
                last_error = "таймаут"

            if attempt < attempts:
                time.sleep(delay_sec)
        return False, last_error

    # --- Monitoring: auto-restart tunnel if it dies ---

    def _poll_status(self) -> None:
        # Daemon status
        if self.agent_proc and self.agent_proc.poll() is None:
            self.agent_status.set("Демон: работает на http://127.0.0.1:8787")
        elif self._using_external_daemon and self._local_daemon_ready() and self._current_project_owns_port_8787():
            self.agent_status.set("Демон: уже запущен на http://127.0.0.1:8787")
        elif self._local_daemon_ready() and not self._current_project_owns_port_8787():
            self._using_external_daemon = False
            self.agent_status.set("Демон: на порту 8787 висит другой проект")
        else:
            self._using_external_daemon = False
            self.agent_status.set("Демон: не запущен")

        # Tunnel auto-restart: if daemon is alive but tunnel died, restart tunnel
        daemon_alive = (self.agent_proc and self.agent_proc.poll() is None) or self._using_external_daemon
        tunnel_dead = self.tunnel_proc is None or self.tunnel_proc.poll() is not None
        if (
            daemon_alive
            and tunnel_dead
            and self.last_url is None
            and self._tunnel_blocked_reason is None
            and not self._recovering_tunnel
        ):
            if self.tunnel_proc is not None:
                self._schedule_tunnel_recovery(self._last_tunnel_failure)

        tunnel_alive = self.tunnel_proc is not None and self.tunnel_proc.poll() is None and self.last_url is not None
        if tunnel_alive and (time.time() - self._last_public_check_ts) >= PUBLIC_CHECK_INTERVAL_SEC:
            self._verify_public_url_in_background()

        self.root.after(TUNNEL_MONITOR_INTERVAL_MS, self._poll_status)

    # --- Clipboard ---

    def copy_url(self) -> None:
        if not self.last_url:
            self.write_log("URL ещё нет. Сначала нажми «Запустить».\n")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.last_url)
        self.write_log(f"Скопировал URL: {self.last_url}\n")

    def copy_log(self) -> None:
        data = self.log.get("1.0", END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(data)
        self.write_log("Скопировал журнал в буфер обмена.\n")

    def open_env_file(self) -> None:
        if not ENV_FILE.exists():
            self.write_log(f"Файл не найден: {ENV_FILE}\n")
            return
        try:
            if shutil.which("open"):
                subprocess.Popen(["open", str(ENV_FILE)], cwd=PROJECT_DIR)
                self.write_log(f"Открыл файл настроек: {ENV_FILE}\n")
            else:
                self.write_log(
                    "Не нашёл системную команду open. Открой этот файл вручную:\n"
                    f"{ENV_FILE}\n"
                )
        except Exception as exc:
            self.write_log(
                "Не смог открыть файл автоматически.\n"
                f"Открой его вручную: {ENV_FILE}\n"
                f"Техническая причина: {exc}\n"
            )

    # --- Lifecycle ---

    def on_close(self) -> None:
        self.stop_all()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    panel = ControlPanel()
    if "--auto-start" in sys.argv or os.environ.get("SECOND_LANE_AUTO_START") == "1":
        panel.root.after(500, panel.start_all)
    panel.run()
