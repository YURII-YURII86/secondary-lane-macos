from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class BrandLink:
    label: str
    url: str


BRAND_NAME = "Second Lane"
BRAND_PRODUCT = "Local GPT Runtime for Mac"
BRAND_AUTHOR = "Yurii Slepnev"
BRAND_COPYRIGHT = "Copyright (c) 2026 Yurii Slepnev"
BRAND_LICENSE = "Apache License 2.0"
BRAND_TAGLINE = "Аккуратный мост между ChatGPT и твоим Mac"
BRAND_INSTALLER_BLURB = "Установщик сам подготавливает Mac, объясняет шаги простыми словами и оставляет человеку только нужные действия."
BRAND_CONTROL_BLURB = "Панель запускает локальный демон и туннель, показывает состояние и помогает спокойно пройти путь до первого рабочего GPT."

BRAND_LINKS: tuple[BrandLink, ...] = (
    BrandLink("Telegram", "https://t.me/yurii_yurii86"),
    BrandLink("YouTube", "https://youtube.com/@yurii_yurii86"),
    BrandLink("Instagram", "https://instagram.com/yurii_yurii86"),
)

PALETTE = {
    "app_bg": "#eceff3",
    "surface": "#f8fafc",
    "panel": "#f2f4f7",
    "border": "#d6dbe3",
    "text": "#1f2937",
    "muted": "#6b7280",
    "accent": "#4b5563",
    "accent_deep": "#374151",
    "accent_soft": "#e8ecf1",
    "success": "#2c7a4b",
    "warning": "#495463",
    "shadow": "#e5e7eb",
}


def open_external(url: str) -> None:
    subprocess.Popen(["open", url])
