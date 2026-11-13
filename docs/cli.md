# Command line reference

The `pymigo-netatmo` command reads a MiGO account and drives its heating from a shell, a
cron job or any tool that can run a process (Node-RED, an MQTT bridge, a CI job). It is
installed with the library and needs no Python code. `python -m pymigo_netatmo.cli` runs
the same thing.

```sh
pymigo-netatmo [global options] [command] [command options]
```

Without a command, it runs `snapshot`.

## Credentials

| Variable | Meaning |
|---|---|
| `MIGO_USERNAME` | The account email. Used when `--username` is not given. |
| `MIGO_PASSWORD` | The account password. Optional, see below. |
| `MIGO_CLIENT_ID` | OAuth client id. Used when `--client-id` is not given. |
| `MIGO_CLIENT_SECRET` | OAuth client secret. It has no option, so it stays out of the process list. |
| `MIGO_USER_PREFIX` | OAuth user prefix. Used when `--user-prefix` is not given. |

The username is required. Without it, the command exits with code 2 and says so.

The password is resolved in this order:

1. `MIGO_PASSWORD`, when set and not empty.
2. No prompt, when `--token-file` points to a file that holds a refresh token for this
   account.
3. An interactive prompt, `MiGO password:`.

A password given in the environment is also the fallback when a stored refresh token is
rejected (HTTP 400 or 401). Network errors, rate limits and server outages never trigger
a password login.

The three OAuth values default to the ones built into the library. Set them only to
override those defaults.

With `--token-file`, the refresh token is stored in that file and reused by later runs.
The file is bound to the account, so a file written for another account is ignored. It is
created with mode `0600`. It is a credential, so keep it private.

## Global options

They go before or after the command: `pymigo-netatmo --json status` and
`pymigo-netatmo status --json` are the same.

| Option | Effect |
|---|---|
| `--username EMAIL` | Account email. Defaults to `MIGO_USERNAME`. |
| `--token-file FILE` | Store and reuse the refresh token in this file. |
| `--home-id ID` | Home to use. Defaults to the only home of the account. |
| `--client-id ID` | OAuth client id. Defaults to `MIGO_CLIENT_ID`, then to the library's value. |
| `--user-prefix PREFIX` | OAuth user prefix. Defaults to `MIGO_USER_PREFIX`, then to the library's value. |
| `--json` | Print JSON instead of text. Errors on stderr become JSON too. |
| `--redact` | Replace personal data in the printed backend data. |
| `--raw-log` | Log unredacted API payloads on stderr. |
| `-y`, `--yes` | Confirm a write without asking. |
| `-v`, `--verbose` | Debug logging on stderr. |

`--home-id` is needed when the account has several homes. Without it, the command exits
with code 2 and lists the ids. `status` shows them.

## Commands

| Command | What it does | Drives something |
|---|---|---|
| `snapshot` | Print the raw account snapshot as JSON. This is the default command. | |
| `status` | Homes, rooms with their temperatures, gateways, thermostats and schedules. | |
| `homes-data` | Print the raw homes, rooms and modules of the account as JSON. | |
| `home-status` | Print the raw live status of a home as JSON. | |
| `configs` | Print the raw configuration of a home as JSON. | |
| `measure GATEWAY_ID THERMOSTAT_ID [options]` | Print consumption measurements as JSON. | |
| `login` | Sign in with the password, and store the refresh token with `--token-file`. | |
| `logout` | Delete the token file. | |
| `set-temperature ROOM_ID TEMP [--duration MIN]` | Set a room temperature, in manual mode. | Yes |
| `set-room-state ROOM_ID [--mode MODE] [--temperature TEMP] [--until WHEN]` | Set a room mode, a setpoint, or both. | Yes |
| `set-temperature-offset ROOM_ID OFFSET` | Set a room temperature offset. | Yes |
| `set-mode MODE [--until WHEN]` | Set the home mode. | Yes |
| `set-control-mode heating\|dhw-only` | Heating, or hot water only. | Yes |
| `set-setpoint-duration MINUTES` | Default duration of a manual setpoint. | Yes |
| `set-anticipation on\|off` | Turn heating anticipation on or off. | Yes |
| `switch-schedule SCHEDULE_ID` | Activate another weekly schedule. | Yes |
| `set-heating-curve GATEWAY_ID SLOPE` | Set the heating curve slope. | Yes |
| `set-hysteresis GATEWAY_ID VALUE` | Set the hysteresis. | Yes |
| `set-heating-type GATEWAY_ID TYPE` | Set the heating system type. | Yes |
| `set-dhw GATEWAY_ID on\|off` | Turn domestic hot water on or off. | Yes |
| `set-dhw-temperature GATEWAY_ID TEMP` | Set the hot water temperature. | Yes |
| `set-dhw-always-on GATEWAY_ID on\|off` | Keep hot water production always on. | Yes |
| `set-dhw-storage GATEWAY_ID STORAGE` | Hot water from a tank or instantaneous. | Yes |

Room, gateway, thermostat and schedule ids come from `status`.

### Limits

The command refuses a value outside these limits with exit code 2, before it sends
anything.

| Value | Range | Step |
|---|---|---|
| Room temperature, `--temperature` | 7 to 30 C | 0.5 |
| Room temperature offset | -5 to 5 | 0.5 |
| `--duration`, `set-setpoint-duration` | 5 to 720 minutes | 5 |
| Heating curve slope | 0 to 5 | 0.1 |
| Hysteresis | 0.1 to 2 | 0.1 |
| Hot water temperature | 45 to 60 C | 1 |

### Room temperature

```sh
pymigo-netatmo status
pymigo-netatmo set-temperature room_456 21.5 --yes
pymigo-netatmo set-temperature room_456 19 --duration 120 --yes
```

The room goes to manual mode at the given temperature. Without `--duration`, the backend
applies its default setpoint duration.

`set-room-state` gives more control. `--mode` is `manual`, `home` or `hg` (frost guard).
It needs `--mode`, `--temperature` or both. `--until` sets when the setpoint expires.

```sh
pymigo-netatmo set-room-state room_456 --mode hg --yes
pymigo-netatmo set-room-state room_456 --mode manual --temperature 19 --until 2026-11-20T18:00 --yes
pymigo-netatmo set-temperature-offset room_456 -1.5 --yes
```

The offset is a room setting in degrees. It goes from -5 to 5 by steps of 0.5. The library
does not document what the backend does with it, so check the room with `status` afterwards.

### Home mode

```sh
pymigo-netatmo set-mode away --yes
pymigo-netatmo set-mode schedule --yes
```

`MODE` is `schedule`, `away` or `hg` (frost guard). The command always sends the heating
control mode `heating` with it.

`--until` sets when the mode ends, so the home goes back to its previous behaviour by
itself. It applies to `away` and `hg` only. Without `--until`, the command sends no end
time, which clears any end time set earlier.

```sh
pymigo-netatmo set-mode away --until 2026-11-20T18:00 --yes
```

### Dates and times

`--until` takes an ISO 8601 date and time, such as `2026-11-20T18:00` or
`2026-11-20T18:00:00+01:00`. A time without an offset is local time on the machine that
runs the command. The time must be in the future, and the command refuses anything else
with exit code 2.

### Home settings

```sh
pymigo-netatmo set-control-mode dhw-only --yes     # hot water only
pymigo-netatmo set-control-mode heating --yes      # back to heating
pymigo-netatmo set-setpoint-duration 90 --yes
pymigo-netatmo set-anticipation on --yes
pymigo-netatmo switch-schedule SCHEDULE_ID --yes
```

`dhw-only` is the "hot water only" quick action of the app. The backend knows it as the
control mode `cooling`, despite the name. `heating` leaves it without changing the home
mode. Use `set-mode` instead when the home mode should change too, as it also sets the
control mode back to `heating`.

`set-setpoint-duration` is the default duration of a manual setpoint, the one the backend
applies when a setpoint has no `--duration`.

`switch-schedule` takes a schedule id from `status`, where the active one is marked.

### Boiler settings

```sh
pymigo-netatmo set-heating-curve gateway_001 2.6 --yes
pymigo-netatmo set-hysteresis gateway_001 0.5 --yes
pymigo-netatmo set-dhw gateway_001 off --yes
pymigo-netatmo set-dhw-temperature gateway_001 50 --yes
pymigo-netatmo set-dhw-always-on gateway_001 on --yes
pymigo-netatmo set-dhw-storage gateway_001 water-tank --yes
pymigo-netatmo set-heating-type gateway_001 radiators --yes
```

These commands take the id of the gateway module (type `NAVaillant`), not a room id.

`set-dhw` turns hot water on or off. `set-dhw-always-on` keeps production on and overrides
the schedule. `set-dhw-storage` is `water-tank` or `instantaneous`. `set-heating-type` is
`radiators`, `convector` or `floor_heating`.

`set-dhw-always-on` relies on a field that Netatmo does not document. `set-dhw-storage` and
`set-heating-type` are wrappers over real endpoints that the library kept without any
consumer using them. Their effect is described in the code only and has not been
confirmed on an installation. Read `status` and `snapshot` after using them.

## Reading the backend

`snapshot` merges several reads. Four commands print the raw answers instead, as JSON.

```sh
pymigo-netatmo homes-data                   # homes, rooms and modules of the account
pymigo-netatmo home-status                  # live status of the only home
pymigo-netatmo configs --home-id home_123   # configuration of one home
pymigo-netatmo measure gateway_001 module_789 --scale 1week --from 2026-11-01 --to 2026-11-08
pymigo-netatmo measure gateway_001 module_789 --latest
```

`measure` takes the gateway id (type `NAVaillant`) and the id of its thermostat (type
`NAThermVaillant`). `status` lists both, and each thermostat shows its gateway.

| Option | Effect |
|---|---|
| `--scale` | `30min`, `1hour`, `3hours`, `1day` (default), `1week` or `1month`. |
| `--type` | One of the measures below. Repeat it to ask for several. Without it, the library asks for `sum_boiler_on` and `sum_boiler_off`. |
| `--from`, `--to` | Start and end of the period, as an ISO 8601 date and time. `--from` must be before `--to`. |
| `--latest` | Print only the latest valid daily reading, as `{"consumption": {...}}`. It is `null` when the answer holds none. It cannot be combined with `--type`. |

The measures are `sum_boiler_on`, `sum_boiler_off`, `sum_energy_gaz_heating`,
`sum_energy_gaz_hot_water`, `sum_energy_elec_heating` and `sum_energy_elec_hot_water`.

## Signing in and out

```sh
pymigo-netatmo login --username user@example.com --token-file ~/.migo-token
pymigo-netatmo logout --token-file ~/.migo-token
```

`login` checks the password. It always uses `MIGO_PASSWORD` or the prompt, even when the
token file already holds a refresh token. With `--token-file`, it stores the new refresh
token. Without it, it only validates the password.

`logout` deletes the token file. It needs no username, no password and no network. The library has no
call to revoke a token, so the token stays valid on the server until it expires.

## Redaction and logs

`--redact` replaces personal data in everything the commands print: the snapshot, the raw
reads and `status`. It uses the library's own list of sensitive keys, which includes names,
coordinates, the city, the invitation code and serial numbers. Ids are kept, so the output
stays usable in a bug report. Read it before sharing it all the same.

```sh
pymigo-netatmo snapshot --redact > snapshot.json
```

The normal logger redacts payloads, and `-v` turns it to debug level. `--raw-log` switches
on the library's `pymigo_netatmo.raw` logger, which prints the payloads unredacted on
stderr. Use it only for your own debugging. The command warns you when it is on.

## Confirmation

Every command marked "Drives something" asks `[y/N]` first. Without a terminal to ask on
and without `--yes`, it refuses with exit code 2 instead of proceeding. The question
comes before any password prompt and before anything is sent. A scheduled job therefore
states its intent explicitly.

A write is never replayed automatically. If a command fails after the backend may have
received it, read `status` before running it again.

## Exit codes

| Code | Meaning | What a script should do |
|---|---|---|
| 0 | Success | |
| 1 | Any other failure: network, backend error, refused request | Alert |
| 2 | Usage error (missing username, invalid value, ambiguous home) or confirmation refused | Fix the call |
| 3 | The library says to retry: network error, rate limit, server outage | Retry later |
| 4 | The library says to authenticate again | Check the credentials |
| 130 | Interrupted with Ctrl+C | |

The code follows the `remedy` of the `MigoError`: `retry` gives 3, `reauthenticate` gives 4,
anything else gives 1.

Error messages go to stderr, so stdout stays parseable. They carry the `code` of the error
when there is one, and its `remedy`:

```text
Error: Authentication failed: HTTP 401 [code=401, remedy=reauthenticate]
```

With `--json`, the error is one JSON object on stderr, and `placeholders` holds the values
the library attaches to the error:

```json
{"error": {"message": "...", "code": 503, "remedy": "retry", "placeholders": {}}}
```

A write is never replayed. If the backend answers a write with HTTP 401, the library renews
the credentials and the command fails with exit code 4. The credentials are fine at that
point, so run the command again.

## Output

`snapshot` always prints indented JSON. It has the same content as `AccountSnapshot.raw`
in the Python library. Its top-level keys are `homes`, `rooms`, `devices` and
`consumption`. Each one maps an identifier to the raw object returned by the backend.

`homes-data`, `home-status`, `configs` and `measure` always print the raw backend answer as indented JSON.
The other commands print text, or one JSON object with `--json`.

| Command | JSON shape |
|---|---|
| `status` | `{"homes": [{"id", "name", "mode", "rooms": [{"id", "name", "temperature", "setpoint", "setpoint_mode", "reachable"}], "gateways": [{"id", "type", "dhw_enabled", "dhw_setpoint_temperature"}], "thermostats": [{"id", "type", "room_id", "gateway_id", "reachable"}], "schedules": [{"id", "name", "selected"}]}]}` |
| `login` | `{"signed_in", "token_stored"}` |
| `logout` | `{"signed_out", "removed"}` |
| `set-temperature` | `{"command", "home_id", "room_id", "temperature", "duration", "status"}` |
| `set-room-state` | `{"command", "home_id", "room_id", "mode", "temperature", "until", "status"}` |
| `set-temperature-offset` | `{"command", "home_id", "room_id", "offset", "status"}` |
| `set-mode` | `{"command", "home_id", "mode", "until", "status"}` |
| `set-control-mode` | `{"command", "home_id", "mode", "temperature_control_mode", "status"}` |
| `set-setpoint-duration` | `{"command", "home_id", "minutes", "status"}` |
| `set-anticipation` | `{"command", "home_id", "enabled", "status"}` |
| `switch-schedule` | `{"command", "home_id", "schedule_id", "status"}` |
| `set-heating-curve` | `{"command", "gateway_id", "slope", "status"}` |
| `set-hysteresis` | `{"command", "gateway_id", "hysteresis", "status"}` |
| `set-heating-type` | `{"command", "gateway_id", "heating_type", "status"}` |
| `set-dhw` | `{"command", "home_id", "gateway_id", "enabled", "status"}` |
| `set-dhw-temperature` | `{"command", "home_id", "gateway_id", "temperature", "status"}` |
| `set-dhw-always-on` | `{"command", "home_id", "gateway_id", "enabled", "status"}` |
| `set-dhw-storage` | `{"command", "home_id", "gateway_id", "storage", "status"}` |

In a write result, `until` is a Unix timestamp, or `null` without `--until`. The `status`
field repeats the status of the backend answer, usually `ok`.

The raw outputs contain personal data. Use `--redact` before sharing them in an issue.

## Python only

Every command and every call of `MigoClient` and `MigoHome` has a counterpart on the
command line. What stays in Python is what a process cannot pass through arguments:
injecting your own `aiohttp` session or `TokenStore`, reading the models as objects, and the
`FakeMigo` test client.

## Recipes

Run from cron without any prompt, once the token file exists:

```sh
# First run, interactive: asks for the password and stores the refresh token
pymigo-netatmo login --username user@example.com --token-file ~/.migo-token

# Later runs, unattended
export MIGO_USERNAME=user@example.com
pymigo-netatmo set-mode schedule --token-file ~/.migo-token --yes
```

Lower a room for the night, then go back to the schedule in the morning:

```cron
0 22 * * * MIGO_USERNAME=user@example.com pymigo-netatmo set-temperature room_456 17 --token-file ~/.migo-token --yes
0 6 * * *  MIGO_USERNAME=user@example.com pymigo-netatmo set-mode schedule --token-file ~/.migo-token --yes
```

Read a value in a script:

```sh
pymigo-netatmo status --json --token-file ~/.migo-token \
  | jq '.homes[0].rooms[] | {name, temperature}'
```
