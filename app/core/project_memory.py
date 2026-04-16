# Second Lane
# Copyright (c) 2026 Yurii Slepnev
# Licensed under the Apache License, Version 2.0.
# Official: https://t.me/yurii_yurii86 | https://youtube.com/@yurii_yurii86 | https://instagram.com/yurii_yurii86

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from .utils import unified_diff


SNAPSHOT_JSONL_TAIL = 5
SNAPSHOT_TEXT_LIMIT = 8000


MEMORY_FILES = {
    "system_state.json": "{}\n",
    "active_tasks.json": "{}\n",
    "decision_log.md": "# Decision Log\n",
    "dependency_graph.md": "# Dependency Graph\n",
    "handoff.md": "# Handoff\n",
    "project_brief.md": "# Project Brief\n",
    "sessions.jsonl": "",
    "change_log.jsonl": "",
}


def _summarize_jsonl(path: Path) -> dict:
    lines = path.read_text("utf-8").splitlines()
    tail = []
    for line in lines[-SNAPSHOT_JSONL_TAIL:]:
        try:
            tail.append(json.loads(line))
        except json.JSONDecodeError:
            tail.append(line)
    return {
        "type": "jsonl",
        "line_count": len(lines),
        "tail": tail,
        "truncated": len(lines) > SNAPSHOT_JSONL_TAIL,
    }


def _summarize_text(path: Path) -> str | dict:
    text = path.read_text("utf-8")
    if len(text) <= SNAPSHOT_TEXT_LIMIT:
        return text
    return {
        "type": "text",
        "preview": text[:SNAPSHOT_TEXT_LIMIT],
        "total_chars": len(text),
        "truncated": True,
    }


def memory_dir(project_root: Path) -> Path:
    return project_root / ".ai_context"


def ensure_memory(project_root: Path, project_name: str | None = None) -> Path:
    mem = memory_dir(project_root)
    mem.mkdir(parents=True, exist_ok=True)
    for name, default in MEMORY_FILES.items():
        target = mem / name
        if not target.exists():
            target.write_text(default, "utf-8")
    system_state = mem / "system_state.json"
    if project_name and system_state.exists():
        try:
            payload = json.loads(system_state.read_text("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        payload.setdefault("project_name", project_name)
        system_state.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8")
    (mem / "checkpoints").mkdir(exist_ok=True)
    return mem


def snapshot_memory(project_root: Path) -> dict:
    mem = ensure_memory(project_root)
    snapshot: dict[str, str | dict | list] = {}
    for file_path in sorted(mem.iterdir()):
        if file_path.is_dir():
            continue
        if file_path.suffix == ".json":
            try:
                snapshot[file_path.name] = json.loads(file_path.read_text("utf-8") or "{}")
            except json.JSONDecodeError:
                snapshot[file_path.name] = _summarize_text(file_path)
        elif file_path.suffix == ".jsonl":
            snapshot[file_path.name] = _summarize_jsonl(file_path)
        else:
            snapshot[file_path.name] = _summarize_text(file_path)
    return snapshot


def append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8")


def write_markdown_section(path: Path, title: str, lines: list[str]) -> None:
    content = [f"# {title}"]
    content.extend(lines)
    path.write_text("\n".join(content) + "\n", "utf-8")


def create_checkpoint(project_root: Path, include_paths: list[str], note: str | None = None) -> dict:
    mem = ensure_memory(project_root)
    checkpoint_id = uuid.uuid4().hex[:12]
    cp_dir = mem / "checkpoints" / checkpoint_id
    cp_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for rel in include_paths:
        source = (project_root / rel).resolve()
        if not source.exists():
            continue
        target = cp_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)
        copied.append(rel)
    meta = {"checkpoint_id": checkpoint_id, "note": note or "", "include_paths": copied}
    write_json(cp_dir / "_meta.json", meta)
    return meta


def list_checkpoints(project_root: Path) -> list[dict]:
    mem = ensure_memory(project_root)
    out = []
    for cp_dir in sorted((mem / "checkpoints").glob("*"), reverse=True):
        meta_file = cp_dir / "_meta.json"
        if not meta_file.exists():
            continue
        try:
            out.append(json.loads(meta_file.read_text("utf-8")))
        except json.JSONDecodeError:
            continue
    return out


def rollback_checkpoint(project_root: Path, checkpoint_id: str | None = None) -> dict:
    checkpoints = list_checkpoints(project_root)
    if not checkpoints:
        return {"ok": False, "detail": "no checkpoints"}
    meta = next((item for item in checkpoints if item["checkpoint_id"] == checkpoint_id), checkpoints[0])
    cp_dir = ensure_memory(project_root) / "checkpoints" / meta["checkpoint_id"]
    restored = []
    for item in cp_dir.rglob("*"):
        if item.name == "_meta.json":
            continue
        rel = item.relative_to(cp_dir)
        target = project_root / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        restored.append(str(rel))
    return {"ok": True, "checkpoint_id": meta["checkpoint_id"], "restored": restored}


def summarize_changes(project_root: Path, checkpoint_id: str | None = None, include_paths: list[str] | None = None) -> dict:
    checkpoints = list_checkpoints(project_root)
    if not checkpoints:
        return {"ok": False, "detail": "no checkpoints"}
    meta = next((item for item in checkpoints if item["checkpoint_id"] == checkpoint_id), checkpoints[0])
    cp_dir = ensure_memory(project_root) / "checkpoints" / meta["checkpoint_id"]
    paths = include_paths or meta.get("include_paths", [])
    diffs: list[dict] = []
    for rel in paths:
        before_path = cp_dir / rel
        after_path = project_root / rel
        before = before_path.read_text("utf-8") if before_path.exists() and before_path.is_file() else ""
        after = after_path.read_text("utf-8") if after_path.exists() and after_path.is_file() else ""
        diff = unified_diff(before, after, f"{rel}@checkpoint", rel)
        diffs.append({"path": rel, "changed": before != after, "diff": diff})
    return {"ok": True, "checkpoint_id": meta["checkpoint_id"], "files": diffs}
