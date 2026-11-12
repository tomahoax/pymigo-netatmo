"""Token persistence, session ownership and CLI behavior."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from pymigo_netatmo import MigoClient, MigoConnectionError, cli
from pymigo_netatmo.tokens import FileTokenStore


async def test_file_store_private_account_bound_and_clear(tmp_path):
    path = tmp_path / "nested" / "token.json"
    store = FileTokenStore(path, account="User@Example.com")
    assert await store.load() is None
    await store.save("secret")
    assert await store.load() == "secret"
    assert path.stat().st_mode & 0o777 == 0o600
    assert await FileTokenStore(path, account="other").load() is None
    path.write_text("[]")
    assert await store.load() is None
    path.write_text("{bad json")
    assert await store.load() is None
    await store.save(None)
    assert not path.exists()


async def test_owned_session_is_closed_and_injected_closed_session_rejected():
    client = MigoClient("u", "p")
    session = await client._get_session()
    await client.close()
    assert session.closed
    injected = MigoClient("u", "p", session=session)
    with pytest.raises(MigoConnectionError):
        await injected._get_session()


def test_cli_parser_is_readonly_and_requires_username(monkeypatch):
    monkeypatch.delenv("MIGO_USERNAME", raising=False)
    monkeypatch.setattr("sys.argv", ["pymigo-netatmo"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    with pytest.raises(SystemExit):
        cli.parser().parse_args(["set-temperature", "21"])


async def test_cli_reads_and_prints_json(monkeypatch, capsys):
    from pymigo_netatmo.models import AccountSnapshot

    client = MagicMock()
    client.ensure_authenticated = AsyncMock()
    account = MagicMock()
    account.read_snapshot = AsyncMock(return_value=AccountSnapshot())
    monkeypatch.setenv("MIGO_PASSWORD", "password")
    monkeypatch.setattr(cli, "MigoClient", lambda *args, **kwargs: client)
    monkeypatch.setattr(cli, "MigoAccount", lambda *args: account)
    await cli._read("u", Path("unused-token"))
    assert json.loads(capsys.readouterr().out) == {"homes": {}, "rooms": {}, "devices": {}, "consumption": {}}
