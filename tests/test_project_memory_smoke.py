# Second Lane
# Copyright (c) 2026 Yurii Slepnev
# Licensed under the Apache License, Version 2.0.
# Official: https://t.me/yurii_yurii86 | https://youtube.com/@yurii_yurii86 | https://instagram.com/yurii_yurii86

from __future__ import annotations

from pathlib import Path
import os

os.environ.setdefault('AGENT_TOKEN', 'x' * 32)

from app.core.project_memory import ensure_memory, snapshot_memory


def test_memory_bootstrap(tmp_path: Path) -> None:
    ensure_memory(tmp_path, 'tmp-project')
    snap = snapshot_memory(tmp_path)
    assert 'system_state.json' in snap
    assert 'active_tasks.json' in snap


def test_memory_snapshot_compacts_jsonl_tail(tmp_path: Path) -> None:
    mem = ensure_memory(tmp_path, 'tmp-project')
    sessions = mem / 'sessions.jsonl'
    sessions.write_text(''.join([f'{{"idx": {i}}}\n' for i in range(8)]), encoding='utf-8')
    snap = snapshot_memory(tmp_path)
    summary = snap['sessions.jsonl']
    assert summary['type'] == 'jsonl'
    assert summary['line_count'] == 8
    assert summary['truncated'] is True
    assert len(summary['tail']) == 5
    assert summary['tail'][-1]['idx'] == 7
