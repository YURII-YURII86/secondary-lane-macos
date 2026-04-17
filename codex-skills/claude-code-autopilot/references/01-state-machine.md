# State Machine

Таблица состояний для Claude Code Autopilot.
Держи открытой — всегда знай в каком ты состоянии.

| Состояние | Реальная ситуация | Действие Claude Code | Проверка | Следующее |
|---|---|---|---|---|
| S0 | Неизвестное состояние | `discover_secondarylane_layout.py`, проверить `.env`, порт 8787, ngrok 4040 | Реальное состояние всех компонентов известно | S1–S6 (нужный) |
| S1 | Python 3.13 неизвестен или отсутствует | `python3.13 --version`; если нет — открыть python.org | `python3.13 --version` → OK | S2 |
| S2 | ngrok неизвестен или отсутствует | `ngrok version`; если нет — `brew install ngrok` | `ngrok version` → OK | S3 |
| S3 | authtoken / домен не настроен | Открыть dashboard.ngrok.com; ждать только ввод токена и имени домена | `ngrok config check` OK + домен известен | S4 |
| S4 | `.env` отсутствует или неполный | `build_env.py . --ngrok-domain <domain>` | `AGENT_TOKEN`, `NGROK_DOMAIN`, `WORKSPACE_ROOTS` непустые | S5 |
| S5 | venv / зависимости не установлены | `python3.13 -m venv .venv && pip install -r requirements.txt` | `import fastapi, uvicorn, pydantic` → OK | S6 |
| S6 | Панель не запущена | `nohup .venv/bin/python gpts_agent_control.py &` + poll `/v1/capabilities` | `curl localhost:8787/v1/capabilities` → `ok:true` | S7 |
| S7 | ngrok тоннель не запущен | `ngrok http 8787 --domain=<domain>` + poll localhost:4040 | Реальный `https://` URL получен | S8 |
| S8 | openapi.gpts.yaml содержит старый URL | Обновить `servers.url`; проверить сквозной вызов через тоннель | `curl <public_url>/v1/capabilities` + Bearer → `ok:true` | S9 |
| S9 | Материалы для GPT не подготовлены | `export_gpt_materials.py` — показать пути/содержимое | Пользователь знает что куда вставлять | S10 |
| S10 | ChatGPT editor не открыт | `open https://chatgpt.com/gpts/editor`; ждать подтверждения | Пользователь видит GPT editor | S11 |
| S11 | Actions / auth не настроены | Провести по шагам: schema → auth → test Preview | Preview → `getCapabilities` → JSON без 401 | S12 |
| S12 | Финальная проверка не пройдена | Проверить панель, тоннель, URL в YAML; попросить тест в сохранённом GPT | Всё зелёное + пользователь получил ответ | S13 |
| S13 | Всё работает, нет финального handoff | Дать короткую сводку: путь, .env, как перезапустить | Пользователь знает где что лежит | DONE |

## Правило перехода

Никогда не переходи вперёд без явной проверки текущего шага.
«Должно работать» — не проверка.
