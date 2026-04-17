# Verification Checklist

Не говори «готово» пока каждый пункт не проверен командой.

## Локальная машина

```bash
# 1. Python
python3.13 --version
# ожидается: Python 3.13.x

# 2. ngrok
ngrok version
# ожидается: ngrok version X.Y.Z

# 3. .env — все ключи
grep -E "^(AGENT_TOKEN|NGROK_DOMAIN|WORKSPACE_ROOTS)=" <branch_root>/.env
# ожидается: три непустые строки

# 4. venv зависимости
<branch_root>/.venv/bin/python -c "import fastapi, uvicorn, pydantic; print('OK')"
# ожидается: OK
```

## Панель и тоннель

```bash
# 5. GUI-окно «GPTS Agent Control» открыто (визуальная проверка)
# Панель отвечает по API:
curl -s --max-time 5 http://localhost:8787/v1/capabilities
# ожидается: JSON с ok:true

# 6. ngrok тоннель активен
curl -s http://localhost:4040/api/tunnels | python3 -c "
import json,sys; d=json.load(sys.stdin)
t=[x['public_url'] for x in d.get('tunnels',[]) if x.get('proto')=='https']
print('ACTIVE:', t[0] if t else 'NONE')
"
# ожидается: ACTIVE: https://xxx.ngrok-free.app

# 7. Сквозной вызов через тоннель (подставь реальный URL и токен)
curl -s --max-time 10 \
  -H "Authorization: Bearer <AGENT_TOKEN>" \
  "https://<NGROK_DOMAIN>/v1/capabilities"
# ожидается: JSON с ok:true
```

## openapi.gpts.yaml

```bash
# 8. servers.url содержит реальный домен
python3 -c "
import re, pathlib
text = pathlib.Path('<branch_root>/openapi.gpts.yaml').read_text()
urls = re.findall(r'- url:\s*(https?://\S+)', text)
print('URL:', urls[0] if urls else 'MISSING')
"
# ожидается: URL: https://<реальный ngrok домен>
```

## ChatGPT / GPT builder

- [ ] GPT editor открыт
- [ ] Текст из `system_instructions.txt` вставлен в поле `Instructions`
- [ ] Все `.md` файлы из `gpts/knowledge/` загружены в `Knowledge`
- [ ] Содержимое `openapi.gpts.yaml` вставлено в `Actions`
- [ ] Auth настроен: тип `Bearer`, значение = только токен из `AGENT_TOKEN`

## Action calls

```bash
# Тест через Preview в редакторе (выполни пользователь):
# → попросить GPT вызвать getCapabilities
# ожидается: JSON-ответ без ошибки 401
```

- [ ] Preview → `getCapabilities` → JSON, не ошибка 401
- [ ] Сохранённый GPT → простой запрос → ответ от агента
- [ ] Панель не упала во время теста
- [ ] Тоннель не отвалился во время теста

## Handoff

- [ ] Пользователь знает где папка проекта
- [ ] Пользователь знает как перезапустить панель
- [ ] Пользователь знает что панель должна быть открыта пока работает GPT
- [ ] Пользователь знает куда смотреть если GPT перестал отвечать
