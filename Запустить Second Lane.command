#!/bin/zsh
# Second Lane — пусковой скрипт для macOS.
# Двойной клик в Finder запускает панель агента.

set -u

cd "$(dirname "$0")" || {
  echo "Не удалось перейти в папку проекта: $(dirname "$0")"
  read -r -n 1 -s -p "Нажми любую клавишу, чтобы закрыть это окно…"
  exit 1
}

if [[ -x ".venv/bin/python" ]]; then
  PICK=".venv/bin/python"
else
  PICK=""
  for candidate in python3.13 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PICK="$candidate"
      break
    fi
  done
fi

if [ -z "$PICK" ]; then
  cat <<'MSG'

Python не найден.

Second Lane требует Python 3.13 или 3.12.

Что сделать:
1. Запусти «Установить Second Lane.command».
2. Если нужно, мастер сам поставит Python.
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
