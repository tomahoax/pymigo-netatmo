"""Serialized OAuth authentication and refresh-token lifecycle."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import aiohttp

from ..const import API_AUTH_URL, GRANT_TYPE_PASSWORD, GRANT_TYPE_REFRESH, SCOPE, TOKEN_EXPIRY_BUFFER
from ..exceptions import MigoApiError, MigoAuthError, MigoConnectionError
from ..redaction import mask_email
from ..tokens import TokenStore
from .transport import _as_json_object

_LOGGER = logging.getLogger(__name__)


class AuthMixin:
    if TYPE_CHECKING:
        _access_token: str | None
        _refresh_token: str | None
        _token_expiry: datetime | None
        _client_id: str
        _client_secret: str
        _user_prefix: str
        _username: str
        _password: str
        _timeout: aiohttp.ClientTimeout
        _token_store: TokenStore
        _token_loaded: bool
        _auth_lock: asyncio.Lock

        async def _get_session(self) -> aiohttp.ClientSession: ...

    def _build_auth_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/x-www-form-urlencoded", "Accept": "*/*"}

    async def _exchange(self, data: dict[str, str], *, preserve_refresh: bool = False) -> bool:
        session = await self._get_session()
        try:
            async with session.post(
                API_AUTH_URL, data=data, headers=self._build_auth_headers(), timeout=self._timeout
            ) as response:
                if response.status == 429 or response.status >= 500:
                    raise MigoConnectionError(
                        f"Authentication service unavailable: HTTP {response.status}", code=response.status
                    )
                if response.status != 200:
                    raise MigoAuthError(f"Authentication failed: HTTP {response.status}", code=response.status)
                result = _as_json_object(await response.json())
                self._store_tokens(result, preserve_refresh=preserve_refresh)
                await self._token_store.save(self._refresh_token)
                return True
        except ValueError as err:
            raise MigoApiError("Authentication service returned invalid JSON") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise MigoConnectionError(f"Connection error: {err}") from err

    async def authenticate(self) -> bool:
        _LOGGER.debug("Authenticating with Netatmo API for user: %s", mask_email(self._username))
        return await self._exchange(
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": GRANT_TYPE_PASSWORD,
                "username": self._username,
                "password": self._password,
                "user_prefix": self._user_prefix,
                "scope": SCOPE,
            }
        )

    async def refresh_access_token(self) -> bool:
        if not self._refresh_token:
            return await self.authenticate()
        return await self._exchange(
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": GRANT_TYPE_REFRESH,
                "refresh_token": self._refresh_token,
            },
            preserve_refresh=True,
        )

    def _store_tokens(self, token_data: dict[str, Any], preserve_refresh: bool = False) -> None:
        access = token_data.get("access_token")
        if not isinstance(access, str) or not access:
            raise MigoAuthError("Authentication response carried no access token")
        refresh = token_data.get("refresh_token")
        expires = token_data.get("expires_in", 10800)
        if not isinstance(expires, (int, float)) or expires <= 0:
            raise MigoAuthError("Authentication response carried an invalid expiry")
        if refresh is not None and (not isinstance(refresh, str) or not refresh):
            raise MigoAuthError("Authentication response carried an invalid refresh token")
        self._access_token = access
        if refresh is not None or not preserve_refresh:
            self._refresh_token = refresh
        self._token_expiry = datetime.now(UTC) + timedelta(seconds=expires)

    async def _ensure_token_valid(self) -> None:
        async with self._auth_lock:
            if not self._token_loaded:
                self._token_loaded = True
                self._refresh_token = await self._token_store.load()
            if (
                self._access_token
                and self._token_expiry
                and (datetime.now(UTC) < self._token_expiry - timedelta(seconds=TOKEN_EXPIRY_BUFFER))
            ):
                return
            await self.refresh_access_token()

    async def _refresh_after_unauthorized(self, rejected_token: str | None) -> None:
        async with self._auth_lock:
            if self._access_token == rejected_token:
                await self.refresh_access_token()
