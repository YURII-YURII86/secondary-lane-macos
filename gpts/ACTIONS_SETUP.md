# ACTIONS SETUP

## Что импортировать

Импортируй `openapi.gpts.yaml` из корня проекта только после запуска панели Second Lane.

Правильный момент: в панели должна появиться строка `Туннель активен`, а ниже сообщение, что URL обновлён в `openapi.gpts.yaml`.

Если импортировать файл раньше, GPT может запомнить учебный адрес-заглушку и Actions будут долго ждать ответ.

## Важно про схему

`openapi.gpts.yaml` — единственный GPT-facing contract в этом проекте.

Именно по нему GPT должен работать в Actions.

## Аутентификация

Используй bearer token из `.env`:

```text
AGENT_TOKEN=...
```

## Python для локального контура

Подтверждённый локальный путь для этого проекта сейчас — `Python 3.13`.

Если готовишь окружение руками, используй:

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`Python 3.14` пока не считай рабочим вариантом для этого набора зависимостей.

## Что проверить после импорта

После импорта schema GPT должен уметь вызвать:

- `getCapabilities`
- `getProviders`
- `inspectProject`
- `runTest`

## Ключевые сильные actions

Текущий compact GPT action-set специально включает:

- `safePatchAndVerifyProjectFile`
- `applyPatch`
- `multiFilePatchAndVerify`
- `runTest`
- `analyzeProjectBuildFailure`
- `runProjectServiceAndSmokeCheck`
