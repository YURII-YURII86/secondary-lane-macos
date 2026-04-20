#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import queue
import re
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tkinter import END, LEFT, RIGHT, BOTH, X, Y
from tkinter import ttk
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from ui_brand import (
    BRAND_AUTHOR,
    BRAND_COPYRIGHT,
    BRAND_INSTALLER_BLURB,
    BRAND_LICENSE,
    BRAND_LINKS,
    BRAND_NAME,
    BRAND_PRODUCT,
    BRAND_TAGLINE,
    PALETTE,
    open_external,
)
from runtime_paths import resolve_project_dir


PROJECT_DIR = resolve_project_dir(__file__)
ENV_EXAMPLE_FILE = PROJECT_DIR / ".env.example"
ENV_FILE = PROJECT_DIR / ".env"
STATE_FILE = PROJECT_DIR / ".installer_state.json"
VENV_DIR = PROJECT_DIR / ".venv"
TOOLS_DIR = PROJECT_DIR / "tools"
LOCAL_NGROK_BIN = TOOLS_DIR / "ngrok" / "ngrok"
REQUIREMENTS_FILE = PROJECT_DIR / "requirements.txt"
CONTROL_PANEL_FILE = PROJECT_DIR / "gpts_agent_control.py"
CONNECT_GUIDE_FILE = PROJECT_DIR / "CONNECT_GPT_ACTIONS_RU.md"
NGROK_SIGNUP_URL = "https://dashboard.ngrok.com/signup"
NGROK_AUTHTOKEN_URL = "https://dashboard.ngrok.com/get-started/your-authtoken"
NGROK_DOMAINS_URL = "https://dashboard.ngrok.com/cloud-edge/domains"
NGROK_DIRECT_DOWNLOADS = {
    "x86_64": "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-amd64.zip",
    "amd64": "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-amd64.zip",
    "arm64": "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-arm64.zip",
    "aarch64": "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-arm64.zip",
}
INTERNET_CHECK_URLS = (
    "https://www.apple.com/library/test/success.html",
    "https://www.google.com/generate_204",
    "https://chatgpt.com",
    "https://raw.githubusercontent.com",
)
TRANSIENT_DOWNLOAD_ERRORS = (
    "download failed",
    "ssl_error_syscall",
    "ssl_connect",
    "failed to connect",
    "connection reset",
    "connection refused",
    "network is unreachable",
    "operation timed out",
    "timed out",
    "could not resolve host",
    "curl: (35)",
    "curl: (56)",
    "curl: (7)",
    "curl: (6)",
)

MIN_FREE_BYTES = 2 * 1024 * 1024 * 1024
WEAK_TOKENS = {
    "",
    "change-me",
    "changeme",
    "default",
    "token",
    "secret",
    "password",
    "example",
    "replace-this-with-a-long-random-secret-token",
    "long-random-secret-token-please-use-your-own-value",
}
WEAK_TOKEN_WORDS = ("change", "default", "example", "password", "replace", "secret", "token")
TOKEN_REGEX = re.compile(r"^[0-9a-f]{64}$")

STATUS_ICON = {
    "pending": "○",
    "running": "⟳",
    "done": "✓",
    "action": "!",
    "error": "✕",
}

STATUS_TEXT = {
    "pending": "Ожидание",
    "running": "В процессе",
    "done": "Готово",
    "action": "Нужно действие человека",
    "error": "Ошибка",
}

NGROK_DOMAIN_REGEX = re.compile(r"^[A-Za-z0-9-]+\.(?:ngrok-free\.dev|ngrok\.app)$")
PLACEHOLDER_NGROK_DOMAINS = {
    "your-domain.ngrok-free.dev",
    "example.ngrok-free.dev",
    "something.ngrok-free.dev",
}


def token_is_safe(token: str) -> bool:
    cleaned = token.strip()
    lowered = cleaned.lower()
    if len(cleaned) < 32:
        return False
    if lowered in WEAK_TOKENS:
        return False
    if len(set(cleaned)) <= 4:
        return False
    if any(word in lowered for word in WEAK_TOKEN_WORDS):
        return False
    return bool(TOKEN_REGEX.fullmatch(cleaned))


def normalize_ngrok_token(raw: str) -> str:
    cleaned = raw.strip()
    if not cleaned:
        return ""
    if "ngrok config add-authtoken" in cleaned:
        cleaned = cleaned.split("ngrok config add-authtoken", 1)[1].strip()
    if cleaned.startswith("NGROK_AUTHTOKEN="):
        cleaned = cleaned.split("=", 1)[1].strip()
    parts = cleaned.split()
    if len(parts) > 1:
        cleaned = parts[-1]
    return cleaned.strip().strip("'\"")


def internet_available() -> bool:
    for url in INTERNET_CHECK_URLS:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Second Lane Installer"})
            response = urllib.request.urlopen(request, timeout=8)
            if hasattr(response, "close"):
                response.close()
            return True
        except (OSError, TimeoutError, urllib.error.URLError):
            continue
    return False


@dataclass(frozen=True)
class StepSpec:
    key: str
    title: str
    description: str
    why: str


STEP_SPECS: list[StepSpec] = [
    StepSpec(
        "system_check",
        "Проверка системы",
        "Проверяю, что это Mac, есть интернет, место на диске и можно писать файлы в эту папку.",
        "Так мы заранее ловим простые проблемы, а не оставляем тебя с непонятной ошибкой в середине установки.",
    ),
    StepSpec(
        "homebrew",
        "Homebrew — установщик программ",
        "Проверяю Homebrew. Это обычный установщик программ для Mac, как App Store, только для технических инструментов.",
        "Через Homebrew мастер сам поставит всё нужное, чтобы тебе не искать команды вручную.",
    ),
    StepSpec(
        "python",
        "Python 3.13 — двигатель Second Lane",
        "Проверяю Python 3.13. Это программа, на которой запускается Second Lane.",
        "Без него панель Second Lane не сможет работать на твоём Mac.",
    ),
    StepSpec(
        "ngrok",
        "ngrok — безопасный адрес для связи",
        "Проверяю ngrok. Это программа, которая даёт ChatGPT временный защищённый адрес твоего локального Second Lane.",
        "Так ChatGPT сможет достучаться до Second Lane, даже если он работает у тебя на компьютере.",
    ),
    StepSpec(
        "ngrok_auth",
        "Вход в ngrok",
        "Проверяю ключ ngrok. Ключ подтверждает, что ngrok запускается от твоего аккаунта.",
        "Это один из немногих шагов, где нужен человек: нужно войти в ngrok и вставить ключ.",
    ),
    StepSpec(
        "project_env",
        "Файл настроек Second Lane",
        "Создаю файл настроек. В нём лежат адрес ngrok, секретный ключ доступа и список папок, к которым можно дать доступ.",
        "Мастер заполнит почти всё сам, тебе нужен только адрес ngrok из личного кабинета.",
    ),
    StepSpec(
        "python_env",
        "Локальная рабочая папка Python",
        "Создаю отдельную рабочую папку Python и ставлю туда нужные части проекта.",
        "Так Second Lane не мешает другим программам на Mac и запускается одинаково у разных людей.",
    ),
    StepSpec(
        "finish",
        "Готово",
        "Покажу, как запустить Second Lane и как подключить его к GPT в ChatGPT.",
        "Последние действия уже не про установку на Mac, а про подключение в интерфейсе ChatGPT.",
    ),
]


class StepActionRequired(Exception):
    def __init__(self, message: str, action_key: str) -> None:
        super().__init__(message)
        self.message = message
        self.action_key = action_key


class StepFailed(Exception):
    pass


class InstallerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"{BRAND_NAME} Installer")
        self.root.geometry("1320x820")
        self.root.minsize(1120, 720)
        self.root.configure(bg=PALETTE["app_bg"])
        self.style = ttk.Style(self.root)
        self.heading_font = self._native_font("TkDefaultFont", 8, "bold")
        self.section_font = self._native_font("TkDefaultFont", 4, "bold")
        self.body_font = self._native_font("TkDefaultFont", 0, "normal")
        self.body_bold_font = self._native_font("TkDefaultFont", 0, "bold")
        self.small_font = self._native_font("TkDefaultFont", -1, "normal")
        self.log_font = self._native_font("TkFixedFont", 0, None)
        self._configure_styles()

        self.worker_queue: queue.Queue[tuple[str, dict]] = queue.Queue()
        self.busy = False
        self.current_command = tk.StringVar(value="Внутреннее действие мастера: —")
        self.header_status = tk.StringVar(value="Подготовка")
        self.primary_button_text = tk.StringVar(value="Начать установку")
        self.secondary_button_text = tk.StringVar(value="Что это значит?")

        self.ngrok_token_var = tk.StringVar(value="")
        self.ngrok_domain_var = tk.StringVar(value="")
        self.workspace_root_var = tk.StringVar(value="")

        self.state = self._load_state()
        self.step_status: dict[str, str] = self.state["step_status"]
        self.current_step_index: int = self.state["current_step_index"]

        self._build_ui()
        self._refresh_step_list()
        self._refresh_step_panel()

        if self.state.get("inputs", {}).get("ngrok_domain"):
            self.ngrok_domain_var.set(self.state["inputs"]["ngrok_domain"])
        if self.state.get("inputs", {}).get("workspace_root"):
            self.workspace_root_var.set(self.state["inputs"]["workspace_root"])
        if not self.workspace_root_var.get().strip():
            self.workspace_root_var.set(self._workspace_root_for_ui())

        self.root.after(120, self._poll_worker_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._close_app)

    def run(self) -> None:
        self.root.mainloop()

    def _native_font(self, font_name: str, size_delta: int, weight: str | None) -> tuple[str, int, str]:
        base = tkfont.nametofont(font_name)
        family = str(base.actual("family"))
        size = int(base.actual("size")) + size_delta
        resolved_weight = str(weight or base.actual("weight"))
        return (family, max(size, 10), resolved_weight)

    def _configure_styles(self) -> None:
        try:
            self.style.theme_use("aqua")
        except tk.TclError:
            self.style.theme_use("clam")
        self.style.configure("App.TFrame", background=PALETTE["app_bg"])
        self.style.configure("Action.TButton", font=self.body_font, padding=(10, 4))
        self.style.configure("Link.TButton", font=self.small_font, padding=(2, 0))
        self.style.configure("Input.TEntry", fieldbackground=PALETTE["surface"], foreground=PALETTE["text"], bordercolor=PALETTE["border"], lightcolor=PALETTE["border"], darkcolor=PALETTE["border"], insertcolor=PALETTE["text"])

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, style="App.TFrame", padding=(18, 18, 18, 10))
        shell.pack(fill=BOTH, expand=True)

        hero = tk.Frame(shell, bg=PALETTE["surface"], highlightbackground=PALETTE["border"], highlightthickness=1, padx=20, pady=18)
        hero.pack(fill=X, pady=(0, 14))
        hero_left = tk.Frame(hero, bg=PALETTE["surface"])
        hero_left.pack(side=LEFT, fill=X, expand=True)
        tk.Label(
            hero_left,
            text="Установщик Second Lane",
            bg=PALETTE["surface"],
            fg=PALETTE["text"],
            font=self.heading_font,
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            hero_left,
            text="Мастер сам подготовит Mac и остановится только там, где нужен человек.",
            bg=PALETTE["surface"],
            fg=PALETTE["text"],
            font=self.body_font,
            justify=LEFT,
            anchor="w",
        ).pack(anchor="w", pady=(8, 0))
        hero_right = tk.Frame(hero, bg=PALETTE["surface"])
        hero_right.pack(side=RIGHT, anchor="ne")
        self.status_chip = tk.Label(
            hero_right,
            textvariable=self.header_status,
            bg=PALETTE["surface"],
            fg=PALETTE["text"],
            font=self.body_bold_font,
        )
        self.status_chip.pack(anchor="e")
        tk.Label(hero_right, text="Intel и Apple Silicon", bg=PALETTE["surface"], fg=PALETTE["muted"], font=self.small_font).pack(anchor="e", pady=(16, 0))

        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill=BOTH, expand=True)

        left = tk.Frame(body, bg=PALETTE["surface"], highlightbackground=PALETTE["border"], highlightthickness=1, padx=18, pady=18)
        left.pack(side=LEFT, fill=BOTH, expand=False, padx=(0, 14))
        tk.Label(left, text="Шаги", bg=PALETTE["surface"], fg=PALETTE["text"], font=self.section_font, anchor="w").pack(anchor="w")

        self.step_list = tk.Listbox(left, width=38, height=20, activestyle="none", exportselection=False, font=self.body_font)
        self.step_list.pack(fill=BOTH, expand=True, pady=(14, 0))
        self.step_list.configure(
            bg="#ffffff",
            fg=PALETTE["text"],
            bd=1,
            relief="flat",
            highlightthickness=1,
            highlightbackground=PALETTE["text"],
            highlightcolor=PALETTE["text"],
            selectbackground="#cfe3fb",
            selectforeground=PALETTE["text"],
        )

        right = tk.Frame(body, bg=PALETTE["app_bg"])
        right.pack(side=LEFT, fill=BOTH, expand=True)
        self.right_panel = right
        self.root.bind("<Configure>", self._sync_layout)
        tk.Label(right, text="Что сейчас делает мастер", bg=PALETTE["app_bg"], fg=PALETTE["text"], font=self.section_font, anchor="w").pack(anchor="w")

        self.step_title = tk.Label(right, text="", bg=PALETTE["app_bg"], fg=PALETTE["text"], font=self.section_font, justify=LEFT, anchor="w")
        self.step_title.pack(anchor="w", pady=(18, 0))
        self.step_desc = tk.Label(right, text="", bg=PALETTE["app_bg"], fg=PALETTE["text"], font=self.body_font, wraplength=760, justify=LEFT, anchor="w")
        self.step_desc.pack(anchor="w", pady=(10, 0))
        self.step_why = tk.Label(right, text="", bg=PALETTE["app_bg"], fg=PALETTE["text"], font=self.small_font, wraplength=760, justify=LEFT, anchor="w")
        self.step_why.pack(anchor="w", pady=(10, 0))

        self.action_hint_box = tk.Frame(right, bg=PALETTE["app_bg"])
        self.action_hint_title = tk.Label(
            self.action_hint_box,
            text="Что нужно сделать:",
            bg=PALETTE["app_bg"],
            fg=PALETTE["text"],
            font=self.body_bold_font,
            anchor="w",
        )
        self.action_hint_title.pack(anchor="w")
        self.action_hint = tk.Label(
            self.action_hint_box,
            text="",
            bg=PALETTE["app_bg"],
            fg=PALETTE["text"],
            font=self.body_font,
            wraplength=760,
            justify=LEFT,
            anchor="w",
        )
        self.action_hint.pack(anchor="w", pady=(6, 0))

        self.input_frame = tk.Frame(right, bg=PALETTE["app_bg"])
        self.input_frame.pack(fill=X, pady=(8, 6))

        self.ngrok_token_row = tk.Frame(self.input_frame, bg=PALETTE["app_bg"])
        tk.Label(self.ngrok_token_row, text="Ключ ngrok:", bg=PALETTE["app_bg"], fg=PALETTE["text"], font=self.body_font).pack(side=LEFT, padx=(0, 8))
        self.ngrok_token_entry = ttk.Entry(self.ngrok_token_row, textvariable=self.ngrok_token_var, show="•", width=52, style="Input.TEntry")
        self.ngrok_token_entry.pack(side=LEFT, fill=X, expand=True)
        self._bind_entry_shortcuts(self.ngrok_token_entry)
        ttk.Button(self.ngrok_token_row, text="Вставить", style="Action.TButton", command=self._paste_ngrok_token_from_clipboard).pack(side=LEFT, padx=(8, 0))

        self.ngrok_domain_row = tk.Frame(self.input_frame, bg=PALETTE["app_bg"])
        tk.Label(self.ngrok_domain_row, text="Адрес ngrok:", bg=PALETTE["app_bg"], fg=PALETTE["text"], font=self.body_font).pack(side=LEFT, padx=(0, 8))
        self.ngrok_domain_entry = ttk.Entry(self.ngrok_domain_row, textvariable=self.ngrok_domain_var, width=52, style="Input.TEntry")
        self.ngrok_domain_entry.pack(side=LEFT, fill=X, expand=True)
        self._bind_entry_shortcuts(self.ngrok_domain_entry)
        ttk.Button(self.ngrok_domain_row, text="Вставить", style="Action.TButton", command=self._paste_ngrok_domain_from_clipboard).pack(side=LEFT, padx=(8, 0))

        self.workspace_row = tk.Frame(self.input_frame, bg=PALETTE["app_bg"])
        tk.Label(self.workspace_row, text="Рабочая папка:", bg=PALETTE["app_bg"], fg=PALETTE["text"], font=self.body_font).pack(side=LEFT, padx=(0, 8))
        self.workspace_entry = ttk.Entry(self.workspace_row, textvariable=self.workspace_root_var, width=52, style="Input.TEntry")
        self.workspace_entry.pack(side=LEFT, fill=X, expand=True)
        self._bind_entry_shortcuts(self.workspace_entry)
        ttk.Button(self.workspace_row, text="Выбрать папку", style="Action.TButton", command=self._choose_workspace_directory).pack(side=LEFT, padx=(8, 0))

        button_row = tk.Frame(right, bg=PALETTE["app_bg"])
        button_row.pack(fill=X, pady=(18, 8))
        self.button_row = button_row
        self.primary_btn = ttk.Button(button_row, textvariable=self.primary_button_text, style="Action.TButton", command=self._on_primary)
        self.primary_btn.pack(side=LEFT)
        self.secondary_btn = ttk.Button(button_row, textvariable=self.secondary_button_text, style="Action.TButton", command=self._on_secondary)
        self.secondary_btn.pack(side=LEFT, padx=(10, 0))
        self.reset_btn = ttk.Button(button_row, text="Начать заново", style="Action.TButton", command=self._reset_state)
        self.reset_btn.pack(side=LEFT, padx=(10, 0))
        self.close_btn = ttk.Button(button_row, text="Закрыть и продолжить позже", style="Action.TButton", command=self._close_app)
        self.close_btn.pack(side=LEFT, padx=(18, 0))

        self.command_label = tk.Label(
            right,
            textvariable=self.current_command,
            bg=PALETTE["app_bg"],
            fg=PALETTE["text"],
            font=self.body_bold_font,
            justify=LEFT,
            anchor="w",
            wraplength=760,
        )
        self.command_label.pack(anchor="w", pady=(12, 0))

        log_row = tk.Frame(right, bg=PALETTE["app_bg"])
        log_row.pack(fill=X, pady=(18, 0))
        tk.Label(log_row, text="Подробности установки", bg=PALETTE["app_bg"], fg=PALETTE["text"], font=self.section_font, anchor="w").pack(side=LEFT)
        ttk.Button(log_row, text="Скопировать лог", style="Action.TButton", command=self._copy_log).pack(side=RIGHT)

        self.log_text = ScrolledText(
            right,
            height=18,
            wrap="word",
            font=self.log_font,
            bg="#ffffff",
            fg=PALETTE["text"],
            relief="solid",
            borderwidth=1,
            insertbackground=PALETTE["text"],
        )
        self.log_text.pack(fill=BOTH, expand=True, pady=(8, 0))
        self.log_text.configure(highlightthickness=1, highlightbackground=PALETTE["border"], highlightcolor=PALETTE["border"])
        self._log(
            "Добро пожаловать в установщик Second Lane.\n"
            "Нажми «Начать установку». Мастер будет показывать, что делает, и остановится только там, где нужно твоё действие.\n"
            "Важно: ничего не нужно вводить в Terminal вручную. Если откроется окно Terminal, просто смотри на него и следуй подсказкам установщика.\n"
        )

        footer = ttk.Frame(shell, style="App.TFrame", padding=(2, 8, 2, 0))
        footer.pack(fill=X)
        footer_left = tk.Frame(footer, bg=PALETTE["app_bg"])
        footer_left.pack(side=LEFT)
        tk.Label(
            footer_left,
            text=f"{BRAND_AUTHOR} · {BRAND_COPYRIGHT}",
            bg=PALETTE["app_bg"],
            fg=PALETTE["muted"],
            font=self.small_font,
            anchor="w",
        ).pack(anchor="w")
        footer_right = ttk.Frame(footer, style="App.TFrame")
        footer_right.pack(side=RIGHT)
        for link in BRAND_LINKS:
            ttk.Button(footer_right, text=link.label, style="Link.TButton", command=lambda url=link.url: open_external(url)).pack(side=LEFT, padx=(8, 0))
        self.root.after_idle(self._sync_layout)

    def _sync_layout(self, _event=None) -> None:
        if not hasattr(self, "right_panel"):
            return
        right_width = max(self.right_panel.winfo_width() - 40, 420)
        wrap_width = max(right_width - 20, 380)
        self.step_desc.configure(wraplength=wrap_width)
        self.step_why.configure(wraplength=wrap_width)
        self.action_hint.configure(wraplength=wrap_width)
        self.command_label.configure(wraplength=wrap_width)

    def _load_state(self) -> dict:
        default = {
            "current_step_index": 0,
            "step_status": {step.key: "pending" for step in STEP_SPECS},
            "inputs": {"ngrok_domain": "", "workspace_root": ""},
        }
        if not STATE_FILE.exists():
            return default
        try:
            parsed = json.loads(STATE_FILE.read_text("utf-8"))
        except Exception:
            return default
        state = default.copy()
        state["current_step_index"] = int(parsed.get("current_step_index", 0))
        state["inputs"] = {
            "ngrok_domain": str(parsed.get("inputs", {}).get("ngrok_domain", "")),
            "workspace_root": str(parsed.get("inputs", {}).get("workspace_root", "")),
        }
        loaded_status = parsed.get("step_status", {})
        for step in STEP_SPECS:
            state["step_status"][step.key] = loaded_status.get(step.key, "pending")
        return state

    def _save_state(self) -> None:
        payload = {
            "current_step_index": self.current_step_index,
            "step_status": self.step_status,
            "inputs": {
                "ngrok_domain": self.ngrok_domain_var.get().strip(),
                "workspace_root": self.workspace_root_var.get().strip(),
            },
        }
        STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")

    def _refresh_step_list(self) -> None:
        self.step_list.delete(0, END)
        for idx, step in enumerate(STEP_SPECS):
            status = self.step_status.get(step.key, "pending")
            icon = STATUS_ICON.get(status, "○")
            line = f"{icon} {idx + 1}. {step.title} — {STATUS_TEXT.get(status, 'Ожидание')}"
            self.step_list.insert(END, line)
        self.step_list.selection_clear(0, END)
        if 0 <= self.current_step_index < len(STEP_SPECS):
            self.step_list.selection_set(self.current_step_index)
            self.step_list.see(self.current_step_index)

    def _refresh_step_panel(self) -> None:
        idx = min(max(self.current_step_index, 0), len(STEP_SPECS) - 1)
        step = STEP_SPECS[idx]
        status = self.step_status.get(step.key, "pending")

        self.step_title.configure(text=f"{idx + 1}. {step.title}")
        self.step_desc.configure(text=step.description)
        self.step_why.configure(text=f"Зачем: {step.why}")
        self.header_status.set(f"Шаг {idx + 1} из {len(STEP_SPECS)}")

        self.ngrok_token_row.pack_forget()
        self.ngrok_domain_row.pack_forget()
        self.workspace_row.pack_forget()
        self.action_hint.configure(text="")
        self.action_hint_box.pack_forget()

        if status == "action":
            self.action_hint_box.pack(fill=X, pady=(10, 8), before=self.input_frame)
            if step.key == "ngrok_auth":
                self.action_hint.configure(
                    text=(
                        "Нужно одно ручное действие: получить ключ ngrok и вставить его в поле ниже.\n"
                        "Если аккаунта ngrok нет, нажми «Открыть ngrok и получить ключ». Откроется сайт ngrok: создай бесплатный аккаунт через Google, GitHub или email.\n"
                        "После входа открой страницу Your Authtoken, скопируй длинный ключ и вставь его сюда. В Terminal ничего вставлять не нужно."
                    )
                )
                self.ngrok_token_row.pack(fill=X, pady=2)
                self.primary_button_text.set("Сохранить ключ")
                self.secondary_button_text.set("Открыть ngrok и получить ключ")
            elif step.key == "project_env":
                self.action_hint.configure(
                    text=(
                        "Вставь адрес ngrok. Он выглядит примерно так: my-name.ngrok-free.dev.\n"
                        "Если адреса ещё нет, нажми «Открыть адреса ngrok». В кабинете ngrok создай бесплатный статический адрес, скопируй только домен без https:// и вставь сюда.\n"
                        "Ниже выбери рабочую папку. Агент сможет работать только внутри неё, а не по всему Mac.\n"
                        "Этот адрес нужен, чтобы ChatGPT всегда знал, куда обращаться на твоём Mac."
                    )
                )
                self.ngrok_domain_row.pack(fill=X, pady=2)
                if not self.workspace_root_var.get().strip():
                    self.workspace_root_var.set(self._workspace_root_for_ui())
                self.workspace_row.pack(fill=X, pady=(8, 2))
                self.primary_button_text.set("Сохранить адрес")
                self.secondary_button_text.set("Открыть адреса ngrok")
            else:
                self.primary_button_text.set("Исправить автоматически")
                self.secondary_button_text.set("Что это значит?")
        elif step.key == "finish" and status == "done":
            self.primary_button_text.set("Запустить Second Lane")
            self.secondary_button_text.set("Открыть памятку GPT")
            self.action_hint_box.pack(fill=X, pady=(10, 8), before=self.input_frame)
            self.action_hint.configure(
                text=(
                    "Установка на Mac завершена. Нажми «Запустить Second Lane», чтобы открыть панель управления.\n"
                    "Потом открой памятку GPT: там простыми шагами написано, что нажать в ChatGPT и какие файлы выбрать."
                )
            )
        else:
            if status == "error":
                self.primary_button_text.set("Проверить снова")
            elif idx == 0 and status == "pending":
                self.primary_button_text.set("Начать установку")
            elif status in {"pending", "action"}:
                self.primary_button_text.set("Продолжить")
            else:
                self.primary_button_text.set("Продолжить")
            self.secondary_button_text.set("Что это значит?")

        if self.busy:
            self.primary_btn.state(["disabled"])
            self.secondary_btn.state(["disabled"])
            self.reset_btn.state(["disabled"])
        else:
            self.primary_btn.state(["!disabled"])
            self.secondary_btn.state(["!disabled"])
            self.reset_btn.state(["!disabled"])

        self._refresh_step_list()

    def _set_current_command(self, text: str) -> None:
        self.current_command.set(f"Внутреннее действие мастера: {text}")

    def _bind_entry_shortcuts(self, entry: ttk.Entry) -> None:
        for sequence in ("<Command-v>", "<Control-v>", "<<Paste>>"):
            entry.bind(sequence, self._paste_into_entry)
        for sequence in ("<Command-c>", "<Control-c>", "<<Copy>>"):
            entry.bind(sequence, self._copy_from_entry)
        for sequence in ("<Command-a>", "<Control-a>"):
            entry.bind(sequence, self._select_all_entry)

    def _paste_into_entry(self, event) -> str:
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            return "break"
        widget = event.widget
        self._replace_entry_selection(widget, text)
        return "break"

    def _copy_from_entry(self, event) -> str:
        widget = event.widget
        try:
            selected = widget.selection_get()
        except tk.TclError:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(selected)
        return "break"

    def _select_all_entry(self, event) -> str:
        widget = event.widget
        widget.selection_range(0, END)
        widget.icursor(END)
        return "break"

    def _replace_entry_selection(self, widget, text: str) -> None:
        try:
            start = widget.index("sel.first")
            end = widget.index("sel.last")
            widget.delete(start, end)
            insert_at = start
        except tk.TclError:
            insert_at = widget.index("insert")
        widget.insert(insert_at, text)
        widget.icursor(insert_at + len(text))

    def _clipboard_text(self) -> str:
        try:
            return self.root.clipboard_get()
        except tk.TclError:
            return ""

    def _paste_ngrok_token_from_clipboard(self) -> None:
        text = normalize_ngrok_token(self._clipboard_text())
        if not text:
            messagebox.showwarning(
                "Буфер обмена пуст",
                "Не вижу ключ ngrok в буфере обмена. Скопируй ключ на сайте ngrok и нажми «Вставить».",
            )
            return
        self.ngrok_token_var.set(text)
        self.ngrok_token_entry.focus_set()
        self.ngrok_token_entry.icursor(END)

    def _paste_ngrok_domain_from_clipboard(self) -> None:
        text = self._clipboard_text().strip()
        text = text.removeprefix("https://").removeprefix("http://").strip().strip("/")
        if not text:
            messagebox.showwarning(
                "Буфер обмена пуст",
                "Не вижу адрес ngrok в буфере обмена. Скопируй адрес на сайте ngrok и нажми «Вставить».",
            )
            return
        self.ngrok_domain_var.set(text)
        self.ngrok_domain_entry.focus_set()
        self.ngrok_domain_entry.icursor(END)

    def _choose_workspace_directory(self) -> None:
        initial_dir = self.workspace_root_var.get().strip() or str(Path.home() / "Documents")
        chosen = filedialog.askdirectory(
            title="Выбери рабочую папку для Second Lane",
            initialdir=initial_dir,
            mustexist=True,
        )
        if chosen:
            self.workspace_root_var.set(str(Path(chosen).expanduser().resolve()))

    def _log(self, text: str) -> None:
        self.log_text.insert(END, text)
        self.log_text.see(END)

    def _copy_log(self) -> None:
        data = self.log_text.get("1.0", END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(data)
        self._log("Лог скопирован в буфер обмена.\n")

    def _close_app(self) -> None:
        self._save_state()
        self.root.destroy()

    def _reset_state(self) -> None:
        if not messagebox.askyesno("Начать заново", "Сбросить прогресс установщика и начать заново?"):
            return
        self.current_step_index = 0
        self.step_status = {step.key: "pending" for step in STEP_SPECS}
        self.ngrok_token_var.set("")
        self.ngrok_domain_var.set("")
        self.workspace_root_var.set(self._workspace_root_for_ui())
        self._save_state()
        self._refresh_step_panel()
        self._log("\nПрогресс сброшен. Можно начать установку заново.\n")

    def _on_secondary(self) -> None:
        step = STEP_SPECS[self.current_step_index]
        status = self.step_status.get(step.key, "pending")
        if step.key == "ngrok_auth" and status == "action":
            subprocess.Popen(["open", NGROK_AUTHTOKEN_URL])
            return
        if step.key == "project_env" and status == "action":
            subprocess.Popen(["open", NGROK_DOMAINS_URL])
            return
        if step.key == "finish" and status == "done":
            if CONNECT_GUIDE_FILE.exists():
                subprocess.Popen(["open", str(CONNECT_GUIDE_FILE)])
            else:
                subprocess.Popen(["open", "https://chatgpt.com/gpts/editor"])
            return
        messagebox.showinfo(
            "Что происходит",
            f"{step.title}\n\n{step.description}\n\nЗачем это нужно:\n{step.why}",
        )

    def _on_primary(self) -> None:
        if self.busy:
            return
        step = STEP_SPECS[self.current_step_index]
        status = self.step_status.get(step.key, "pending")

        if step.key == "ngrok_auth" and status == "action":
            token = normalize_ngrok_token(self.ngrok_token_var.get())
            if not token:
                messagebox.showwarning(
                    "Нужен ключ ngrok",
                    "Вставь ключ из кабинета ngrok. Если аккаунта ещё нет, нажми «Открыть ngrok и получить ключ» и создай бесплатный аккаунт.",
                )
                return
            self._run_async(self._action_save_ngrok_token, token)
            return

        if step.key == "project_env" and status == "action":
            domain = self.ngrok_domain_var.get().strip()
            if not self._valid_ngrok_domain(domain):
                messagebox.showwarning(
                    "Неверный адрес ngrok",
                    "Нужен адрес вида my-name.ngrok-free.dev. Его нужно создать или скопировать в кабинете ngrok.",
                )
                return
            workspace_root = self.workspace_root_var.get().strip()
            if not self._valid_workspace_root(workspace_root):
                messagebox.showwarning(
                    "Нужна рабочая папка",
                    "Выбери существующую папку на Mac. Агент будет читать и менять файлы только внутри неё.",
                )
                return
            self._run_async(self._action_save_env_domain, domain)
            return

        if step.key == "finish" and status == "done":
            self._launch_control_panel()
            return

        self._run_async(self._run_steps_until_blocked, self.current_step_index)

    def _run_async(self, fn, *args) -> None:
        self.busy = True
        self._refresh_step_panel()
        thread = threading.Thread(target=fn, args=args, daemon=True)
        thread.start()

    def _poll_worker_queue(self) -> None:
        while True:
            try:
                kind, payload = self.worker_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._log(payload["text"])
            elif kind == "command":
                self._set_current_command(payload["text"])
            elif kind == "step_status":
                key = payload["key"]
                self.step_status[key] = payload["status"]
                self.current_step_index = payload["index"]
                self._save_state()
            elif kind == "next_step":
                self.current_step_index = payload["index"]
                self._save_state()
            elif kind == "busy":
                self.busy = payload["value"]
            elif kind == "hint":
                self._log(payload["text"])
            elif kind == "clear_ngrok_token":
                self.ngrok_token_var.set("")
            elif kind == "set_ngrok_domain":
                self.ngrok_domain_var.set(payload["value"])

        self._refresh_step_panel()
        self.root.after(120, self._poll_worker_queue)

    def _emit(self, kind: str, **payload) -> None:
        self.worker_queue.put((kind, payload))

    def _execute_step_body(self, step_key: str) -> None:
        if step_key == "system_check":
            self._step_system_check()
        elif step_key == "homebrew":
            self._step_homebrew()
        elif step_key == "python":
            self._step_python()
        elif step_key == "ngrok":
            self._step_ngrok()
        elif step_key == "ngrok_auth":
            self._step_ngrok_auth()
        elif step_key == "project_env":
            self._step_project_env()
        elif step_key == "python_env":
            self._step_python_env()
        elif step_key == "finish":
            self._step_finish()

    def _run_step(self, step_index: int) -> None:
        step = STEP_SPECS[step_index]
        self._emit("step_status", key=step.key, status="running", index=step_index)
        self._emit("log", text=f"\n--- Шаг {step_index + 1}: {step.title} ---\n")
        try:
            self._execute_step_body(step.key)
        except StepActionRequired as exc:
            self._emit("step_status", key=step.key, status="action", index=step_index)
            self._emit("hint", text=f"{exc.message}\n")
            self._emit("busy", value=False)
            return
        except StepFailed as exc:
            self._emit("step_status", key=step.key, status="error", index=step_index)
            self._emit("hint", text=f"Ошибка: {exc}\n")
            self._emit("busy", value=False)
            return
        except Exception as exc:
            self._emit("step_status", key=step.key, status="error", index=step_index)
            self._emit("hint", text=f"Неожиданная ошибка: {exc}\n")
            self._emit("busy", value=False)
            return

        self._emit("step_status", key=step.key, status="done", index=step_index)
        if step_index + 1 < len(STEP_SPECS):
            self._emit("next_step", index=step_index + 1)
            self._emit("hint", text=f"Шаг «{step.title}» завершён.\n")
        self._emit("busy", value=False)

    def _run_steps_until_blocked(self, start_index: int) -> None:
        step_index = start_index
        while step_index < len(STEP_SPECS):
            step = STEP_SPECS[step_index]
            self._emit("step_status", key=step.key, status="running", index=step_index)
            self._emit("log", text=f"\n--- Шаг {step_index + 1}: {step.title} ---\n")
            try:
                self._execute_step_body(step.key)
            except StepActionRequired as exc:
                self._emit("step_status", key=step.key, status="action", index=step_index)
                self._emit("hint", text=f"{exc.message}\n")
                self._emit("busy", value=False)
                return
            except StepFailed as exc:
                self._emit("step_status", key=step.key, status="error", index=step_index)
                self._emit("hint", text=f"Ошибка: {exc}\n")
                self._emit("busy", value=False)
                return
            except Exception as exc:
                self._emit("step_status", key=step.key, status="error", index=step_index)
                self._emit("hint", text=f"Неожиданная ошибка: {exc}\n")
                self._emit("busy", value=False)
                return

            self._emit("step_status", key=step.key, status="done", index=step_index)
            self._emit("hint", text=f"Шаг «{step.title}» завершён.\n")
            step_index += 1
            if step_index < len(STEP_SPECS):
                self._emit("next_step", index=step_index)
        self._emit("busy", value=False)

    def _action_save_ngrok_token(self, token: str) -> None:
        try:
            token = normalize_ngrok_token(token)
            if not token:
                raise StepFailed("Ключ ngrok пустой. Открой страницу ngrok, скопируй ключ и вставь его полностью.")
            ngrok_bin = self._find_ngrok_bin()
            if not ngrok_bin:
                raise StepFailed("Программа ngrok не найдена. Вернись к шагу установки ngrok и нажми «Продолжить».")
            self._run_command([ngrok_bin, "config", "add-authtoken", token])
            if not self._has_ngrok_auth():
                raise StepFailed("Ключ ngrok не сохранился. Скопируй его из кабинета ngrok ещё раз и вставь полностью.")
            self._check_ngrok_config(ngrok_bin)
            self._emit("clear_ngrok_token")
            self._emit("hint", text="Ключ ngrok сохранён. Теперь мастер может проверить связь с твоим аккаунтом ngrok.\n")
            self._emit("step_status", key="ngrok_auth", status="done", index=self.current_step_index)
            next_index = min(self.current_step_index + 1, len(STEP_SPECS) - 1)
            self._emit("next_step", index=next_index)
            self._run_steps_until_blocked(next_index)
            return
        except Exception as exc:
            self._emit("step_status", key="ngrok_auth", status="error", index=self.current_step_index)
            self._emit("hint", text=f"Не удалось сохранить ключ ngrok: {exc}\n")
        self._emit("busy", value=False)

    def _action_save_env_domain(self, domain: str) -> None:
        try:
            self._prepare_env_file()
            self._upsert_env("NGROK_DOMAIN", domain)
            self._upsert_env("WORKSPACE_ROOTS", self._normalized_workspace_roots())
            token = self._read_env_value("AGENT_TOKEN")
            if not token_is_safe(token):
                self._upsert_env("AGENT_TOKEN", self._generate_token())
            self._emit("hint", text="Адрес ngrok сохранён в файл настроек Second Lane.\n")
            self._emit("step_status", key="project_env", status="done", index=self.current_step_index)
            next_index = min(self.current_step_index + 1, len(STEP_SPECS) - 1)
            self._emit("next_step", index=next_index)
            self._run_steps_until_blocked(next_index)
            return
        except Exception as exc:
            self._emit("step_status", key="project_env", status="error", index=self.current_step_index)
            self._emit("hint", text=f"Не удалось сохранить адрес ngrok: {exc}\n")
        self._emit("busy", value=False)

    def _step_system_check(self) -> None:
        if platform.system() != "Darwin":
            raise StepFailed("Этот установщик рассчитан на macOS.")
        if not internet_available():
            raise StepFailed(
                "Не получилось проверить интернет. Если сайты в браузере открываются, нажми «Проверить снова». "
                "Если ошибка повторится, скопируй лог и покажи тому, кто помогает с установкой."
            )
        total, used, free = shutil.disk_usage(PROJECT_DIR)
        _ = total, used
        if free < MIN_FREE_BYTES:
            raise StepFailed("Недостаточно места. Нужно минимум 2 ГБ свободно.")
        if not os.access(PROJECT_DIR, os.W_OK):
            raise StepFailed("Mac не даёт записывать файлы в папку проекта. Перемести папку в Documents или разреши доступ.")
        self._emit("hint", text="Система готова: это Mac, интернет работает, место на диске есть, папка доступна.\n")

    def _step_homebrew(self) -> None:
        brew = self._find_brew_bin()
        if brew:
            self._emit("hint", text=f"Homebrew уже установлен. Это установщик программ для Mac. Путь: {brew}\n")
            return
        self._emit("hint", text="Homebrew не найден. Мастер попробует установить его автоматически, чтобы дальше поставить нужные программы.\n")
        script = 'NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        self._run_command(["/bin/bash", "-c", script])
        brew = self._find_brew_bin()
        if not brew:
            raise StepFailed("Homebrew не появился после установки. Открой brew.sh, установи Homebrew вручную и запусти мастер снова.")
        self._emit("hint", text=f"Homebrew установлен. Теперь мастер может ставить нужные программы сам. Путь: {brew}\n")

    def _step_python(self) -> None:
        py = self._find_python_bin()
        if py:
            self._emit("hint", text=f"Python 3.13 уже готов. Это двигатель Second Lane. Путь: {py}\n")
            return
        brew = self._require_brew()
        self._run_command([brew, "install", "python@3.13"])
        py = self._find_python_bin()
        if not py:
            raise StepFailed("Python 3.13 не найден после установки. Закрой и снова открой установщик, чтобы Mac обновил список программ.")
        self._emit("hint", text=f"Python 3.13 установлен. Это двигатель Second Lane. Путь: {py}\n")

    def _step_ngrok(self) -> None:
        ngrok = self._find_ngrok_bin()
        if ngrok:
            self._emit("hint", text=f"ngrok уже установлен. Он даёт адрес, по которому ChatGPT сможет обратиться к Second Lane. Путь: {ngrok}\n")
            return
        self._install_ngrok_direct()
        ngrok = self._find_ngrok_bin()
        if not ngrok:
            raise StepFailed("ngrok не найден после установки. Нажми «Проверить снова».")
        self._emit("hint", text=f"ngrok установлен. Он даст адрес для связи ChatGPT с Second Lane. Путь: {ngrok}\n")

    def _install_ngrok_direct(self) -> None:
        machine = platform.machine().lower()
        url = NGROK_DIRECT_DOWNLOADS.get(machine)
        if not url:
            raise StepFailed(f"Не понял тип процессора Mac: {machine or 'неизвестно'}. Скопируй лог и покажи тому, кто помогает с установкой.")

        install_dir = LOCAL_NGROK_BIN.parent
        download_dir = TOOLS_DIR / "downloads"
        archive_path = download_dir / "ngrok.zip"
        install_dir.mkdir(parents=True, exist_ok=True)
        download_dir.mkdir(parents=True, exist_ok=True)

        self._emit(
            "hint",
            text=(
                "Скачиваю ngrok напрямую с официального сервера ngrok. "
                "Это обходит проблемную установку через Homebrew на этом Mac.\n"
            ),
        )
        last_error = ""
        for attempt in range(1, 4):
            try:
                self._emit("log", text=f"\nСкачивание ngrok: попытка {attempt} из 3\n")
                request = urllib.request.Request(url, headers={"User-Agent": "Second Lane Installer"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    archive_path.write_bytes(response.read())
                with zipfile.ZipFile(archive_path) as archive:
                    member = next((name for name in archive.namelist() if Path(name).name == "ngrok"), "")
                    if not member:
                        raise StepFailed("В архиве ngrok не найден файл запуска.")
                    extracted = archive.extract(member, install_dir)
                extracted_path = Path(extracted)
                if extracted_path != LOCAL_NGROK_BIN:
                    shutil.move(str(extracted_path), str(LOCAL_NGROK_BIN))
                LOCAL_NGROK_BIN.chmod(0o755)
                archive_path.unlink(missing_ok=True)
                self._run_command([str(LOCAL_NGROK_BIN), "version"])
                return
            except Exception as exc:
                last_error = str(exc)
                if attempt < 3:
                    self._emit("hint", text="Скачивание ngrok оборвалось. Мастер попробует ещё раз.\n")
                    time.sleep(3)
                    continue
        raise StepFailed(
            "Не получилось скачать ngrok напрямую. "
            "Если сайты открываются, нажми «Проверить снова». "
            f"Техническая деталь: {last_error}"
        )

    def _step_ngrok_auth(self) -> None:
        ngrok = self._find_ngrok_bin()
        if not ngrok:
            raise StepFailed("Программа ngrok не найдена. Сначала пройди шаг установки ngrok.")
        if self._has_ngrok_auth():
            self._check_ngrok_config(ngrok)
            self._emit("hint", text="Ключ ngrok уже настроен и прошёл проверку.\n")
            return
        raise StepActionRequired(
            "Ключ ngrok не найден. Вставь ключ в поле ниже и нажми «Сохранить ключ».",
            action_key="ngrok_auth",
        )

    def _step_project_env(self) -> None:
        self._prepare_env_file()
        current_domain = self._read_env_value("NGROK_DOMAIN")
        if not self._valid_ngrok_domain(current_domain):
            if current_domain:
                self._emit("set_ngrok_domain", value=current_domain)
            raise StepActionRequired(
                "Нужен корректный адрес ngrok. Пример: my-name.ngrok-free.dev.",
                action_key="project_env",
            )

        token = self._read_env_value("AGENT_TOKEN")
        if not token_is_safe(token):
            self._upsert_env("AGENT_TOKEN", self._generate_token())
            self._emit("hint", text="Создал новый секретный ключ доступа для Second Lane. Он защищает панель от чужих запросов.\n")

        self._upsert_env("WORKSPACE_ROOTS", self._normalized_workspace_roots())
        self._emit("hint", text=f"Файл настроек готов. Техническое имя файла: {ENV_FILE}\n")

    def _step_python_env(self) -> None:
        py = self._find_python_bin()
        if not py:
            raise StepFailed("Не найден Python 3.13.")
        if not VENV_DIR.exists():
            self._run_command([py, "-m", "venv", str(VENV_DIR)])
        vpy = VENV_DIR / "bin" / "python"
        if not vpy.exists():
            raise StepFailed("Не удалось создать отдельную рабочую папку Python для Second Lane.")
        self._run_command([str(vpy), "-m", "pip", "install", "--upgrade", "pip"])
        self._run_command([str(vpy), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])
        self._run_command([str(vpy), "-c", "import fastapi,uvicorn;print('deps-ok')"])
        self._emit("hint", text="Локальная рабочая папка Python готова, нужные части проекта установлены.\n")

    def _step_finish(self) -> None:
        self._emit(
            "hint",
            text=(
                "Готово. Теперь можно запускать панель Second Lane.\n"
                "После запуска открой памятку GPT: там написано, что нажать в ChatGPT, чтобы подключить Second Lane.\n"
            ),
        )

    def _run_command(self, argv: list[str], attempts: int = 1) -> str:
        cmd_text = " ".join(argv)
        self._emit("command", text=cmd_text)
        last_output = ""
        last_code = 0
        for attempt in range(1, max(attempts, 1) + 1):
            if attempts > 1:
                self._emit("log", text=f"\nПопытка {attempt} из {attempts}: {cmd_text}\n")
            else:
                self._emit("log", text=f"$ {cmd_text}\n")
            env = os.environ.copy()
            env.setdefault("HOMEBREW_NO_ENV_HINTS", "1")
            proc = subprocess.Popen(
                argv,
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            output: list[str] = []
            assert proc.stdout is not None
            for line in proc.stdout:
                output.append(line)
                self._emit("log", text=line)
            last_code = proc.wait()
            last_output = "".join(output)
            if last_code == 0:
                return last_output
            if attempt < attempts and self._is_transient_download_error(last_output):
                self._emit(
                    "hint",
                    text=(
                        "Скачивание оборвалось. Это бывает даже при рабочем интернете. "
                        "Мастер сам попробует ещё раз.\n"
                    ),
                )
                time.sleep(3)
                continue
            break
        raise StepFailed(self._friendly_command_error(argv, last_code, last_output))

    def _is_transient_download_error(self, output: str) -> bool:
        lowered = output.lower()
        return any(marker in lowered for marker in TRANSIENT_DOWNLOAD_ERRORS)

    def _friendly_command_error(self, argv: list[str], code: int, output: str) -> str:
        command = " ".join(argv)
        lowered = output.lower()
        if "xcode-select" in lowered or "command line tools" in lowered:
            return (
                "Mac просит установить Apple Command Line Tools. "
                "Дождись системного окна установки, заверши его и нажми «Продолжить» ещё раз."
            )
        if "permission denied" in lowered or "operation not permitted" in lowered:
            return "Не хватило прав доступа. Закрой лишние окна, запусти установщик снова и введи пароль Mac, если он спросит. В Terminal ничего вручную вводить не нужно."
        if self._is_transient_download_error(output):
            if "ngrok" in command.lower() or "bin.ngrok.com" in lowered:
                return (
                    "Не получилось скачать ngrok: интернет есть, но сервер скачивания ngrok оборвал соединение. "
                    "Нажми «Проверить снова». Если ошибка повторится несколько раз, скопируй лог и покажи тому, кто помогает с установкой."
                )
            return "Похоже, соединение оборвалось во время скачивания. Нажми «Проверить снова». В Terminal ничего вводить не нужно."
        if "already in use" in lowered:
            return "Нужный порт уже занят другой программой. Закрой старую панель Second Lane и повтори шаг."
        if "invalid authtoken" in lowered or "authentication failed" in lowered:
            return "ngrok не принял ключ. Скопируй ключ из кабинета ngrok полностью и вставь его в поле установщика снова. В Terminal ничего вставлять не нужно."
        if "no such file or directory" in lowered:
            return f"Не найден нужный файл или программа для команды: {command}"
        return f"Команда не завершилась успешно (код {code}). Подробности видны в живом логе ниже."

    def _find_brew_bin(self) -> str | None:
        direct = shutil.which("brew")
        if direct:
            return direct
        for candidate in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
            if Path(candidate).exists():
                return candidate
        return None

    def _require_brew(self) -> str:
        brew = self._find_brew_bin()
        if not brew:
            raise StepFailed("Homebrew не найден.")
        return brew

    def _find_python_bin(self) -> str | None:
        direct = shutil.which("python3.13")
        if direct:
            return direct
        brew = self._find_brew_bin()
        if brew:
            try:
                prefix = subprocess.check_output([brew, "--prefix", "python@3.13"], text=True).strip()
            except Exception:
                prefix = ""
            if prefix:
                candidate = Path(prefix) / "bin" / "python3.13"
                if candidate.exists():
                    return str(candidate)
        return None

    def _find_ngrok_bin(self) -> str | None:
        if LOCAL_NGROK_BIN.exists():
            return str(LOCAL_NGROK_BIN)
        direct = shutil.which("ngrok")
        if direct:
            return direct
        for candidate in ("/opt/homebrew/bin/ngrok", "/usr/local/bin/ngrok"):
            if Path(candidate).exists():
                return candidate
        return None

    def _detect_ngrok_config_files(self) -> list[Path]:
        home = Path.home()
        return [
            home / ".config" / "ngrok" / "ngrok.yml",
            home / "Library" / "Application Support" / "ngrok" / "ngrok.yml",
        ]

    def _has_ngrok_auth(self) -> bool:
        for cfg in self._detect_ngrok_config_files():
            if not cfg.exists():
                continue
            try:
                text = cfg.read_text("utf-8")
            except Exception:
                continue
            if re.search(r"^\s*authtoken\s*:\s*.+$", text, flags=re.MULTILINE):
                return True
        return False

    def _check_ngrok_config(self, ngrok_bin: str) -> None:
        try:
            self._run_command([ngrok_bin, "config", "check"])
        except StepFailed as exc:
            raise StepFailed(f"ngrok token найден, но конфиг не прошёл проверку. {exc}") from exc

    def _prepare_env_file(self) -> None:
        if ENV_FILE.exists():
            return
        if not ENV_EXAMPLE_FILE.exists():
            raise StepFailed("Не найден файл .env.example")
        shutil.copyfile(ENV_EXAMPLE_FILE, ENV_FILE)
        self._emit("hint", text=".env создан из шаблона.\n")

    def _read_env_value(self, key: str) -> str:
        if not ENV_FILE.exists():
            return ""
        for raw_line in ENV_FILE.read_text("utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip()
        return ""

    def _upsert_env(self, key: str, value: str) -> None:
        lines: list[str] = []
        if ENV_FILE.exists():
            lines = ENV_FILE.read_text("utf-8").splitlines()
        replaced = False
        new_lines: list[str] = []
        for raw in lines:
            if raw.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                replaced = True
            else:
                new_lines.append(raw)
        if not replaced:
            new_lines.append(f"{key}={value}")
        ENV_FILE.write_text("\n".join(new_lines) + "\n", "utf-8")

    def _generate_token(self) -> str:
        return secrets.token_hex(32)

    def _normalized_workspace_roots(self) -> str:
        selected = self.workspace_root_var.get().strip()
        if self._valid_workspace_root(selected):
            return str(Path(selected).expanduser().resolve())
        current = self._read_env_value("WORKSPACE_ROOTS")
        if current and current != "/Users/your-name/Documents:/workspace:/projects":
            return current
        return str((Path.home() / "Documents").expanduser().resolve())

    def _workspace_root_for_ui(self) -> str:
        current = self._read_env_value("WORKSPACE_ROOTS")
        if current and current != "/Users/your-name/Documents:/workspace:/projects":
            first = current.split(":", 1)[0].strip()
            if first:
                return first
        return str((Path.home() / "Documents").expanduser().resolve())

    def _valid_workspace_root(self, path_text: str) -> bool:
        if not path_text.strip():
            return False
        try:
            candidate = Path(path_text).expanduser().resolve()
        except Exception:
            return False
        return candidate.exists() and candidate.is_dir()

    def _valid_ngrok_domain(self, domain: str) -> bool:
        cleaned = domain.strip().lower()
        if not cleaned or cleaned in PLACEHOLDER_NGROK_DOMAINS:
            return False
        return bool(NGROK_DOMAIN_REGEX.match(cleaned))

    def _launch_control_panel(self) -> None:
        py = str(VENV_DIR / "bin" / "python") if (VENV_DIR / "bin" / "python").exists() else self._find_python_bin()
        if not py:
            messagebox.showerror("Ошибка", "Не найден Python для запуска панели. Сначала пройди шаги установки.")
            return
        if not CONTROL_PANEL_FILE.exists():
            messagebox.showerror("Ошибка", f"Не найден файл: {CONTROL_PANEL_FILE}")
            return
        subprocess.Popen([py, str(CONTROL_PANEL_FILE), "--auto-start"], cwd=PROJECT_DIR)
        self._log("Панель Second Lane запущена в отдельном окне. Она сама нажмёт запуск и поднимет локальный сервер с ngrok-адресом.\n")


def main() -> None:
    app = InstallerApp()
    app.run()


if __name__ == "__main__":
    main()
