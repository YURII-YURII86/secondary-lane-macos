#!/bin/zsh

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)" || exit 1
INSTALLER_PY="$SCRIPT_DIR/second_lane_installer.py"
PYTHON_ORG_MACOS_URL="https://www.python.org/downloads/latest/python3.13/"

export PATH="${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd "$SCRIPT_DIR" || exit 1

if [[ "${SECOND_LANE_INSTALLER_FORCE_BOOTSTRAP:-}" != "1" ]]; then
  for PY_BIN in python3.13 python3; do
    if command -v "$PY_BIN" >/dev/null 2>&1; then
      if "$PY_BIN" - <<'PY' >/dev/null 2>&1
import tkinter as tk
root = tk.Tk()
root.withdraw()
root.update_idletasks()
root.destroy()
PY
      then
        if [[ "${SECOND_LANE_INSTALLER_BOOTSTRAP_CHECK_ONLY:-}" == "1" ]]; then
          printf "\n============================================================\n"
          printf "Bootstrap self-check\n"
          printf "============================================================\n"
          printf "• Подходящий Python для GUI найден: %s\n" "$PY_BIN"
          exit 0
        fi
        exec "$PY_BIN" "$INSTALLER_PY"
      fi
    fi
  done
fi

say_step() {
  printf "\n============================================================\n"
  printf "%s\n" "$1"
  printf "============================================================\n"
}

say_info() {
  printf "• %s\n" "$1"
}

open_external_url() {
  local URL="$1"
  if [[ "${SECOND_LANE_INSTALLER_TEST_DISABLE_OPEN:-}" == "1" ]]; then
    return 0
  fi
  open "$URL"
}

pause_for_user() {
  printf "\nНажми Enter, чтобы продолжить..."
  read -r
}

check_internet_or_stop() {
  for URL in \
    "https://www.apple.com/library/test/success.html" \
    "https://www.google.com/generate_204" \
    "https://raw.githubusercontent.com" \
    "https://brew.sh"
  do
    if curl -fsSL --max-time 8 -o /dev/null "$URL" >/dev/null 2>&1; then
      return 0
    fi
  done
  say_step "Нет доступа к интернету"
  say_info "Установщик не смог сам проверить интернет."
  say_info "Если сайты в браузере открываются, закрой это окно и запусти установщик снова."
  say_info "Потом запусти этот установщик снова."
  say_info "Ничего не вводи в Terminal вручную."
  pause_for_user
  exit 1
}

python_gui_smoke() {
  local PY_BIN="$1"
  "$PY_BIN" - <<'PY' >/dev/null 2>&1
import tkinter as tk
root = tk.Tk()
root.withdraw()
root.update_idletasks()
root.destroy()
PY
}

python_with_tkinter() {
  local CANDIDATES=()
  if [[ -n "${SECOND_LANE_INSTALLER_TEST_ABSOLUTE_PYTHON_CANDIDATE:-}" ]]; then
    CANDIDATES+=("${SECOND_LANE_INSTALLER_TEST_ABSOLUTE_PYTHON_CANDIDATE}")
  fi
  if [[ "${SECOND_LANE_INSTALLER_TEST_SKIP_ABSOLUTE_PYTHON:-}" == "1" ]]; then
    CANDIDATES+=(python3.13 python3)
  else
    CANDIDATES+=(
      /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13
      /usr/local/bin/python3.13
      python3.13
      python3
      /opt/homebrew/bin/python3.13
    )
  fi
  for PY_BIN in "${CANDIDATES[@]}"; do
    if command -v "$PY_BIN" >/dev/null 2>&1 || [[ -x "$PY_BIN" ]]; then
      if python_gui_smoke "$PY_BIN"; then
        printf "%s" "$PY_BIN"
        return 0
      fi
    fi
  done
  return 1
}

launch_gui_if_possible() {
  local PY_BIN
  PY_BIN="$(python_with_tkinter || true)"
  if [[ -n "$PY_BIN" ]]; then
    if [[ "${SECOND_LANE_INSTALLER_BOOTSTRAP_CHECK_ONLY:-}" == "1" ]]; then
      say_step "Bootstrap self-check"
      say_info "Подходящий Python для GUI найден: $PY_BIN"
      exit 0
    fi
    exec "$PY_BIN" "$INSTALLER_PY"
  fi
}

find_brew() {
  if command -v brew >/dev/null 2>&1; then
    command -v brew
    return 0
  fi
  for BREW_BIN in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -x "$BREW_BIN" ]]; then
      printf "%s" "$BREW_BIN"
      return 0
    fi
  done
  return 1
}

install_homebrew() {
  say_step "Подготовка Homebrew"
  say_info "Homebrew нужен, чтобы поставить Python 3.13 и другие программы."
  say_info "Если macOS попросит пароль, это нормально: пароль нужен только для установки системных инструментов."
  say_info "Если появится окно Apple Command Line Tools, дождись завершения установки."
  say_info "Ничего не копируй и не вставляй в Terminal: установщик всё сделает сам."
  pause_for_user
  check_internet_or_stop
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
}

install_python_313() {
  local BREW_BIN="$1"
  say_step "Подготовка Python 3.13"
  say_info "Ставлю Python 3.13. После этого откроется графический мастер установки."
  check_internet_or_stop
  "$BREW_BIN" install python@3.13
}

install_python_tk_313() {
  local BREW_BIN="$1"
  say_step "Подготовка окна установщика"
  say_info "На этом Mac Python уже есть, но ему не хватает части для обычных окон."
  say_info "Сейчас установщик сам докачает эту часть и снова попробует открыть мастер."
  say_info "Ничего не вводи в Terminal вручную."
  check_internet_or_stop
  "$BREW_BIN" install python-tk@3.13
}

guide_user_to_python_org() {
  say_step "Нужен официальный Python для графического окна"
  say_info "На этом Mac графическое окно Python падает ещё до запуска мастера."
  say_info "Это похоже на проблему некоторых Homebrew-сборок Python с tkinter на macOS."
  say_info "Сейчас открою официальный Python installer. Пройди обычную установку мышкой, потом вернись сюда и нажми Enter."
  say_info "Ничего не вводи в Terminal вручную."
  check_internet_or_stop
  open_external_url "$PYTHON_ORG_MACOS_URL"
  pause_for_user
}

say_step "Second Lane Installer: первый запуск"
say_info "На этом Mac пока нет подходящего Python для графического окна."
say_info "Сейчас установщик подготовит основу в этом окне, а потом откроет красивый мастер."
say_info "Ничего не вводи в Terminal вручную. Просто следи за подсказками."

BREW_BIN="$(find_brew || true)"
if [[ -z "$BREW_BIN" ]]; then
  install_homebrew
  BREW_BIN="$(find_brew || true)"
fi

if [[ -n "$BREW_BIN" ]]; then
  if [[ "$BREW_BIN" == /opt/homebrew/bin/brew ]]; then
    eval "$("$BREW_BIN" shellenv)"
  elif [[ "$BREW_BIN" == /usr/local/bin/brew ]]; then
    eval "$("$BREW_BIN" shellenv)"
  fi
fi

if [[ -z "$BREW_BIN" ]]; then
  say_step "Нужна ручная помощь"
  say_info "Homebrew не появился после установки."
  say_info "Не вводи команды вручную. Лучше скопируй этот текст ошибки и покажи тому, кто помогает с установкой."
  say_info "На сайте Homebrew есть справка, но для этого установщика мы не просим тебя самому писать команды."
  open_external_url "https://brew.sh"
  pause_for_user
  exit 1
fi

if ! python_with_tkinter >/dev/null 2>&1; then
  install_python_313 "$BREW_BIN"
fi

if ! python_with_tkinter >/dev/null 2>&1; then
  install_python_tk_313 "$BREW_BIN"
fi

if ! python_with_tkinter >/dev/null 2>&1; then
  guide_user_to_python_org
fi

launch_gui_if_possible

if [[ "${SECOND_LANE_INSTALLER_BOOTSTRAP_CHECK_ONLY:-}" == "1" ]] && python_with_tkinter >/dev/null 2>&1; then
  say_step "Bootstrap self-check"
  say_info "Проверка bootstrap-сценария завершена без запуска GUI."
  exit 0
fi

say_step "Не удалось открыть графический мастер"
say_info "Python найден, но графическое окно всё ещё не запускается."
say_info "Если ты уже поставил официальный Python installer, закрой это окно и запусти установщик снова."
say_info "Если ошибка повторится, скопируй текст этого окна и покажи тому, кто помогает с установкой."
say_info "Ничего не вводи в Terminal вручную."
pause_for_user
exit 1
