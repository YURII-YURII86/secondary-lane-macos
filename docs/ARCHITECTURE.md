# ARCHITECTURE

Second Lane by **Yurii Slepnev** · Apache-2.0  
Telegram: https://t.me/yurii_yurii86 · YouTube: https://youtube.com/@yurii_yurii86 · Instagram: https://instagram.com/yurii_yurii86

## Коротко

Проект — это локальный action-backend для Custom GPT / GPT Actions.

Поток работы:

```text
Пользователь -> GPT -> GPT Actions -> openapi.gpts.yaml -> FastAPI (app/main.py) -> core modules -> local machine / ssh / http / files / project memory
```

## Главные слои

- `app/main.py` — HTTP API и маршруты
- `app/core/config.py` — загрузка окружения и runtime settings
- `app/core/security.py` — bearer auth
- `app/core/utils.py` — subprocess, поиск, diff, ограничения по путям
- `app/core/project_memory.py` — `.ai_context`, checkpoints, summary, rollback
- `app/core/providers.py` — загрузка optional provider manifests
- `gpts_agent_control.py` — локальная панель запуска демона и туннеля
- `openapi.gpts.yaml` — curated compact-контракт для GPT Actions

## GPT schema

Проект использует одну рабочую GPT schema:

- `openapi.gpts.yaml` оставляет только самые сильные и понятные GPT-facing actions

## Текущие сильные workflow actions в GPT schema

- `safePatchAndVerifyProjectFile`
- `applyPatch`
- `multiFilePatchAndVerify`
- `runTest`
- `analyzeProjectBuildFailure`
- `runProjectServiceAndSmokeCheck`

## Рабочий цикл

1. `getCapabilities`
2. `getProviders`
3. `inspectProject`
4. чтение релевантного контекста
5. минимальное действие
6. проверка результата
7. обновление `.ai_context`

## Ограничения

- доступ к файлам ограничен `WORKSPACE_ROOTS`
- все маршруты защищены bearer token
- SSH ограничен allowlist-хостами и allowlist-CIDR; неизвестные host keys не auto-accept и должны присутствовать в known_hosts
- compact GPT schema может быть уже backend schema по составу actions
- snapshot project memory намеренно компактнее полного `.ai_context/`, чтобы bootstrap/read actions не раздувались на длинной истории
