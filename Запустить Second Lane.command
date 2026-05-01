#!/bin/zsh
# Second Lane — пусковой скрипт для macOS.
# Двойной клик в Finder запускает панель агента.

set -u

cd "$(dirname "$0")" || {
  echo "Не удалось перейти в папку проекта: $(dirname "$0")"
  read -r -n 1 -s -p "Нажми любую клавишу, чтобы закрыть это окно…"
  exit 1
}

export PATH="${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

python_313_gui_ok() {
  local PY_BIN="$1"
  "$PY_BIN" - <<'PY' >/dev/null 2>&1
import sys
import tkinter as tk
if sys.version_info[:2] != (3, 13):
    raise SystemExit(1)
root = tk.Tk()
root.withdraw()
root.update_idletasks()
root.destroy()
PY
}

if [[ -x ".venv/bin/python" ]] && python_313_gui_ok ".venv/bin/python"; then
  PICK=".venv/bin/python"
else
  PICK=""
  for candidate in \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 \
    /usr/local/bin/python3.13 \
    /opt/homebrew/bin/python3.13 \
    python3.13; do
    if { command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]]; } && python_313_gui_ok "$candidate"; then
      PICK="$candidate"
      break
    fi
  done
fi

if [ -z "$PICK" ]; then
  cat <<'MSG'

Подходящий Python не найден.

Second Lane сейчас подтверждён на Python 3.13 с графическим модулем tkinter.

Что сделать:
1. Запусти «Установить Second Lane.command».
2. Если нужно, мастер сам поставит подходящий Python.
3. Потом снова дважды нажми «Запустить Second Lane.command».

MSG
  read -r -n 1 -s -p "Нажми любую клавишу, чтобы закрыть это окно…"
  exit 1
fi

env_value() {
  local KEY="$1"
  if [[ ! -f ".env" ]]; then
    return 1
  fi
  awk -F= -v key="$KEY" '
    $0 !~ /^[[:space:]]*#/ && $1 == key {
      sub(/^[^=]*=/, "", $0)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)
      print $0
      exit
    }
  ' ".env"
}

token_ready() {
  local TOKEN="$1"
  [[ "$TOKEN" =~ '^[0-9a-fA-F]{64}$' ]] || return 1
  local UNIQUE_COUNT
  UNIQUE_COUNT="$(printf "%s" "$TOKEN" | fold -w 1 | sort -u | wc -l | tr -d ' ')"
  [[ "${UNIQUE_COUNT:-0}" -gt 4 ]]
}

domain_ready() {
  local DOMAIN="$1"
  DOMAIN="${DOMAIN#http://}"
  DOMAIN="${DOMAIN#https://}"
  DOMAIN="${DOMAIN%%/*}"
  DOMAIN="${DOMAIN%.}"
  DOMAIN="${DOMAIN:l}"
  [[ -n "$DOMAIN" ]] || return 1
  case "$DOMAIN" in
    your-domain.ngrok-free.app|your-domain.ngrok-free.dev|example.ngrok-free.app|example.ngrok-free.dev|something.ngrok-free.app|something.ngrok-free.dev)
      return 1
      ;;
  esac
  [[ "$DOMAIN" =~ '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$' ]] || return 1
  [[ "$DOMAIN" == *.ngrok-free.app || "$DOMAIN" == *.ngrok-free.dev || "$DOMAIN" == *.ngrok-free.pizza || "$DOMAIN" == *.ngrok.app || "$DOMAIN" == *.ngrok.dev || "$DOMAIN" == *.ngrok.pizza ]]
}

ngrok_ready() {
  [[ -x "tools/ngrok/ngrok" ]] || command -v ngrok >/dev/null 2>&1
}

open_installer_for_repair() {
  local REASON="$1"
  cat <<MSG

Настройка Second Lane ещё не готова.

Причина:
• $REASON

Сейчас открою пошаговый установщик. Он сам поправит настройки, ничего вручную в Terminal вводить не нужно.

MSG
  exec "$PICK" second_lane_installer.py
}

if [[ ! -f ".env" ]]; then
  open_installer_for_repair "не найден файл .env с настройками"
fi

AGENT_TOKEN_VALUE="$(env_value "AGENT_TOKEN" || true)"
NGROK_DOMAIN_VALUE="$(env_value "NGROK_DOMAIN" || true)"

if ! token_ready "$AGENT_TOKEN_VALUE"; then
  open_installer_for_repair "секретный ключ AGENT_TOKEN пустой, шаблонный или слишком слабый"
fi

if ! domain_ready "$NGROK_DOMAIN_VALUE"; then
  open_installer_for_repair "адрес NGROK_DOMAIN пустой, шаблонный или не похож на домен ngrok"
fi

if ! ngrok_ready; then
  open_installer_for_repair "ngrok ещё не установлен в проекте и не найден в системе"
fi

echo "Запускаю Second Lane через $PICK"
"$PICK" gpts_agent_control.py
rc=$?

if [ $rc -ne 0 ]; then
  echo ""
  echo "Панель завершилась с ошибкой (код $rc)."
  echo "Проверь текст выше. Если не понятно, снова запусти установщик и потом повтори запуск."
  read -r -n 1 -s -p "Нажми любую клавишу, чтобы закрыть это окно…"
  exit $rc
fi
