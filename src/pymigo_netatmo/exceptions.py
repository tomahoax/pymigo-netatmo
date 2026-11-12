"""Consumer-neutral error taxonomy.

Remedies describe the action available to a host application. Unknown API codes
are preserved without guessing which user action would repair them.
"""

from __future__ import annotations

from enum import StrEnum


class Remedy(StrEnum):
    REAUTHENTICATE = "reauthenticate"
    RETRY = "retry"
    CHECK_REQUEST = "check_request"
    UNKNOWN = "unknown"


class MigoError(Exception):
    """Base error with structured information for host applications."""

    remedy = Remedy.UNKNOWN

    def __init__(
        self, message: str, *, code: str | int | None = None, placeholders: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.placeholders = dict(placeholders or {})


class MigoApiError(MigoError):
    """The API rejected the request or returned an invalid payload."""


class MigoAuthError(MigoApiError):
    """The account requires authentication."""

    remedy = Remedy.REAUTHENTICATE


class MigoConnectionError(MigoApiError):
    """The remote service could not be reached."""

    remedy = Remedy.RETRY
