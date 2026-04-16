# Adaptive Project Detection

Если ожидаемая папка `Версия для Мак` не найдена или переименована, ищи по маркерам:

- `.env.example`
- `gpts_agent_control.py`
- `openapi.gpts.yaml`
- `Запустить Second Lane.command`
- `gpts/system_instructions.txt`

Используй `scripts/discover_secondarylane_layout.py` и выбирай кандидат с наибольшим количеством совпадений.
