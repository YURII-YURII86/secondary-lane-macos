# ngrok — что нужно и как получить

Этот файл нужен на шаге S3.

## Что нужно от пользователя

Два значения, оба берутся с сайта ngrok.com:

1. **Authtoken** — строка вида `2abc123...XYZ` (~48 символов)
2. **Зарезервированный домен** — строка вида `xxx.ngrok-free.app` или `xxx.ngrok.app`

---

## Шаг 1. Зарегистрироваться / войти

```bash
open https://dashboard.ngrok.com/signup
```

Если уже есть аккаунт:

```bash
open https://dashboard.ngrok.com/login
```

Жди пока пользователь скажет «вошёл».

---

## Шаг 2. Получить authtoken

```bash
open https://dashboard.ngrok.com/get-started/your-authtoken
```

Скажи пользователю:
> «На открывшейся странице нажми "Copy" рядом с длинной строкой (это твой authtoken).
> Вставь её сюда.»

Получив строку — выполни:

```bash
ngrok config add-authtoken <полученная_строка>
```

Проверь:

```bash
ngrok config check
# ожидается: Valid configuration file, no errors
```

---

## Шаг 3. Зарезервировать домен

```bash
open https://dashboard.ngrok.com/domains
```

Скажи пользователю:
> «Если уже есть домен в списке — скопируй его название (например xxx.ngrok-free.app).
> Если нет — нажми "New Domain" и скопируй созданное имя.»

На бесплатном аккаунте доступен 1 статический домен бесплатно.

Запомни это имя — используется в S4, S7, S8.

---

## Важные детали

- Домен вводить **без** `https://` — только само имя: `xxx.ngrok-free.app`
- Authtoken привязан к аккаунту — нельзя использовать чужой
- Домен можно использовать только с тем аккаунтом который его зарезервировал
- Если тоннель не стартует — проверить что домен именно в `ngrok-free.app`,
  а не ошибка в написании

---

## Проверка после настройки

```bash
# Тестовый запуск тоннеля
ngrok http 8787 --domain=<domain> &
sleep 3
curl -s http://localhost:4040/api/tunnels | python3 -c "
import json,sys
d=json.load(sys.stdin)
for t in d.get('tunnels',[]):
    if t.get('proto')=='https':
        print('OK:', t['public_url'])
"
pkill -f "ngrok http"
```

Ожидается: `OK: https://<твой_домен>`
