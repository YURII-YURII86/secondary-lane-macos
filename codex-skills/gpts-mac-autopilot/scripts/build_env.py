#!/usr/bin/env python3
import argparse
import json
import secrets
from pathlib import Path


def find_branch_root(raw_root: Path) -> Path:
    candidates = [raw_root, raw_root / "Версия для Мак"]
    for candidate in candidates:
        if (candidate / ".env.example").exists():
            return candidate
    raise SystemExit("Could not find macOS project root with .env.example")


def parse_lines(text: str):
    return text.splitlines()


def set_key(lines, key, value):
    prefix = f"{key}="
    output = []
    replaced = False
    for line in lines:
        if line.startswith(prefix):
            output.append(f"{prefix}{value}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(f"{prefix}{value}")
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", help="Workspace root or macOS branch root")
    parser.add_argument("--ngrok-domain", required=True, help="Raw domain only, without https://")
    parser.add_argument("--workspace-root", help="macOS root to place first in WORKSPACE_ROOTS")
    parser.add_argument("--agent-token", help="Optional pre-generated AGENT_TOKEN")
    args = parser.parse_args()

    branch_root = find_branch_root(Path(args.project_root).expanduser().resolve())
    env_example_path = branch_root / ".env.example"
    env_path = branch_root / ".env"
    base_text = env_path.read_text(encoding="utf-8") if env_path.exists() else env_example_path.read_text(encoding="utf-8")
    lines = parse_lines(base_text)

    workspace_root = args.workspace_root.strip() if args.workspace_root else str(branch_root)
    if not workspace_root.startswith("/"):
        raise SystemExit(f"workspace root must look like a macOS path, got: {workspace_root}")

    agent_token = args.agent_token or secrets.token_urlsafe(48)
    ngrok_domain = args.ngrok_domain.replace("https://", "").strip().strip("/")

    workspace_roots = ":".join([workspace_root, str(Path.home() / "Documents"), "/workspace"])
    lines = set_key(lines, "AGENT_TOKEN", agent_token)
    lines = set_key(lines, "NGROK_DOMAIN", ngrok_domain)
    lines = set_key(lines, "WORKSPACE_ROOTS", workspace_roots)
    lines = set_key(lines, "ENABLED_PROVIDER_MANIFESTS", str(branch_root / "app" / "providers"))
    lines = set_key(lines, "STATE_DB_PATH", str(branch_root / "data" / "agent.db"))

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "env_path": str(env_path),
        "branch_root": str(branch_root),
        "workspace_root": workspace_root,
        "ngrok_domain": ngrok_domain,
        "agent_token_generated": args.agent_token is None,
        "agent_token_preview": f"{agent_token[:6]}...{agent_token[-4:]}" if len(agent_token) >= 10 else "***",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
