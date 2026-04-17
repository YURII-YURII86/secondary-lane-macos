# Claude Skills — Second Lane macOS

Скиллы для **Claude Code** (Anthropic CLI).

> Если ты используешь **OpenAI Codex** (ChatGPT) — смотри папку
> [`../codex-skills/`](../codex-skills/README.md).

## Что здесь

| Папка | Для чего |
|---|---|
| `mac-autopilot/` | Полностью автоматическая установка Second Lane через Claude Code |

## Ключевое отличие от Codex-скилла

Claude Code работает **локально** — он имеет прямой доступ к файловой
системе и терминалу. Поэтому этот скилл:

- **выполняет команды напрямую** (не объясняет как, а делает сам)
- **проверяет результат реально** через curl / python3
- **умеет устранять типовые ошибки** без участия пользователя

Человек нужен только в двух местах:
1. Логин / регистрация на ngrok.com (браузер)
2. Сборка GPT в редакторе ChatGPT (браузер)

## Как использовать

В Claude Code, находясь в папке проекта:

```text
Открой claude-skills/mac-autopilot/ENTRYPOINT.md и разверни
Second Lane на моём Mac полностью автоматически.
Делай максимум сам, останавливайся только там где физически
нужны мои руки. Говори по-русски.
```

Или одной командой сначала проверить состояние:

```bash
python3 claude-skills/mac-autopilot/scripts/run_preflight.py .
```

## Структура

```
mac-autopilot/
├── ENTRYPOINT.md              # Что читать первым
├── SKILL.md                   # Полная инструкция S0–S13
├── agents/
│   └── claude.yaml            # Конфиг агента
├── references/
│   ├── 01-state-machine.md    # Таблица состояний
│   ├── 02-verification-checklist.md
│   ├── 03-troubleshooting.md  # Ошибка → фикс
│   ├── 04-ngrok-guide.md      # Получить authtoken + домен
│   └── 05-chatgpt-builder.md  # Сборка GPT в ChatGPT
└── scripts/
    └── run_preflight.py       # Preflight: JSON-отчёт о состоянии всех компонентов
```

## Общие скрипты

Скрипты для работы с проектом лежат в `codex-skills/gpts-mac-autopilot/scripts/`
и используются обоими скиллами. Дублирования нет.
