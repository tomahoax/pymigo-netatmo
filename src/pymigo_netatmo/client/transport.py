"""Low-level HTTP transport, JSON boundary and logging helpers for the API client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

import aiohttp

from ..exceptions import MigoApiError, MigoAuthError, MigoConnectionError
from ..redaction import redact

_LOGGER = logging.getLogger(__name__)

# Server error bodies reach a user-facing notification, so they are truncated
# there. The untruncated text still goes to the debug log.
ERROR_BODY_MAX_LENGTH: Final = 200

# Opt-in channel for unredacted payloads. A child logger inherits its parent's
# level, so checking the EFFECTIVE level here would defeat the whole point: it
# would go live the moment anyone debugs the integration normally. Only an
# explicit `pymigo_netatmo.raw: debug` in Home Assistant's
# logger configuration sets a level on this logger itself.
#
# Hardcoded rather than derived from __name__: this exact name is documented
# in docs/troubleshooting.md, and must not change just because this code
# lives in api/transport.py rather than a flat api.py.
_RAW_LOGGER = logging.getLogger("pymigo_netatmo.raw")


def _raw_logging_enabled() -> bool:
    """Return True only when the raw logger's own level was set explicitly."""
    return _RAW_LOGGER.level == logging.DEBUG


def _log_payload(label: str, payload: Any) -> None:
    """Log an API payload, with sensitive values redacted by default.

    The redacted form keeps the full structure, so it is still useful for
    diagnosing an undocumented backend, but the account email, the home's GPS
    coordinates, the invitation code and hardware serials come out replaced.

    Args:
        label: Human-readable description of what is being logged.
        payload: The request or response payload.
    """
    if _raw_logging_enabled():
        _RAW_LOGGER.debug("%s (raw, unredacted): %s", label, payload)
    elif _LOGGER.isEnabledFor(logging.DEBUG):
        # Guarded: redact() copies the whole payload, and this runs on every
        # poll. No point paying for it when DEBUG is off.
        _LOGGER.debug("%s: %s", label, redact(payload))


def _as_json_object(payload: object) -> dict[str, Any]:
    """Return payload as a JSON object, or raise if it is not one.

    aiohttp's response.json() is typed Any, so without this every caller would
    silently treat a JSON array or scalar as if it were a mapping. This is the
    one place the untrusted wire format becomes a typed value.

    Args:
        payload: The decoded JSON payload.

    Returns:
        The payload, as a JSON object.

    Raises:
        MigoApiError: If the payload is not a JSON object.
    """
    if not isinstance(payload, dict):
        raise MigoApiError(f"Expected a JSON object from the API, got {type(payload).__name__}")
    return payload


def _summarise_error_body(body: str) -> str:
    """Return a short, safe form of a server error body for a user-facing error.

    The full body ends up in a Home Assistant error notification through the
    api_error translation placeholder, which gives an untrusted backend an
    arbitrary-text channel into the frontend, usable for phishing. The complete
    text is still written to the debug log, where it is genuinely useful.

    Args:
        body: The raw response body.

    Returns:
        The body collapsed to one line and truncated.
    """
    collapsed = " ".join(body.split())
    if len(collapsed) <= ERROR_BODY_MAX_LENGTH:
        return collapsed
    return collapsed[:ERROR_BODY_MAX_LENGTH] + "..."


class TransportMixin:
    """Mixin providing the shared authenticated-request path.

    Combined into `MigoApi` alongside `AuthMixin` (token lifecycle) and the
    read/write endpoint mixins - see `api/client.py`. The attributes and
    methods declared under TYPE_CHECKING below are provided by the other
    mixins/`MigoApi.__init__` once assembled; declared here only so this
    mixin type-checks on its own.
    """

    if TYPE_CHECKING:
        _access_token: str | None
        _timeout: aiohttp.ClientTimeout

        async def _get_session(self) -> aiohttp.ClientSession: ...
        async def _ensure_token_valid(self) -> None: ...
        async def authenticate(self) -> bool: ...
        async def _refresh_after_unauthorized(self, rejected_token: str | None) -> None: ...

    def _build_api_headers(self, use_json: bool = True) -> dict[str, str]:
        """Build headers for authenticated API requests.

        Args:
            use_json: Whether to use JSON content type.

        Returns:
            Dictionary of HTTP headers.
        """
        content_type = "application/json" if use_json else "application/x-www-form-urlencoded"
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": content_type,
            "Accept": "*/*",
        }

    async def _api_request(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        method: str = "POST",
        use_json: bool = True,
    ) -> dict[str, Any]:
        """Issue a request; retry reads once after 401, never replay a write."""
        await self._ensure_token_valid()
        session = await self._get_session()
        # Read endpoints also use POST. HTTP method alone cannot establish safety.
        is_read = url.rsplit("/", 1)[-1] in {"homesdata", "homestatus", "getconfigs", "getmeasure"}
        for attempt in range(2):
            rejected_token = self._access_token
            kwargs: dict[str, Any] = {"headers": self._build_api_headers(use_json)}
            if data is not None:
                kwargs["json" if use_json else "data"] = data
                _log_payload("API request payload", data)
            try:
                async with session.request(method, url, timeout=self._timeout, **kwargs) as response:
                    if response.status == 401:
                        if attempt:
                            raise MigoAuthError("API authentication rejected after refresh", code=401)
                        # Exit the response context before renewing credentials.
                        unauthorized = True
                    else:
                        unauthorized = False
                        if response.status >= 400:
                            body = await response.text()
                            raise MigoApiError(
                                f"API returned {response.status}: {_summarise_error_body(body)}",
                                code=response.status,
                            )
                        result = _as_json_object(await response.json())
                        error = result.get("error")
                        if error:
                            code = error.get("code") if isinstance(error, dict) else None
                            raise MigoApiError("API returned an error payload", code=code)
                        _log_payload("API response data", result)
                        return result
                if unauthorized:
                    await self._refresh_after_unauthorized(rejected_token)
                    if not is_read:
                        raise MigoAuthError("Write rejected; credentials renewed without replaying it", code=401)
            except (aiohttp.ClientError, TimeoutError) as err:
                raise MigoConnectionError(f"Connection error: {err}") from err
            except ValueError as err:
                raise MigoApiError("API returned invalid JSON") from err
        raise MigoAuthError("API authentication rejected", code=401)
