#!/usr/bin/env bash
# Second Lane
# Copyright (c) 2026 Yurii Slepnev
# Licensed under the Apache License, Version 2.0.
# Official: https://t.me/yurii_yurii86 | https://youtube.com/@yurii_yurii86 | https://instagram.com/yurii_yurii86
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.13}"
DEFAULT_VENV_DIR="${PROJECT_DIR}/.venv"
VENV_DIR="${VENV_DIR:-${DEFAULT_VENV_DIR}}"
STAMP_FILE="${VENV_DIR}/.requirements_installed"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Required interpreter not found: ${PYTHON_BIN}" >&2
  echo "This project currently supports local verification through Python 3.13." >&2
  exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "Creating local venv at ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

if [[ ! -f "${STAMP_FILE}" || "${PROJECT_DIR}/requirements.txt" -nt "${STAMP_FILE}" ]]; then
  echo "Installing project requirements into ${VENV_DIR}"
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install -r "${PROJECT_DIR}/requirements.txt"
  touch "${STAMP_FILE}"
fi

cd "${PROJECT_DIR}"

if [[ "$#" -eq 0 ]]; then
  set -- tests/test_smoke.py tests/test_project_memory_smoke.py tests/test_super_actions.py
fi

exec "${VENV_DIR}/bin/python" -m pytest -q "$@"
