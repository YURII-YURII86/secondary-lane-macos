# Second Lane — Claude Code Autopilot

Скилл для полностью автоматизированного разворачивания Second Lane на macOS.
Запускается через Claude Code, работает локально, управляет всем процессом
установки от нуля до первого рабочего вызова из ChatGPT.

## Принцип работы

Claude Code имеет прямой доступ к файловой системе и терминалу. Поэтому
этот скилл работает иначе, чем ChatGPT-версия: не объясняет шаги, а
**выполняет их напрямую** через Bash.

Пользователь нужен только в двух местах:
1. Регистрация/логин на ngrok.com (браузер)
2. Сборка GPT в ChatGPT (браузер)

Всё остальное — автоматически.

## Стиль общения

- Говори по-русски
- Коротко и конкретно: что делаешь, что получилось, что нужно от человека
- Не объясняй теорию если не просят
- Когда нужно действие от пользователя — опиши его одним предложением и жди

---

## Алгоритм — читай SKILL.md целиком перед первым действием

### S0. Обнаружить реальное состояние

**Автоматически:**

```bash
# Найти корень проекта
python3 codex-skills/gpts-mac-autopilot/scripts/discover_secondarylane_layout.py . --max-depth 4

# Проверить .env
cat <branch_root>/.env 2>/dev/null || echo "NO_ENV"

# Проверить запущен ли агент
curl -s --max-time 3 http://localhost:8787/v1/capabilities 2>/dev/null || echo "NOT_RUNNING"

# Проверить ngrok
curl -s --max-time 3 http://localhost:4040/api/tunnels 2>/dev/null || echo "NGROK_NOT_RUNNING"
```

Запомни результат. Переходи в то состояние, которое реально соответствует ситуации.
Не начинай с начала если половина уже сделана.

---

### S1. Python 3.13

**Автоматически:**

```bash
python3.13 --version 2>&1 || python3.12 --version 2>&1 || python3 --version 2>&1
```

**Если 3.13 не найден:**
- Сообщи пользователю одним предложением
- Открой браузер: `open https://www.python.org/downloads/macos/`
- Жди пока скажет «установил»
- Проверь снова

**Принято если:** `python3.13 --version` → `Python 3.13.x`
**Запасной вариант:** 3.12 тоже подойдёт

---

### S2. ngrok

**Автоматически:**

```bash
ngrok version 2>&1 || which ngrok || brew list ngrok 2>/dev/null
```

**Если не найден — установи через Homebrew (если есть):**

```bash
if command -v brew >/dev/null 2>&1; then
  brew install ngrok/ngrok/ngrok
fi
```

**Если Homebrew тоже нет:**
- `open https://ngrok.com/download`
- Дай пользователю короткую инструкцию: скачать pkg, перетащить ngrok в /usr/local/bin
- Жди подтверждения

**Принято если:** `ngrok version` → `ngrok version X.Y.Z`

---

### S3. ngrok authtoken + reserved domain

**Проверь есть ли уже:**

```bash
# Проверить authtoken
ngrok config check 2>&1
# Проверить в .env
grep NGROK_DOMAIN <branch_root>/.env 2>/dev/null
```

**Если authtoken не настроен:**
1. Открой страницу: `open https://dashboard.ngrok.com/get-started/your-authtoken`
2. Скажи пользователю: «Скопируй authtoken с этой страницы и вставь сюда»
3. Получи от пользователя строку вида `2abc...XYZ`
4. Выполни: `ngrok config add-authtoken <token>`

**Если домен не известен:**
1. Открой: `open https://dashboard.ngrok.com/domains`
2. Скажи: «Скопируй имя своего зарезервированного домена (вида xxx.ngrok-free.app или xxx.ngrok.app)»
3. Запомни — понадобится в S4

**Принято если:** `ngrok config check` не содержит ошибок + домен известен

---

### S4. Создать / обновить .env

**Автоматически:**

```bash
cd <branch_root>
python3 codex-skills/gpts-mac-autopilot/scripts/build_env.py . \
  --ngrok-domain "<domain_from_S3>"
```

Скрипт сам:
- читает `.env.example` как базу
- генерирует `AGENT_TOKEN`
- записывает `NGROK_DOMAIN`
- устанавливает `WORKSPACE_ROOTS` = корень проекта

**Проверь результат:**

```bash
grep -E "^(AGENT_TOKEN|NGROK_DOMAIN|WORKSPACE_ROOTS)=" <branch_root>/.env
```

Все три строки должны быть непустыми. `WORKSPACE_ROOTS` должен начинаться с `/`.

**Принято если:** все три ключа присутствуют и непусты.

---

### S5. Виртуальное окружение + зависимости

**Автоматически:**

```bash
cd <branch_root>
# Создать venv если нет
if [ ! -d .venv ]; then
  python3.13 -m venv .venv
fi

# Установить зависимости
.venv/bin/pip install --quiet -r requirements.txt
```

**Проверь:**

```bash
.venv/bin/python -c "import fastapi, uvicorn, pydantic; print('OK')"
```

**Если pip завис или упал** — попробуй `pip install --quiet --timeout 60 -r requirements.txt`.

**Принято если:** импорты fastapi/uvicorn/pydantic работают без ошибок.

---

### S6. Запустить панель управления

`gpts_agent_control.py` — это **GUI-приложение** (Tkinter). При запуске
открывается окно «GPTS Agent Control» с кнопками управления, статусом
демона, URL тоннеля и логом. Это окно должно **оставаться открытым**
пока пользователь работает с GPT.

**Скажи пользователю:**

> «Сейчас откроется окно панели управления Second Lane.
> Не закрывай его — ChatGPT общается с агентом пока это окно открыто.»

**Способ 1 — через лончер (рекомендуется, самый простой):**

```bash
open "<branch_root>/Запустить Second Lane.command"
```

Это откроет Terminal с запущенной панелью.

**Способ 2 — напрямую из терминала:**

```bash
cd <branch_root>

# Убедиться что порт 8787 свободен
lsof -ti:8787 | xargs kill -9 2>/dev/null; sleep 1

# Запустить — откроется GUI-окно
.venv/bin/python gpts_agent_control.py
```

> Если нужно запустить в фоне без GUI (только сервер, без окна управления):
> `nohup .venv/bin/python gpts_agent_control.py > /tmp/secondlane.log 2>&1 &`
> Но тогда пользователь теряет кнопки «Скопировать URL», «Проверить» и т.д.

**Проверить что панель поднялась** (из другого терминала или через Claude Code):

```bash
curl -s --max-time 5 http://localhost:8787/v1/capabilities
```

**Принято если:** открылось GUI-окно с URL тоннеля + curl возвращает `ok: true`

---

### S7. Запустить ngrok тоннель

**Автоматически:**

```bash
# Убить старый ngrok если есть
pkill -f "ngrok http" 2>/dev/null; sleep 1

# Запустить тоннель
nohup ngrok http 8787 --domain=<ngrok_domain> > /tmp/ngrok_output.log 2>&1 &
sleep 4

# Получить реальный URL из API
curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import json,sys
data=json.load(sys.stdin)
for t in data.get('tunnels',[]):
    if t.get('proto')=='https':
        print(t['public_url'])
        break
"
```

**Принято если:** реальный `https://` URL получен из localhost:4040

---

### S8. Обновить openapi.gpts.yaml и проверить связку

**Автоматически:**

```bash
REAL_URL="<url_from_S7>"
cd <branch_root>

# Обновить servers url
python3 -c "
import re, pathlib
p = pathlib.Path('openapi.gpts.yaml')
text = p.read_text()
text = re.sub(r'(- url:)\s*https?://[^\s]+', f'\1 ${REAL_URL}', text)
p.write_text(text)
print('Updated')
"

# Сквозная проверка через реальный тоннель
curl -s --max-time 10 \
  -H "Authorization: Bearer <agent_token_from_env>" \
  "${REAL_URL}/v1/capabilities" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('TUNNEL_OK' if d.get('ok') else 'TUNNEL_FAIL')
"
```

**Принято если:** `TUNNEL_OK` через публичный URL.

---

### S9. Подготовить материалы для GPT

**Автоматически:**

```bash
python3 codex-skills/gpts-mac-autopilot/scripts/export_gpt_materials.py <branch_root>
```

Покажи пользователю:
- путь к `system_instructions.txt` — скопировать в Instructions
- список knowledge файлов — загрузить в Knowledge
- путь к `openapi.gpts.yaml` — вставить содержимое в Actions
- значение `AGENT_TOKEN` из `.env` — вставить в auth поле

---

### S10. ChatGPT — человеческий шлюз

**Открой браузер:**

```bash
open https://chatgpt.com/gpts/editor
```

Это обязательный ручной шаг. Объясни пользователю:

> «Сейчас нужно собрать GPT в ChatGPT. Открываю редактор в браузере.
> Я проведу тебя шаг за шагом. Скажи когда видишь форму GPT editor.»

Дальше веди пользователя по шагам из `references/05-chatgpt-builder.md`.

---

### S11. Настроить Actions + auth

Объясни пользователю конкретно:
1. В редакторе GPT нажать «Configure» → «Create new action»
2. Вставить **полное содержимое** `openapi.gpts.yaml`
3. В поле Authentication → API Key → Auth Type = Bearer
4. В поле API Key вставить **только значение** `AGENT_TOKEN` из `.env`
   (без слова Bearer, без знака `=`, без кавычек)
5. Нажать Save

**Проверь что auth принят:**
- В Preview попросить GPT выполнить `getCapabilities`
- Должен появиться JSON-ответ от агента, не ошибка 401

**Принято если:** Preview → `getCapabilities` → JSON с `ok: true`

---

### S12. Финальная проверка

Выполни сам:

```bash
# Панель жива
curl -s http://localhost:8787/v1/capabilities | python3 -c "import json,sys; print(json.load(sys.stdin).get('ok'))"

# Тоннель жив
curl -s http://localhost:4040/api/tunnels | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('TUNNEL_ACTIVE' if d.get('tunnels') else 'TUNNEL_DOWN')
"

# openapi.gpts.yaml содержит реальный URL
python3 -c "
import pathlib
text = pathlib.Path('<branch_root>/openapi.gpts.yaml').read_text()
import re
urls = re.findall(r'- url:\s*(https?://\S+)', text)
print('URL_OK:', urls[0] if urls else 'MISSING')
"
```

Все три должны быть OK.

Попроси пользователя в сохранённом GPT (не в Preview) написать: «Проверь соединение».
GPT должен вызвать агент и получить ответ.

**Принято если:** всё зелёное + пользователь видит ответ от агента.

---

### S13. Финальный handoff

Дай пользователю короткую сводку:

```
✅ Second Lane запущен

Папка проекта:     <branch_root>
.env:              <branch_root>/.env
AGENT_TOKEN:       (хранится в .env — не делиться)
Публичный URL:     <ngrok_domain>

Что должно оставаться открытым пока пользуешься GPT:
  1. Окно «GPTS Agent Control» (панель управления) — не закрывай
  2. ngrok (запускается автоматически из той же панели или отдельно)

Как перезапустить если что-то упало:
  Двойной клик по «Запустить Second Lane.command»
  — или —
  cd <branch_root>
  .venv/bin/python gpts_agent_control.py

Если GPT вдруг перестаёт отвечать:
  1. Проверь http://localhost:8787/v1/capabilities
  2. Проверь http://localhost:4040 (ngrok dashboard)
  3. Перезапусти по командам выше
```

---

## Guardrails

- Никогда не хардкодь путь к проекту — всегда используй обнаруженный `branch_root`
- Никогда не запускай `pip install` без активированного `.venv`
- Никогда не трогай `app/`, `tests/`, `openapi.gpts.yaml` структуру — только `servers.url`
- Перед `kill` на порт — проверь что это именно процесс Second Lane
- Если ngrok занят другим туннелем — сначала спроси пользователя перед killом

## Стоп-правило

Если не можешь честно ответить «в каком я сейчас состоянии?» —
останови всё и выполни S0 заново.
