#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

MARKERS = {
    "env_example": ".env.example",
    "launcher": "Запустить Second Lane.command",
    "openapi": "openapi.gpts.yaml",
    "system_instructions": "gpts/system_instructions.txt",
    "knowledge_dir": "gpts/knowledge",
    "control": "gpts_agent_control.py",
    "mac_first_start": "docs/MAC_FIRST_START.md",
}
PATH_PENALTIES = {"бэкап": 3, "backup": 3, ".ai_context": 4, "checkpoints": 4, "__pycache__": 5, ".git": 5}
PATH_BONUSES = {"версия для мак": 3, "secondlane": 1}
PATH_SOFT_PENALTIES = {"версия для виндовс": 3, "windows": 3, "боевой проект": 2, "starter": 2, "стартер": 2}


def score_candidate(path: Path):
    found = {}
    score = 0
    for key, relative in MARKERS.items():
        exists = (path / relative).exists()
        found[key] = {"relative": relative, "exists": exists, "path": str(path / relative)}
        if exists:
            score += 1
    lowered = str(path).lower()
    penalty_hits = [token for token in PATH_PENALTIES if token in lowered]
    penalty = sum(PATH_PENALTIES[token] for token in penalty_hits)
    bonus_hits = [token for token in PATH_BONUSES if token in lowered]
    bonus = sum(PATH_BONUSES[token] for token in bonus_hits)
    soft_penalty_hits = [token for token in PATH_SOFT_PENALTIES if token in lowered]
    soft_penalty = sum(PATH_SOFT_PENALTIES[token] for token in soft_penalty_hits)
    effective_score = score + bonus - penalty - soft_penalty
    return score, effective_score, penalty, penalty_hits, found, bonus, bonus_hits, soft_penalty, soft_penalty_hits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("search_root")
    parser.add_argument("--max-depth", type=int, default=4)
    args = parser.parse_args()
    root = Path(args.search_root).expanduser().resolve()

    # Bounded BFS instead of root.rglob("*") which previously walked
    # the entire subtree (potentially millions of files under iCloud,
    # Time Machine or ~/Library) and blew up on TCC-protected dirs.
    SKIP_DIRS = {
        ".git", "__pycache__", "node_modules",
        ".venv", "venv", ".idea", ".vscode",
        "Library", "Pictures", "Movies", "Music",
    }
    candidates = []
    frontier: list[tuple[Path, int]] = [(root, 0)]
    while frontier:
        current, depth = frontier.pop(0)
        candidates.append(current)
        if depth >= args.max_depth:
            continue
        try:
            children = list(current.iterdir())
        except (PermissionError, OSError):
            continue
        for child in children:
            try:
                if not child.is_dir():
                    continue
            except (PermissionError, OSError):
                continue
            name = child.name
            if name in SKIP_DIRS:
                continue
            if name.startswith(".") and name not in ("."):
                continue
            frontier.append((child, depth + 1))
    results = []
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        score, effective, penalty, hits, found, bonus, bonus_hits, soft_penalty, soft_penalty_hits = score_candidate(candidate)
        if score == 0:
            continue
        results.append({
            "candidate_root": str(candidate),
            "score": score,
            "effective_score": effective,
            "path_penalty": penalty,
            "path_penalty_hits": hits,
            "path_bonus": bonus,
            "path_bonus_hits": bonus_hits,
            "path_soft_penalty": soft_penalty,
            "path_soft_penalty_hits": soft_penalty_hits,
            "markers": found,
        })
    results.sort(key=lambda item: (-item["effective_score"], -item["score"], item["candidate_root"]))
    print(json.dumps({"search_root": str(root), "best_match": results[0] if results else None, "candidates": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
