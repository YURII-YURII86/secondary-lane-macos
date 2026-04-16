# SECOND LANE GPT PACKAGE

Second Lane by **Yurii Slepnev** · Apache-2.0  
Telegram: https://t.me/yurii_yurii86 · YouTube: https://youtube.com/@yurii_yurii86 · Instagram: https://instagram.com/yurii_yurii86

В этой папке лежат файлы, которые нужны для сборки и настройки Custom GPT.

## Что важно

- `system_instructions.txt` — основная системная инструкция GPT
- `knowledge/` — knowledge-pack
- `openapi.gpts.yaml` — curated compact OpenAPI schema для GPT Actions

## Что сейчас считается сильным action-set

В GPT schema намеренно выставлены сильные workflow actions:

- `safePatchAndVerifyProjectFile`
- `applyPatch`
- `multiFilePatchAndVerify`
- `runTest`
- `analyzeProjectBuildFailure`
- `runProjectServiceAndSmokeCheck`

Слабые browser/GUI convenience actions не считаются обязательной частью GPT-facing набора.

## Минимальная настройка GPT

1. Открой локальную панель и подними текущий daemon.
2. Импортируй `openapi.gpts.yaml` в GPT Actions.
3. Укажи bearer token из `.env`.
4. Вставь `gpts/system_instructions.txt` в instructions.
5. Загрузи `gpts/knowledge/` в Knowledge.
6. Проверь первые вызовы `getCapabilities`, `inspectProject`, `runTest`.
