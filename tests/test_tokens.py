"""Token persistence and session ownership."""

import pytest

from pymigo_netatmo import MigoClient, MigoConnectionError
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
