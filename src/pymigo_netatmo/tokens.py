"""Async refresh-token persistence independent of the embedding application."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenStore(Protocol):
    async def load(self) -> str | None:
        """Load a refresh token, if one exists."""

    async def save(self, refresh_token: str | None) -> None:
        """Save or clear a refresh token."""


class MemoryTokenStore:
    def __init__(self, refresh_token: str | None = None) -> None:
        self._token = refresh_token

    async def load(self) -> str | None:
        return self._token

    async def save(self, refresh_token: str | None) -> None:
        self._token = refresh_token


class FileTokenStore:
    """An account-bound private JSON file; disk work runs outside the event loop."""

    def __init__(self, path: str | Path, *, account: str) -> None:
        self._path = Path(path).expanduser()
        self._account = account.casefold()

    async def load(self) -> str | None:
        return await asyncio.to_thread(self._load)

    def _load(self) -> str | None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or data.get("account") != self._account:
            return None
        token = data.get("refresh_token")
        return token if isinstance(token, str) and token else None

    async def save(self, refresh_token: str | None) -> None:
        await asyncio.to_thread(self._save, refresh_token)

    def _save(self, refresh_token: str | None) -> None:
        if refresh_token is None:
            self._path.unlink(missing_ok=True)
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replacement prevents a crash during a refresh from losing the token.
        temporary = self._path.with_name(self._path.name + ".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({"account": self._account, "refresh_token": refresh_token}, handle)
            temporary.chmod(0o600)
            temporary.replace(self._path)
        finally:
            temporary.unlink(missing_ok=True)
