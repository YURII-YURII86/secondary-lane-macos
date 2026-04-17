#!/bin/zsh
# Second Lane — пусковой скрипт для macOS.
# Двойной клик в Finder запускает панель агента.
#
# На macOS двойной клик открывает .command в Terminal с cwd = домашняя
# папка пользователя, поэтому первым делом переходим в папку, где
# лежит этот скрипт.

set -u

cd "$(dirname "$0")" || {
  echo "Не удалось перейти в папку проекта: $(dirname "$0")"
  read -r -n 1 -s -p "Нажми любую клавишу, чтобы закрыть это окно…"
  exit 1
}

# Ищем рабочий Python в порядке от самого желанного к запасному.
PICK=""
for candidate in python3.13 python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PICK="$candidate"
    break
  fi
done

if [ -z "$PICK" ]; then
  cat <<'EOF'

❌ Python не найден.

Second Lane требует Python 3.13 (минимум 3.12).

Что сделать:
  1. Открой https://www.python.org/downloads/macos/
  2. Скачай установщик Python 3.13 для macOS.
  3. Запусти установщик — дважды кликни по скачанному .pkg,
     потом «Continue» → «Continue» → «Install».
  4. После установки закрой это окно и ещё раз дважды кликни
     «Запустить Second Lane.command».

Альтернатива через Homebrew (если умеешь им пользоваться):
    brew install python@3.13

EOF
  read -r -n 1 -s -p "Нажми любую клавишу, чтобы закрыть это окно…"
  exit 1
fi

echo "▶ Запускаю Second Lane через $PICK"
"$PICK" gpts_agent_control.py
rc=$?

if [ $rc -ne 0 ]; then
  echo ""
  echo "❌ Панель завершилась с ошибкой (код $rc)."
  echo "Проверь вывод выше. Если не понятно — сверься с docs/MAC_FIRST_START.md."
  read -r -n 1 -s -p "Нажми любую клавишу, чтобы закрыть это окно…"
  exit $rc
fi
