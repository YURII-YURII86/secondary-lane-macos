# Second Lane
# Copyright (c) 2026 Yurii Slepnev
# Licensed under the Apache License, Version 2.0.
# Official: https://t.me/yurii_yurii86 | https://youtube.com/@yurii_yurii86 | https://instagram.com/yurii_yurii86

from __future__ import annotations

from fastapi import Header, HTTPException, status

from .config import Settings


def require_auth(settings: Settings, authorization: str | None = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization[len(prefix):].strip()
    if token != settings.agent_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bearer token")
