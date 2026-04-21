# Second Lane for macOS

Second Lane подключает ChatGPT к выбранной папке на твоём Mac через GPT Actions.

Простыми словами: ты общаешься с GPT в ChatGPT, а Second Lane аккуратно выполняет разрешённые действия на твоём компьютере: смотрит файлы, правит код, запускает проверки и показывает результат.

Built by **Yurii Slepnev**.

Official links:
- Telegram: https://t.me/yurii_yurii86
- YouTube: https://youtube.com/@yurii_yurii86
- Instagram: https://instagram.com/yurii_yurii86

Copyright (c) 2026 Yurii Slepnev. Licensed under Apache-2.0.

## Что нужно

- Mac на Apple Silicon или Intel.
- Интернет.
- Аккаунт ngrok. Если его нет, установщик поможет открыть страницу регистрации.
- ChatGPT с возможностью создавать GPTs и Actions.

## Как установить

1. Скачай этот репозиторий как ZIP.
2. Распакуй ZIP.
3. Открой распакованную папку.
4. Дважды нажми `Установить Second Lane.command`.
5. Следуй окну установщика.

Важно: ничего не вводи в Terminal вручную. Если Terminal открылся, просто смотри на подсказки установщика.

## Если Mac блокирует запуск

Это обычная защита macOS для файлов, скачанных из интернета.

Сделай так:

1. Нажми правой кнопкой на `Установить Second Lane.command`.
2. Выбери `Открыть`.
3. Если Mac всё равно блокирует запуск, открой `System Settings` → `Privacy & Security`.
4. Нажми `Open Anyway` для Second Lane.
5. Снова открой файл через правый клик → `Открыть`.

## Что делает установщик

Установщик сам:

- проверяет Mac и интернет;
- готовит Python 3.13, если он нужен;
- скачивает правильный ngrok для Apple Silicon или Intel;
- создаёт безопасный ключ `AGENT_TOKEN`;
- просит выбрать рабочую папку;
- запускает панель Second Lane Control.

Рабочая папка — это папка, к которой GPT сможет обращаться. Second Lane не должен работать со всем Mac сразу.

## Как подключить GPT

После установки откроется панель `Second Lane Control`.

1. Нажми `Запустить`.
2. Дождись строки `Туннель активен`.
3. Убедись, что в журнале написано: URL обновлён в `openapi.gpts.yaml`.
4. Только после этого импортируй `openapi.gpts.yaml` в GPT Actions.
5. В GPT Actions укажи Bearer token из `.env`: это значение после `AGENT_TOKEN=`.
6. В инструкции GPT вставь содержимое `gpts/system_instructions.txt`.
7. В Knowledge загрузи файлы из `gpts/knowledge/`.

Подробная инструкция рядом:

`CONNECT_GPT_ACTIONS_RU.md`

Важно: не импортируй `openapi.gpts.yaml` прямо из GitHub до запуска панели. До запуска туннеля там учебный адрес-заглушка, и GPT Actions будут долго ждать ответ.

## Как запускать потом

После первой установки можно запускать:

`Запустить Second Lane.command`

Если что-то сломалось или нужно поменять настройки, снова запусти:

`Установить Second Lane.command`

## Что лежит в папке

- `Установить Second Lane.command` — первый запуск и настройка.
- `Запустить Second Lane.command` — запуск панели после установки.
- `app/` — локальный сервер Second Lane.
- `gpts/` — инструкции и knowledge-файлы для GPT.
- `openapi.gpts.yaml` — схема Actions для GPT.
- `.env.example` — пример файла настроек.

## Безопасность простыми словами

- Second Lane работает локально на твоём Mac.
- Доступ защищён секретным ключом `AGENT_TOKEN`.
- Рабочая папка выбирается человеком в установщике.
- Не публикуй свой `.env` и не отправляй никому `AGENT_TOKEN`.
