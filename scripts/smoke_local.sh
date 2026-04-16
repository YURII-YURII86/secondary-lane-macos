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
HOST="127.0.0.1"
TOKEN="${SMOKE_AGENT_TOKEN:-local-smoke-token-1234567890abcdef}"
WORKSPACE_ROOTS_VALUE="${SMOKE_WORKSPACE_ROOTS:-${PROJECT_DIR}}"
STATE_DB_PATH_VALUE="${SMOKE_STATE_DB_PATH:-/tmp/second-lane-smoke.db}"
STARTUP_TIMEOUT_SEC="${SMOKE_STARTUP_TIMEOUT_SEC:-20}"

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

PORT="$("${VENV_DIR}/bin/python" - <<'PY'
import socket
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
)"

LOG_FILE="$(mktemp -t second-lane-smoke.XXXXXX.log)"
PID=""

cleanup() {
  if [[ -n "${PID}" ]] && kill -0 "${PID}" >/dev/null 2>&1; then
    kill "${PID}" >/dev/null 2>&1 || true
    wait "${PID}" 2>/dev/null || true
  fi
  rm -f "${LOG_FILE}"
}
trap cleanup EXIT

cd "${PROJECT_DIR}"

echo "Starting local smoke server on http://${HOST}:${PORT}"
AGENT_TOKEN="${TOKEN}" \
AGENT_HOST="${HOST}" \
AGENT_PORT="${PORT}" \
WORKSPACE_ROOTS="${WORKSPACE_ROOTS_VALUE}" \
STATE_DB_PATH="${STATE_DB_PATH_VALUE}" \
"${VENV_DIR}/bin/python" -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" >"${LOG_FILE}" 2>&1 &
PID="$!"

SMOKE_HOST="${HOST}" \
SMOKE_PORT="${PORT}" \
SMOKE_TOKEN="${TOKEN}" \
SMOKE_LOG_FILE="${LOG_FILE}" \
SMOKE_STARTUP_TIMEOUT_SEC="${STARTUP_TIMEOUT_SEC}" \
"${VENV_DIR}/bin/python" - <<'PY'
import json
import os
import sys
import time
import urllib.request

host = os.environ["SMOKE_HOST"]
port = int(os.environ["SMOKE_PORT"])
token = os.environ["SMOKE_TOKEN"]
log_file = os.environ["SMOKE_LOG_FILE"]
startup_timeout_sec = float(os.environ["SMOKE_STARTUP_TIMEOUT_SEC"])


def read_log() -> str:
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except FileNotFoundError:
        return ""


def get_json(path: str):
    req = urllib.request.Request(f"http://{host}:{port}{path}")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
        return resp.status, payload


deadline = time.time() + startup_timeout_sec
last_error = "service did not start"
while time.time() < deadline:
    try:
        status, payload = get_json("/health")
    except Exception as exc:  # noqa: BLE001
        last_error = str(exc)
        time.sleep(0.25)
        continue
    if status == 200 and payload.get("ok") is True:
        break
else:
    log = read_log()
    print("Smoke startup failed", file=sys.stderr)
    print(last_error, file=sys.stderr)
    if log:
        print(log, file=sys.stderr)
    raise SystemExit(1)

status, caps = get_json("/v1/capabilities")
if status != 200:
    raise SystemExit(f"Unexpected status from /v1/capabilities: {status}")
if caps.get("workspace") is not True:
    raise SystemExit("Capabilities response is missing workspace=true")
roots = caps.get("workspace_roots") or []
if not roots:
    raise SystemExit("Capabilities response is missing workspace_roots")

print("Smoke check passed")
print(json.dumps({
    "health_ok": True,
    "capabilities_ok": True,
    "workspace_roots": roots,
}, ensure_ascii=False))
PY
