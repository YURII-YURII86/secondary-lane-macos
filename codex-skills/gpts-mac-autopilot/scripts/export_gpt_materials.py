#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def find_branch_root(raw_root: Path) -> Path:
    candidates = [raw_root, raw_root / "Версия для Мак"]
    for candidate in candidates:
        if (candidate / ".env.example").exists():
            return candidate
    raise SystemExit("Could not find macOS project root with .env.example")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root")
    args = parser.parse_args()
    branch_root = find_branch_root(Path(args.project_root).expanduser().resolve())
    knowledge_root = branch_root / "gpts" / "knowledge"
    output = {
        "instructions": str(branch_root / "gpts" / "system_instructions.txt"),
        "openapi": str(branch_root / "openapi.gpts.yaml"),
        "knowledge_files": sorted(str(path) for path in knowledge_root.rglob("*") if path.is_file()) if knowledge_root.exists() else [],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
