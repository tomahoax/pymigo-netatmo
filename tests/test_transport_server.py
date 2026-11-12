"""Exercise real HTTP boundaries without contacting Netatmo."""

from datetime import UTC, datetime, timedelta

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from pymigo_netatmo import MigoApiError, MigoAuthError, MigoClient
from pymigo_netatmo.client import auth
from pymigo_netatmo.tokens import MemoryTokenStore


@pytest.mark.parametrize("endpoint,is_read", [("homesdata", True), ("setstate", False)])
async def test_401_renews_once_and_never_replays_writes(monkeypatch, endpoint, is_read):
    calls = {"resource": 0, "token": []}

    async def token(request):
        calls["token"].append(dict(await request.post()))
        return web.json_response({"access_token": "new", "refresh_token": "rotated", "expires_in": 3600})

    async def resource(request):
        calls["resource"] += 1
        if calls["resource"] == 1:
            return web.Response(status=401)
        return web.json_response({"body": {"homes": []}})

    app = web.Application()
    app.router.add_post("/token", token)
    app.router.add_post("/" + endpoint, resource)
    async with TestServer(app) as server, aiohttp.ClientSession() as session:
        monkeypatch.setattr(auth, "API_AUTH_URL", str(server.make_url("/token")))
        store = MemoryTokenStore("refresh")
        client = MigoClient("u", "p", session=session, token_store=store)
        client._token_loaded = True
        client._refresh_token = "refresh"
        client._access_token = "old"
        client._token_expiry = datetime.now(UTC) + timedelta(hours=1)
        if is_read:
            result = await client._api_request(str(server.make_url("/" + endpoint)))
            assert result["body"]["homes"] == []
        else:
            with pytest.raises(MigoAuthError):
                await client._api_request(str(server.make_url("/" + endpoint)))
        assert calls["resource"] == (2 if is_read else 1)
        assert len(calls["token"]) == 1
        assert calls["token"][0]["grant_type"] == "refresh_token"
        assert await store.load() == "rotated"
        await client.close()
        assert not session.closed


async def test_restart_uses_persisted_refresh_token(monkeypatch):
    grants = []

    async def token(request):
        grants.append((await request.post())["grant_type"])
        return web.json_response({"access_token": "new", "refresh_token": "rotated"})

    app = web.Application()
    app.router.add_post("/token", token)
    async with TestServer(app) as server, aiohttp.ClientSession() as session:
        monkeypatch.setattr(auth, "API_AUTH_URL", str(server.make_url("/token")))
        store = MemoryTokenStore("saved")
        first = MigoClient("u", "p", session=session, token_store=store)
        await first.ensure_authenticated()
        first.clear_credentials()
        second = MigoClient("u", "p", session=session, token_store=store)
        await second.ensure_authenticated()
        assert grants == ["refresh_token", "refresh_token"]


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_auth_service_outage_does_not_request_reauthentication(monkeypatch, status):
    async def token(request):
        return web.Response(status=status)

    app = web.Application()
    app.router.add_post("/token", token)
    async with TestServer(app) as server, aiohttp.ClientSession() as session:
        monkeypatch.setattr(auth, "API_AUTH_URL", str(server.make_url("/token")))
        client = MigoClient("u", "p", session=session)
        with pytest.raises(MigoApiError) as error:
            await client.ensure_authenticated()
        assert not isinstance(error.value, MigoAuthError)
        assert error.value.code == status
