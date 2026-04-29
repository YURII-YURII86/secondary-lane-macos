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
