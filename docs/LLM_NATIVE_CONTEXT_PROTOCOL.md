# LLM-NATIVE CONTEXT ARCHITECTURE

Second Lane by **Yurii Slepnev** · Apache-2.0  
Telegram: https://t.me/yurii_yurii86 · YouTube: https://youtube.com/@yurii_yurii86 · Instagram: https://instagram.com/yurii_yurii86

## Принцип

Код, память проекта и handoff должны быть синхронизированы.

## Обязательные файлы памяти

- `.ai_context/system_state.json`
- `.ai_context/active_tasks.json`
- `.ai_context/handoff.md`
- `.ai_context/project_brief.md`
- `.ai_context/sessions.jsonl`
- `.ai_context/change_log.jsonl`

## Рабочий цикл

`READ -> CODE -> UPDATE -> VERIFY`

## Практический смысл

- нельзя держать важные решения только в чате
- после значимых изменений надо обновлять `.ai_context`
- если работа длинная, следующий агент должен продолжить её без нового расследования с нуля
