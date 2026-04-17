# Codex Skills — Second Lane macOS

Скиллы для **OpenAI Codex** (ChatGPT с Codex-режимом).

> Если ты используешь **Claude Code** (Anthropic) — смотри папку
> [`../claude-skills/`](../claude-skills/README.md).

## Что здесь

| Папка | Для чего |
|---|---|
| `gpts-mac-autopilot/` | Почти автоматическая установка Second Lane через Codex |

## Как использовать

1. Скопируй папку `gpts-mac-autopilot` в каталог skills своего Codex
2. Скажи Codex:

```text
Установи мне Second Lane на Mac по skill-у gpts-mac-autopilot.
Делай всё сам, останавливайся только там, где нужен мой логин,
регистрация, капча, подтверждение почты, оплата или системное разрешение.
```

## Что Codex делает сам

- проверяет структуру проекта
- проверяет Python 3.13 и ngrok
- помогает собрать `.env`
- поднимает панель и тоннель
- проверяет `openapi.gpts.yaml`
- проводит через сборку GPT в ChatGPT

## Что Codex не делает без тебя

- регистрация / логин в ngrok и ChatGPT
- капча, подтверждение почты, оплата
- системные разрешения macOS

## Ручная инструкция

Без Codex или для проверки шагов руками:
[`docs/MAC_FIRST_START.md`](../docs/MAC_FIRST_START.md)
