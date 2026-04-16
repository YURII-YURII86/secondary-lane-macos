# Security Policy

Second Lane is created by **Yurii Slepnev**.
Official links: Telegram https://t.me/yurii_yurii86 · YouTube https://youtube.com/@yurii_yurii86 · Instagram https://instagram.com/yurii_yurii86
License: Apache-2.0

## RU

Second Lane может давать ChatGPT доступ к реальным действиям на машине, поэтому безопасность тут критична.

### Как сообщать об уязвимости

Если ты нашёл серьёзную уязвимость, сначала сообщи о ней приватно, а не публикуй детали сразу.

Добавь:

- что именно можно эксплуатировать
- как это воспроизвести
- какой ущерб, по твоему мнению, это может дать

### Важные заметки по безопасности

- все маршруты должны быть защищены bearer auth
- доступ к файлам специально ограничен через `WORKSPACE_ROOTS`
- SSH-доступ должен оставаться жёстко ограниченным allowlist'ом
- публичный tunnel нужно использовать осторожно
- секреты, например bearer token, нельзя коммитить в репозиторий

### Области повышенного риска

К чувствительным зонам относятся:

- аутентификация и авторизация
- вычисление путей и границы workspace
- выполнение команд
- выполнение SSH-команд
- публичная экспозиция через tunnel
- любые будущие интеграции с браузером или системным управлением

## EN

Second Lane can expose real machine actions through ChatGPT and GPT Actions, so security matters.

### Report A Vulnerability

If you find a serious security issue, please report it privately before publishing details.

Include:

- what can be exploited
- how to reproduce it
- what impact you believe it has

### Security Notes

- all routes are expected to be protected by bearer auth
- file access is intentionally restricted by `WORKSPACE_ROOTS`
- SSH access should stay tightly allowlisted
- public tunnel use should be treated carefully
- secrets such as bearer tokens must never be committed to the repository

### Scope

Security-sensitive areas include:

- authentication and authorization
- path resolution and workspace boundaries
- command execution
- SSH execution
- tunnel exposure
- any future browser or system-control integrations
