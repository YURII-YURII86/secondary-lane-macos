# DEPLOY

Second Lane by **Yurii Slepnev** · Apache-2.0  
Telegram: https://t.me/yurii_yurii86 · YouTube: https://youtube.com/@yurii_yurii86 · Instagram: https://instagram.com/yurii_yurii86

## Локальный режим

Подтверждённый рабочий путь для проекта — запуск из панели `gpts_agent_control.py`.

### Требования

- Python 3.13 для проектного окружения
- ngrok
- заполненный `.env`
- для repo-local verify/test/smoke-скриптов основной путь окружения — `.venv`
- если используешь Docker Compose на macOS, при необходимости задай `HOST_PROJECTS_DIR` в `.env` или shell

### Минимальный запуск

```bash
cd "$(dirname "$0")"
python3.13 gpts_agent_control.py
```

Или двойным кликом по `Запустить Second Lane.command`.

### Что делает панель

- поднимает локальный daemon на `127.0.0.1:8787`
- использует repo-local `.venv`
- поднимает туннель ngrok
- обновляет URL в `openapi.gpts.yaml`
- даёт операторский UI для статуса и проверки
- умеет жёстко перезапускать daemon текущего проекта

## После изменения action-set

Если менялся GPT-facing action-set или `openapi.gpts.yaml`, операторский порядок такой:

1. перезапустить daemon
2. убедиться, что поднялся именно текущий проект
3. заново импортировать `openapi.gpts.yaml` в GPT Actions
4. прогнать smoke-check ключевых actions

## Серверный режим

В проекте есть шаблоны для `systemd` и `nginx`:

- `deploy/systemd/universal-flex-agent.service`
- `deploy/nginx/default.conf`

Их нужно адаптировать под фактический путь установки на сервере.

## Важно

- для `pydantic==2.9.2` локальная установка на Python 3.14 не считается надёжной
- если нужен чистый setup, создавай `.venv` на Python 3.13
- verify/test/smoke-скрипты используют repo-local `.venv`
