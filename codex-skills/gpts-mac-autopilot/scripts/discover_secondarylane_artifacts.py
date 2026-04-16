#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

TARGETS = {
    "launcher": ["Запустить Second Lane.command"],
    "env_example": [".env.example"],
    "openapi": ["openapi.gpts.yaml"],
    "instructions": ["gpts/system_instructions.txt", "system_instructions.txt"],
    "knowledge": ["gpts/knowledge"],
    "control": ["gpts_agent_control.py"],
}
IGNORE_TOKENS = ["/.ai_context/", "/__pycache__/", "/.git/", "/checkpoints/"]


def is_ignored(path: Path) -> bool:
    normalized = "/" + str(path).replace("\\", "/").lstrip("/")
    return any(token in normalized for token in IGNORE_TOKENS)


def dedupe_keep_order(items):
    seen = set()
    output = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def role_hits(root: Path, role: str, variants):
    hits = []
    if role == "knowledge":
        preferred = root / "gpts" / "knowledge"
        if preferred.is_dir() and not is_ignored(preferred):
            hits.append(str(preferred))
        other_hits = [
            str(path)
            for path in root.rglob("knowledge")
            if path.is_dir() and not is_ignored(path)
        ]
        return dedupe_keep_order(hits + other_hits)

    for variant in variants:
        preferred = root / variant
        if preferred.exists() and not is_ignored(preferred):
            hits.append(str(preferred))
        basename = variant.split("/")[-1]
        for path in root.rglob(basename):
            if is_ignored(path):
                continue
            hits.append(str(path))
    return dedupe_keep_order(hits)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root")
    args = parser.parse_args()
    root = Path(args.project_root).expanduser().resolve()
    found = {role: role_hits(root, role, variants) for role, variants in TARGETS.items()}
    print(json.dumps({"project_root": str(root), "artifacts": found}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
