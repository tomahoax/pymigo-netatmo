"""Entry point: argument parsing, authentication, dispatch and exit codes."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import logging
import os
import sys
from collections.abc import Sequence

import aiohttp

from ..client import MigoClient
from ..exceptions import MigoError, Remedy
from ..tokens import FileTokenStore
from .commands import COMMANDS, check, cmd_logout, describe, needs_confirmation
from .exit_codes import EXIT_AUTH, EXIT_ERROR, EXIT_INTERRUPTED, EXIT_RETRY, EXIT_USAGE
from .output import UsageError, confirm
from .parser import build_parser

__all__ = ["main"]


def _password(args: argparse.Namespace, store: FileTokenStore | None) -> str:
    """The password: the environment, a prompt, or none when a stored token is enough.

    The prompt runs on the main thread, outside any event loop. Ctrl+C then interrupts it at
    once. In a worker thread, it would keep the process waiting for Enter.
    """
    password = os.environ.get("MIGO_PASSWORD") or ""
    if password:
        return password
    # `login` validates the password itself, so it never settles for a stored token.
    if args.command != "login" and store is not None and asyncio.run(store.load()) is not None:
        return ""
    return getpass.getpass("MiGO password: ") or ""


async def _run(args: argparse.Namespace, password: str, store: FileTokenStore | None) -> int:
    async with aiohttp.ClientSession() as session:
        client = MigoClient(
            args.username,
            password,
            session=session,
            client_id=args.client_id,
            client_secret=os.environ.get("MIGO_CLIENT_SECRET"),
            user_prefix=args.user_prefix,
            token_store=store,
        )
        if args.command != "login":
            await client.ensure_authenticated()
        return await COMMANDS[args.command](args, client)


_EXIT_BY_REMEDY = {Remedy.REAUTHENTICATE: EXIT_AUTH, Remedy.RETRY: EXIT_RETRY}


def _report(err: MigoError, as_json: bool) -> int:
    """Print the structured error on stderr and map its remedy to an exit code."""
    if as_json:
        error = {"message": str(err), "code": err.code, "remedy": err.remedy.value, "placeholders": err.placeholders}
        print(json.dumps({"error": error}, ensure_ascii=False), file=sys.stderr)
    else:
        details = f"remedy={err.remedy.value}" if err.code is None else f"code={err.code}, remedy={err.remedy.value}"
        print(f"Error: {err} [{details}]", file=sys.stderr)
    return _EXIT_BY_REMEDY.get(err.remedy, EXIT_ERROR)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        args.command = "snapshot"
    # `logout` only deletes a file, so it needs no account.
    if not args.username and args.command != "logout":
        parser.error("--username or MIGO_USERNAME is required")
    if message := check(args):
        parser.error(message)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.raw_log:
        # The library only trusts a level set on this logger itself, never an inherited one.
        logging.getLogger("pymigo_netatmo.raw").setLevel(logging.DEBUG)
        print("Raw logging is on: payloads on stderr hold personal data.", file=sys.stderr)

    # Ask before anything is sent, and before any password prompt.
    if needs_confirmation(args.command) and not confirm(f"Really {describe(args)}?", args.yes):
        return EXIT_USAGE
    try:
        if args.command == "logout":
            return asyncio.run(cmd_logout(args))
        store = FileTokenStore(args.token_file, account=args.username) if args.token_file else None
        return asyncio.run(_run(args, _password(args, store), store))
    except UsageError as err:
        print(f"{err}.", file=sys.stderr)
        return EXIT_USAGE
    except MigoError as err:
        return _report(err, args.json)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return EXIT_INTERRUPTED
