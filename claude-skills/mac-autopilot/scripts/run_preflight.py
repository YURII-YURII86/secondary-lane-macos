#!/usr/bin/env python3
"""Preflight check для Claude Code Autopilot.

Запускать из корня репозитория:
    python3 claude-skills/mac-autopilot/scripts/run_preflight.py [search_root]

Выводит JSON-отчёт о текущем реальном состоянии всех компонентов
Second Lane. Claude Code использует этот вывод для определения
начального состояния (S0) и выбора следующего шага.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Добавить путь к shared helpers из codex-skills/gpts-mac-autopilot/scripts/
# Структура: claude-skills/mac-autopilot/scripts/ → ../../../codex-skills/gpts-mac-autopilot/scripts/
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "codex-skills" / "gpts-mac-autopilot" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from _common import find_branch_root  # noqa: E402


def _run(argv: list, timeout: int = 8) -> dict:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "stdout": r.stdout.strip()[:500],
            "stderr": r.stderr.strip()[:500],
        }
    except FileNotFoundError:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": f"command not found: {argv[0]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": "timeout"}


def _curl_json(url: str, token: str | None = None, timeout: int = 5) -> dict:
    """Hit a local URL and parse JSON. Returns {ok, status_code, body}."""
    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(url)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
            return {"ok": True, "status_code": resp.status, "body": body}
    except Exception as exc:
        return {"ok": False, "status_code": None, "body": None, "error": str(exc)}


def _parse_env(env_path: Path) -> dict:
    if not env_path.exists():
        return {}
    result = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        result[k.strip()] = v.strip()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Second Lane preflight check")
    parser.add_argument("search_root", nargs="?", default=".", help="Where to search for the project root")
    args = parser.parse_args()

    search_root = Path(args.search_root).expanduser().resolve()
    report: dict = {"search_root": str(search_root)}

    # ── 1. Project root discovery ─────────────────────────────────────
    try:
        branch_root = find_branch_root(search_root)
        report["branch_root"] = str(branch_root)
        report["branch_root_found"] = True
    except SystemExit as exc:
        report["branch_root_found"] = False
        report["branch_root_error"] = str(exc)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(1)

    # ── 2. Python versions ────────────────────────────────────────────
    python_checks = {}
    for candidate in ("python3.13", "python3.12", "python3"):
        if shutil.which(candidate):
            r = _run([candidate, "--version"])
            python_checks[candidate] = {"available": True, "version": r["stdout"] or r["stderr"]}
        else:
            python_checks[candidate] = {"available": False}
    report["python"] = python_checks
    report["python_ok"] = any(v["available"] for v in python_checks.values())

    # ── 3. venv ───────────────────────────────────────────────────────
    venv_path = branch_root / ".venv"
    venv_python = venv_path / "bin" / "python"
    report["venv"] = {
        "exists": venv_path.exists(),
        "python_path": str(venv_python),
        "dependencies_ok": False,
    }
    if venv_python.exists():
        dep_check = _run([str(venv_python), "-c", "import fastapi, uvicorn, pydantic; print('OK')"])
        report["venv"]["dependencies_ok"] = dep_check["ok"]
        report["venv"]["dep_check_output"] = dep_check["stdout"] or dep_check["stderr"]

    # ── 4. .env ───────────────────────────────────────────────────────
    env_path = branch_root / ".env"
    env_values = _parse_env(env_path)
    report["env"] = {
        "path": str(env_path),
        "exists": env_path.exists(),
        "agent_token_present": bool(env_values.get("AGENT_TOKEN")),
        "ngrok_domain": env_values.get("NGROK_DOMAIN", ""),
        "workspace_roots": env_values.get("WORKSPACE_ROOTS", ""),
        "complete": bool(
            env_values.get("AGENT_TOKEN")
            and env_values.get("NGROK_DOMAIN")
            and env_values.get("WORKSPACE_ROOTS")
        ),
    }

    # ── 5. ngrok CLI ──────────────────────────────────────────────────
    ngrok_result = _run(["ngrok", "version"])
    ngrok_config = _run(["ngrok", "config", "check"])
    report["ngrok"] = {
        "available": shutil.which("ngrok") is not None,
        "version": ngrok_result.get("stdout", "") or ngrok_result.get("stderr", ""),
        "config_ok": ngrok_config["ok"],
        "config_output": ngrok_config["stdout"] or ngrok_config["stderr"],
    }

    # ── 6. Panel running? ─────────────────────────────────────────────
    panel = _curl_json("http://localhost:8787/v1/capabilities")
    report["panel"] = {
        "running": panel["ok"],
        "status_code": panel.get("status_code"),
        "capabilities_ok": panel.get("body", {}).get("ok") if panel["ok"] else False,
    }

    # ── 7. ngrok tunnel running? ──────────────────────────────────────
    ngrok_api = _curl_json("http://localhost:4040/api/tunnels")
    public_url = ""
    if ngrok_api["ok"] and ngrok_api.get("body"):
        tunnels = ngrok_api["body"].get("tunnels", [])
        https_tunnels = [t for t in tunnels if t.get("proto") == "https"]
        public_url = https_tunnels[0]["public_url"] if https_tunnels else ""
    report["tunnel"] = {
        "running": ngrok_api["ok"],
        "public_url": public_url,
    }

    # ── 8. openapi.gpts.yaml URL ──────────────────────────────────────
    openapi_path = branch_root / "openapi.gpts.yaml"
    yaml_url = ""
    if openapi_path.exists():
        import re
        text = openapi_path.read_text(encoding="utf-8")
        m = re.search(r"- url:\s*(https?://\S+)", text)
        yaml_url = m.group(1) if m else ""
    report["openapi"] = {
        "exists": openapi_path.exists(),
        "server_url": yaml_url,
        "url_matches_tunnel": bool(yaml_url and public_url and yaml_url.rstrip("/") == public_url.rstrip("/")),
    }

    # ── 9. Recommended next state ─────────────────────────────────────
    if not report["python_ok"]:
        report["suggested_state"] = "S1"
    elif not report["ngrok"]["available"]:
        report["suggested_state"] = "S2"
    elif not report["ngrok"]["config_ok"]:
        report["suggested_state"] = "S3"
    elif not report["env"]["complete"]:
        report["suggested_state"] = "S4"
    elif not report["venv"]["dependencies_ok"]:
        report["suggested_state"] = "S5"
    elif not report["panel"]["running"]:
        report["suggested_state"] = "S6"
    elif not report["tunnel"]["running"]:
        report["suggested_state"] = "S7"
    elif not report["openapi"]["url_matches_tunnel"]:
        report["suggested_state"] = "S8"
    else:
        report["suggested_state"] = "S9+"

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
