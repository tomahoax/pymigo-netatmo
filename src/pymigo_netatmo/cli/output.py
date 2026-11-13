"""Output and confirmation helpers shared by every command."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any

from ..redaction import redact


class UsageError(Exception):
    """A call the command line cannot honour, for example an ambiguous home."""


def emit(payload: dict[str, Any], lines: Sequence[str], as_json: bool) -> None:
    """Print one JSON object with `--json`, plain text lines otherwise."""
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("\n".join(lines))


def emit_json(data: Any, redact_values: bool) -> None:
    """Print raw backend data as indented JSON, with sensitive values replaced on request."""
    print(json.dumps(redact(data) if redact_values else data, indent=2, ensure_ascii=False))


def confirm(question: str, assume_yes: bool) -> bool:
    """Ask before driving the heating. Without a terminal, refuse rather than proceed."""
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print(f"{question} No terminal to ask on, pass --yes to confirm.", file=sys.stderr)
        return False
    try:
        # The prompt goes to stderr, so a `--json` stdout stays parseable.
        print(f"{question} [y/N] ", end="", file=sys.stderr, flush=True)
        answer = input("")
    except EOFError:
        return False
    return answer.strip().lower() in {"y", "yes"}
