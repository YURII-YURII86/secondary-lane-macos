#!/bin/zsh

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)" || exit 1
INSTALLER_PY="$SCRIPT_DIR/second_lane_installer.py"
PYTHON_ORG_MACOS_PAGE="https://www.python.org/downloads/latest/python3.13/"
PYTHON_ORG_MACOS_PKG_FALLBACK_URL="https://www.python.org/ftp/python/3.13.13/python-3.13.13-macos11.pkg"

export PATH="${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd "$SCRIPT_DIR" || exit 1

if [[ "${SECOND_LANE_INSTALLER_FORCE_BOOTSTRAP:-}" != "1" ]]; then
  for PY_BIN in python3.13; do
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

resolve_python_pkg_url() {
  local HTML PKG_URL
  HTML="$(curl -fsSL --compressed --max-time 20 "$PYTHON_ORG_MACOS_PAGE" 2>/dev/null || true)"
  PKG_URL="$(
    printf "%s" "$HTML" \
      | grep -Eo 'https://www\.python\.org/ftp/python/3\.13\.[0-9]+/python-3\.13\.[0-9]+-macos11\.pkg|/ftp/python/3\.13\.[0-9]+/python-3\.13\.[0-9]+-macos11\.pkg' \
      | head -n 1
  )"
  if [[ "$PKG_URL" == /ftp/* ]]; then
    printf "https://www.python.org%s" "$PKG_URL"
  elif [[ -n "$PKG_URL" ]]; then
    printf "%s" "$PKG_URL"
  else
    printf "%s" "$PYTHON_ORG_MACOS_PKG_FALLBACK_URL"
  fi
}

download_and_open_python_pkg() {
  local PKG_URL DOWNLOAD_DIR PKG_FILE
  PKG_URL="$(resolve_python_pkg_url)"
  DOWNLOAD_DIR="${TMPDIR:-/tmp}/second-lane-python-installer"
  PKG_FILE="$DOWNLOAD_DIR/$(basename "$PKG_URL")"

  if [[ "${SECOND_LANE_INSTALLER_TEST_DISABLE_OPEN:-}" == "1" ]]; then
    say_info "Тестовый режим: пропускаю скачивание Python installer."
    return 0
  fi

  mkdir -p "$DOWNLOAD_DIR" || {
    say_info "Не смог создать временную папку для Python installer. Открою страницу python.org."
    open_external_url "$PYTHON_ORG_MACOS_PAGE"
    return 0
  }

  if [[ ! -f "$PKG_FILE" ]]; then
    say_info "Скачиваю официальный Python installer с python.org. Размер около 68 MB."
    if ! curl -fL --progress-bar --connect-timeout 15 --max-time 600 -o "$PKG_FILE" "$PKG_URL"; then
      say_info "Не получилось скачать .pkg автоматически. Открою страницу python.org как запасной путь."
      open_external_url "$PYTHON_ORG_MACOS_PAGE"
      return 0
    fi
  else
    say_info "Python installer уже скачан: $PKG_FILE"
  fi

  say_info "Открываю обычное окно установки Python. В нём нажимай Continue / Install."
  open "$PKG_FILE"
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
    "https://www.python.org"
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
    CANDIDATES+=(python3.13)
  else
    CANDIDATES+=(
      /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13
      /usr/local/bin/python3.13
      python3.13
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

install_python_from_python_org() {
  say_step "Подготовка Python 3.13"
  say_info "На этом Mac пока нет подходящего Python 3.13 для графического окна."
  say_info "Я НЕ буду ставить Python через Homebrew: на Mac с M‑процессором это иногда уходит в долгую сборку и выглядит как зависание."
  say_info "Сейчас скачаю официальный .pkg с python.org и открою обычное окно установки."
  say_info "Когда в окне установки появится Install Succeeded, вернись в Terminal и нажми Enter."
  say_info "Ничего технического в Terminal вводить не нужно."
  check_internet_or_stop
  download_and_open_python_pkg
  pause_for_user
}

say_step "Second Lane Installer: первый запуск"
say_info "На этом Mac пока нет подходящего Python для графического окна."
say_info "Сейчас установщик проверит официальный Python 3.13 и откроет красивый мастер."
say_info "Ничего не вводи в Terminal вручную. Просто следи за подсказками."

for ATTEMPT in 1 2 3; do
  if python_with_tkinter >/dev/null 2>&1; then
    launch_gui_if_possible
  fi
  install_python_from_python_org
done

launch_gui_if_possible

if [[ "${SECOND_LANE_INSTALLER_BOOTSTRAP_CHECK_ONLY:-}" == "1" ]] && python_with_tkinter >/dev/null 2>&1; then
  say_step "Bootstrap self-check"
  say_info "Проверка bootstrap-сценария завершена без запуска GUI."
  exit 0
fi

say_step "Не удалось открыть графический мастер"
say_info "Официальный Python 3.13 всё ещё не найден или его графическое окно не запускается."
say_info "Проверь, что установка с python.org действительно завершилась, затем закрой это окно и запусти установщик снова."
say_info "Если ошибка повторится, скопируй текст этого окна и покажи тому, кто помогает с установкой."
say_info "Ничего не вводи в Terminal вручную."
pause_for_user
exit 1
