#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_branch_root  # noqa: E402


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
