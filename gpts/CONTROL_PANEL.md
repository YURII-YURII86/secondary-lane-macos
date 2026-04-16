# CONTROL PANEL

Second Lane by **Yurii Slepnev** · Apache-2.0  
Telegram: https://t.me/yurii_yurii86 · YouTube: https://youtube.com/@yurii_yurii86 · Instagram: https://instagram.com/yurii_yurii86

Локальная панель запускается файлом `gpts_agent_control.py`.

## Основные действия

- `Запустить` — поднять daemon и tunnel
- `Перезапустить демон` — жёстко остановить текущий daemon проекта на `8787` и поднять новый
- `Выключить` — остановить процессы, которые панель сама поднимала
- `Скопировать URL` — взять текущий public URL
- `Проверить` — выполнить health-проверку
- `Открыть .env` — открыть конфиг

## Что важно

- проект ожидает Python 3.13 для clean local setup
- панель принудительно использует provider dir и state DB из текущей папки проекта
- если action-set или `openapi.gpts.yaml` изменились, после этого нужен перезапуск daemon и реимпорт GPT schema
