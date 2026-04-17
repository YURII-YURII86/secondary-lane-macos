# ChatGPT GPT Builder — пошаговое руководство

Используй на шагах S10–S11.

## Условия для этого шага

Перед тем как вести пользователя сюда — убедись:
- [ ] `openapi.gpts.yaml` содержит реальный ngrok URL
- [ ] Панель отвечает на `localhost:8787/v1/capabilities`
- [ ] Сквозной вызов через тоннель прошёл
- [ ] Пользователь залогинен в ChatGPT с подпиской (нужен ChatGPT Plus/Team/Pro)

---

## Создать новый GPT

1. Открыть `https://chatgpt.com/gpts/editor`
2. Нажать «Configure» (не «Create»)

---

## Поле Name

Любое название — например `Second Lane` или `Мой Mac агент`.

---

## Поле Instructions

Источник: `<branch_root>/gpts/system_instructions.txt`

```bash
cat <branch_root>/gpts/system_instructions.txt
```

Скажи пользователю:
> «Скопируй весь текст из этого файла и вставь в поле Instructions.»

---

## Knowledge

Источник: все `.md` файлы из `<branch_root>/gpts/knowledge/`

```bash
python3 codex-skills/gpts-mac-autopilot/scripts/export_gpt_materials.py <branch_root>
```

Скажи пользователю:
> «Загрузи все эти файлы в раздел Knowledge (кнопка Upload files).»

---

## Actions — вставить схему

1. В редакторе GPT → раздел «Actions» → «Create new action»
2. Нажать «Import from URL» или вставить вручную
3. Если вставлять вручную — скажи:
   > «Скопируй всё содержимое файла `openapi.gpts.yaml` и вставь в поле Schema.»

```bash
cat <branch_root>/openapi.gpts.yaml
```

4. Нажать «Format» — должна появиться таблица endpoints без ошибок

---

## Authentication

В том же разделе Actions → кнопка «Authentication»:

- Authentication Type: `API Key`
- Auth Type: `Bearer`
- API Key: **только значение токена** (всё что справа от `=` в строке `AGENT_TOKEN=...`)

```bash
# Показать только значение токена (без ключа)
grep '^AGENT_TOKEN=' <branch_root>/.env | cut -d= -f2
```

Скажи пользователю:
> «Скопируй эту строку целиком и вставь в поле API Key.
> Не добавляй слово Bearer — это делает ChatGPT сам.»

---

## Privacy Policy URL

Можно вставить любую ссылку — например `https://github.com/YURII-YURII86/secondary-lane-macos`.

---

## Тест в Preview

1. В правой части редактора — панель Preview
2. Написать: «Проверь соединение» или «Вызови getCapabilities»
3. GPT должен вернуть JSON-ответ от агента

**Что означает ошибка 401:** неправильно вставлен токен → проверить по `references/03-troubleshooting.md`

**Что означает timeout:** панель не запущена или тоннель упал → проверить S6/S7

---

## Сохранить GPT

После успешного теста в Preview:
- Нажать «Save» (или «Update» если GPT уже существовал)
- Выбрать доступность: «Only me» достаточно

---

## Финальный тест в сохранённом GPT

1. Открыть `https://chatgpt.com/gpts` → найти свой GPT
2. Написать в чате: «Проверь соединение»
3. Должен появиться ответ от агента (не сообщение об ошибке)
