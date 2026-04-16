# PROJECT MEMORY SPEC

Second Lane by **Yurii Slepnev** · Apache-2.0  
Telegram: https://t.me/yurii_yurii86 · YouTube: https://youtube.com/@yurii_yurii86 · Instagram: https://instagram.com/yurii_yurii86

## Что хранится

- `system_state.json` — подтверждённая текущая правда о проекте
- `active_tasks.json` — открытые задачи, blockers, next resume hint
- `handoff.md` — где проект сейчас и что делать дальше
- `sessions.jsonl` — журнал рабочих сессий
- `change_log.jsonl` — журнал реальных изменений
- `checkpoints/` — откатные снапшоты файлов

## Базовые правила

- не записывать выдуманные факты
- обновлять память после значимых изменений
- хранить следующий шаг явно, а не только в чате
