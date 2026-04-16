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

echo "Running py_compile verification"
"${VENV_DIR}/bin/python" -m py_compile \
  app/main.py \
  app/core/config.py \
  app/core/project_memory.py \
  app/core/providers.py \
  app/core/security.py \
  app/core/utils.py \
  gpts_agent_control.py \
  tests/test_smoke.py \
  tests/test_project_memory_smoke.py \
  tests/test_super_actions.py

echo "Running pytest verification"
exec bash "${PROJECT_DIR}/scripts/run_local_pytest.sh" "$@"
