# Troubleshooting

Конкретные ошибки и конкретные фиксы. Без теории.

---

## Python

### `python3.13: command not found`

```bash
# Попробовать запасные
python3.12 --version || python3 --version

# Если есть Homebrew
brew install python@3.13

# Если нет ничего
open https://www.python.org/downloads/macos/
# → установить .pkg → потом снова python3.13 --version
```

### `python3.13 -m venv` упал с ошибкой ensurepip

```bash
# macOS иногда не включает ensurepip в системный Python
# Решение: скачать Python с python.org (включает pip)
open https://www.python.org/downloads/macos/
```

---

## pip / зависимости

### `pydantic-core: failed-wheel-build`

Причина: Python 3.14 не поддерживается pydantic-core.
Фикс: убедись что используешь 3.13, не 3.14:

```bash
.venv/bin/python --version   # должно быть 3.13.x
```

### `pip` зависает

```bash
.venv/bin/pip install --timeout 60 -r requirements.txt
```

### `ModuleNotFoundError` при запуске панели

```bash
# venv не создан или зависимости не установлены
.venv/bin/python -c "import fastapi"
# если ошибка — переустановить
.venv/bin/pip install -r requirements.txt
```

---

## Панель

### `Address already in use` (порт 8787)

```bash
# Найти и убить процесс
lsof -ti:8787 | xargs kill -9 2>/dev/null
sleep 2
# Перезапустить
```

### Панель запускается и сразу падает

```bash
# Посмотреть лог
tail -50 /tmp/secondlane_panel.log

# Запустить в foreground чтобы видеть ошибку
cd <branch_root>
.venv/bin/python gpts_agent_control.py
```

### `AGENT_TOKEN not set` / `WORKSPACE_ROOTS not found`

```bash
# .env не найден или неполный
python3 codex-skills/gpts-mac-autopilot/scripts/build_env.py . \
  --ngrok-domain "<your_domain>"
```

---

## ngrok

### `authtoken is required`

```bash
# Открыть dashboard и получить токен
open https://dashboard.ngrok.com/get-started/your-authtoken
# Потом:
ngrok config add-authtoken <token>
```

### `failed to start tunnel: domain not found` / `not reserved`

Причина: домен введён с опечаткой или не зарезервирован на аккаунте.

```bash
open https://dashboard.ngrok.com/domains
# Убедиться что домен есть в списке, скопировать точное имя
```

### ngrok запустился но URL не совпадает с `NGROK_DOMAIN` в .env

```bash
# Обновить .env и YAML с реальным URL
python3 codex-skills/gpts-mac-autopilot/scripts/build_env.py . \
  --ngrok-domain "<real_domain>"
```

### localhost:4040 не отвечает

ngrok не запущен или завис.

```bash
pkill -f "ngrok http" 2>/dev/null
sleep 1
nohup ngrok http 8787 --domain=<domain> &
sleep 4
curl http://localhost:4040/api/tunnels
```

---

## ChatGPT / Actions

### Ошибка 401 при тесте Preview

Причина: неправильно вставлен токен.

Проверить:
- Скопирован ли **только значение** из строки `AGENT_TOKEN=` (без самого `AGENT_TOKEN=`)
- Нет ли лишних пробелов или переносов строк
- Выбран ли тип `Bearer` (не `Basic`, не `None`)

```bash
# Проверить токен напрямую
TOKEN=$(grep '^AGENT_TOKEN=' <branch_root>/.env | cut -d= -f2)
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8787/v1/capabilities
# ожидается: {"ok": true, ...}
```

### Actions не принимает YAML — «invalid schema»

```bash
# Проверить что YAML валидный
python3 -c "import yaml; yaml.safe_load(open('<branch_root>/openapi.gpts.yaml').read()); print('VALID')"
```

### GPT вызывает не тот URL (старый localhost или placeholder)

```bash
# Проверить servers.url
grep -A2 "servers:" <branch_root>/openapi.gpts.yaml
# должно быть: - url: https://<реальный_домен>
```

---

## Права доступа на macOS

### `Permission denied` при запуске .command

```bash
chmod +x "Запустить Second Lane.command"
```

### macOS Gatekeeper блокирует ngrok

```bash
xattr -d com.apple.quarantine /usr/local/bin/ngrok 2>/dev/null
# или
spctl --add /usr/local/bin/ngrok
```
