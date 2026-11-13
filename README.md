# pymigo-netatmo

Async Python client for thermostats using **MiGO. Your Heating Assistant** and its
Netatmo backend. Supports Python 3.11 and later. MiGO Link and myVAILLANT use other APIs.

## Installation

```sh
python -m pip install pymigo-netatmo
```

To work on the library itself, see [CONTRIBUTING.md](CONTRIBUTING.md).

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
`read_snapshot(consumption=False)` skips the consumption request made for each gateway.
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

## Command line

The `pymigo-netatmo` command reads a MiGO account and drives the heating from a shell, a
cron job or any tool that can run a process.

Give it the account through the environment:

```sh
export MIGO_USERNAME=user@example.com
export MIGO_PASSWORD='...'
```

Then read the account and drive it:

```sh
pymigo-netatmo status --token-file tokens.json    # homes, rooms, temperatures, gateways
pymigo-netatmo snapshot > snapshot.json           # raw account data, the default command
pymigo-netatmo set-temperature ROOM_ID 21.5 --duration 60 --yes
pymigo-netatmo set-mode away --until 2026-11-20T18:00 --yes   # schedule, away or hg
pymigo-netatmo set-heating-curve GATEWAY_ID 2.6 --yes
pymigo-netatmo set-dhw GATEWAY_ID off --yes
```

Every call of the library has a command: the writes above and more, the raw reads
(`homes-data`, `home-status`, `configs`, `measure`), `login` and `logout`. `--redact` hides personal data
in what they print.

`status` lists the ids that the other commands take. Commands that drive the heating ask for
confirmation and refuse to run without a terminal unless `--yes` is given. Values outside
the limits of the boiler are refused before anything is sent. The exit code tells a script
what happened. Code 3 means retry later, and code 4 means authenticate again.

```sh
pymigo-netatmo set-mode hg --yes || { [ $? -eq 4 ] && echo "check the credentials"; }
```

Every command, option, JSON shape and exit code:
[command line reference](https://github.com/tomahoax/pymigo-netatmo/blob/main/docs/cli.md).

## Models and tests

`Home`, `Room`, `Module` and `Consumption` are dataclasses implementing `Mapping`.
`from_json()` accepts missing fields and retains a deep copy in `.raw`. Frozen
containers prevent field reassignment; nested dictionaries remain mutable.
`AccountSnapshot.raw` returns a detached serializable account snapshot.
`pymigo_netatmo.testing.FakeMigo` supports offline consumer setup and writes.

Development setup and checks are described in [CONTRIBUTING.md](CONTRIBUTING.md).

See the [API reference](docs/api/reference.md), [OpenAPI](openapi.yaml) and
[architecture](docs/architecture.md). This is an unofficial, undocumented backend;
real error codes and refresh-token rotation need confirmation from captures.
