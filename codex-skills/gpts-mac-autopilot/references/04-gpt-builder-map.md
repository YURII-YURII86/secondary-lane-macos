# GPT Builder Map

Используй это при проведении пользователя через редактор GPT в ChatGPT.

> **Пути:** ниже `<branch>/` — это корень ветки, который возвращает
> `discover_secondarylane_layout.py` / `_common.find_branch_root`.
> Не хардкодь `Версия для Мак/` — пользователь мог распаковать в
> `~/SecondLane/`, `Downloads/secondary-lane-macos/` или под любым
> другим именем. Всегда подставляй реальный обнаруженный путь перед
> тем, как показать его пользователю.

## Основной маппинг

| Источник | Куда в ChatGPT |
|---|---|
| `<branch>/gpts/system_instructions.txt` | поле `Instructions` |
| все `.md` из `<branch>/gpts/knowledge/` | раздел `Knowledge` |
| `<branch>/openapi.gpts.yaml` | раздел `Actions` |
| значение `AGENT_TOKEN` из `.env` | auth-поле `Actions` |

## Важные правила «не перепутай»

- `Instructions` — только текст из `system_instructions.txt`
- `Knowledge` — только файлы из `gpts/knowledge/`
- `Actions` — только содержимое `openapi.gpts.yaml`

Нельзя говорить пользователю:

- вставить knowledge-файлы в `Instructions`
- загрузить YAML в `Knowledge`
- вручную править YAML

## Auth map

### Что видит пользователь в ChatGPT

В редакторе GPT → `Actions` → `Authentication`:

- выбрать `API Key`
- `Auth Type` = `Bearer`
- `API Key` = **только значение токена** (строка после `AGENT_TOKEN=` в `.env`)

### Простое объяснение для пользователя

> «Bearer-токен — это просто пароль, который агент на твоём Mac ждёт
> в каждом запросе от ChatGPT. В `.env` он записан в виде
> `AGENT_TOKEN=длинная_строка`. В ChatGPT нужно вставить только эту
> длинную строку — без слова `Bearer`, без знака `=`, без кавычек.
> ChatGPT сам добавит `Bearer ` в начало при отправке».

Источник:

- значение справа от `=` в строке `AGENT_TOKEN=...` файла `.env`

Назначение:

- поле `API Key` при `Auth Type = Bearer`

Главное правило:

- вставлять **только** чистое значение токена

Исключение только если UI явно просит полный header:

- тогда `Bearer <token>` (ровно один пробел)

Никогда не вставлять:

- всю строку `AGENT_TOKEN=<token>` из `.env`
- токен в кавычках
- значение с пробелами или переносами строк в конце

## Первый тестовый вызов

Предпочтительно:

- попросить GPT вызвать `getCapabilities`

Это безопаснее, чем начинать с деструктивного или сложного action.
