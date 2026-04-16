# Second Lane
# Copyright (c) 2026 Yurii Slepnev
# Licensed under the Apache License, Version 2.0.
# Official: https://t.me/yurii_yurii86 | https://youtube.com/@yurii_yurii86 | https://instagram.com/yurii_yurii86

from __future__ import annotations

from pathlib import Path
import os

from fastapi.testclient import TestClient
import app.main as main


def test_health_requires_auth_and_then_works() -> None:
    client = TestClient(main.app)
    assert client.get('/health').status_code == 401
    resp = client.get('/health', headers={'Authorization': 'Bearer ' + main.settings.agent_token})
    assert resp.status_code == 200


def test_capabilities_returns_workspace_roots() -> None:
    client = TestClient(main.app)
    resp = client.get('/v1/capabilities', headers={'Authorization': 'Bearer ' + main.settings.agent_token})
    assert resp.status_code == 200
    assert 'workspace_roots' in resp.json()
