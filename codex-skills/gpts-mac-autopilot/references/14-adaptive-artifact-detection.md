# Adaptive Artifact Detection

Если корень проекта найден, но отдельные файлы переехали, ищи роль артефакта, а не только точное имя.

Нужно восстановить как минимум:

- launcher
- `.env.example`
- `openapi.gpts.yaml`
- `gpts/system_instructions.txt`
- `gpts/knowledge/`

Используй `scripts/discover_secondarylane_artifacts.py` до того, как объявлять проект сломанным.
