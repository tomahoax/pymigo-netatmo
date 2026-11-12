"""Read-only command line snapshot inspection."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path

import aiohttp

from . import MigoAccount, MigoClient
from .tokens import FileTokenStore


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Read a MiGO account snapshot; no write commands are available.")
    result.add_argument("--username", default=os.environ.get("MIGO_USERNAME"))
    result.add_argument("--token-file", type=Path, help="Persist the refresh token in a private account-bound file")
    return result


async def _read(username: str, token_file: Path | None) -> None:
    store = FileTokenStore(token_file, account=username) if token_file else None
    password = os.environ.get("MIGO_PASSWORD") or ""
    if not password and (store is None or await store.load() is None):
        password = await asyncio.to_thread(getpass.getpass, "MiGO password: ") or ""
    async with aiohttp.ClientSession() as session:
        client = MigoClient(username, password, session=session, token_store=store)
        await client.ensure_authenticated()
        snapshot = await MigoAccount(client).read_snapshot()
        print(json.dumps(snapshot.raw, indent=2, ensure_ascii=False))


def main() -> None:
    arguments = parser()
    args = arguments.parse_args()
    if not args.username:
        arguments.error("--username or MIGO_USERNAME is required")
    asyncio.run(_read(args.username, args.token_file))


if __name__ == "__main__":
    main()
