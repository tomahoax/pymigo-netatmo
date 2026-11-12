# pymigo-netatmo

Async Python client for thermostats using **MiGO. Your Heating Assistant** and its
Netatmo backend. Supports Python 3.11 and later. MiGO Link and myVAILLANT use other APIs.

## Read an account

```python
import aiohttp
from pymigo_netatmo import MigoAccount, MigoClient
from pymigo_netatmo.tokens import FileTokenStore


async def read(username, password):
    async with aiohttp.ClientSession() as session:
        client = MigoClient(
            username, password, session=session, token_store=FileTokenStore("tokens.json", account=username)
        )
        await client.ensure_authenticated()
        snapshot = await MigoAccount(client).read_snapshot()
        return snapshot.raw
```

`ensure_authenticated()` loads persisted refresh tokens before using password login.
An explicit refresh rejection (HTTP 400 or 401) falls back once to the supplied
password. Network errors, rate limits and server outages never trigger password
recovery. `authenticate()` explicitly validates the supplied password. The caller owns an
injected session. `close()` only closes sessions created by the client itself.

## Control a home

```python
home = MigoAccount(client).home("home_id")
await home.set_temperature("room_id", 21.5, duration=60)
await home.set_heating_curve("gateway_id", 2.6)
```

Temperature durations are minutes; heating curves and hysteresis use user-facing
units. Wire conversions have one implementation in the private client services.
A read may be retried once after HTTP 401. A write is **never replayed** automatically.

Errors derive from `MigoError` and expose `remedy`, `code` and `placeholders`.
Unknown Netatmo error codes are preserved without guessing their meaning.
`HeatingAlgorithm.UNKNOWN` exists for unsupported values; advanced algorithm values
remain unconfirmed.

## Models and tests

`Home`, `Room`, `Module` and `Consumption` are dataclasses implementing `Mapping`.
`from_json()` accepts missing fields and retains a deep copy in `.raw`. Frozen
containers prevent field reassignment; nested dictionaries remain mutable.
`AccountSnapshot.raw` returns a detached serializable account snapshot.
`pymigo_netatmo.testing.FakeMigo` supports offline consumer setup and writes.

```sh
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy src
pytest --cov=pymigo_netatmo --cov-report=term-missing
```

The CLI is read-only: `pymigo-netatmo --username user@example.com --token-file tokens.json`.
The password comes from an interactive prompt or `MIGO_PASSWORD`. CLI snapshots contain
personal data; the normal logger redacts payloads. Raw logging requires an explicit
`pymigo_netatmo.raw` debug level.

See the [API reference](docs/api/reference.md), [OpenAPI](openapi.yaml) and
[architecture](docs/architecture.md). This is an unofficial, undocumented backend;
real error codes and refresh-token rotation need confirmation from captures.
