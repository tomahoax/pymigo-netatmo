"""Command line: reads, writes, confirmation, validation and exit codes."""

import argparse
import asyncio
import getpass
import json
import logging
import threading
from datetime import datetime

import pytest

from pymigo_netatmo import MigoApiError, MigoAuthError, MigoConnectionError
from pymigo_netatmo.cli import app, commands
from pymigo_netatmo.cli.parser import build_parser
from pymigo_netatmo.testing import FakeMigo

HOME = {
    "id": "home_123",
    "name": "My Home",
    "therm_mode": "schedule",
    "rooms": [{"id": "room_456", "name": "Living Room", "module_ids": ["module_789"]}],
    "modules": [
        {"id": "gateway_001", "type": "NAVaillant"},
        {"id": "module_789", "type": "NAThermVaillant", "room_id": "room_456", "bridge": "gateway_001"},
    ],
}
STATUS = {
    "body": {
        "home": {
            "rooms": [
                {
                    "id": "room_456",
                    "therm_measured_temperature": 21.5,
                    "therm_setpoint_temperature": 20.0,
                    "therm_setpoint_mode": "schedule",
                    "reachable": True,
                }
            ]
        }
    }
}
CONFIG = {"body": {"home": {"modules": [{"id": "gateway_001", "dhw_enabled": True, "dhw_setpoint_temperature": 55}]}}}


def make_fake(*homes: dict) -> FakeMigo:
    homes = homes or (HOME,)
    return FakeMigo(
        homes={"body": {"homes": list(homes)}},
        statuses={"home_123": STATUS},
        configs={"home_123": CONFIG},
    )


@pytest.fixture
def fake(monkeypatch):
    client = make_fake()
    monkeypatch.setenv("MIGO_USERNAME", "user@example.com")
    monkeypatch.setenv("MIGO_PASSWORD", "password")
    monkeypatch.setattr(app, "MigoClient", lambda *args, **kwargs: client)
    return client


def test_username_is_required(monkeypatch):
    monkeypatch.delenv("MIGO_USERNAME", raising=False)
    with pytest.raises(SystemExit) as error:
        app.main([])
    assert error.value.code == 2


def test_default_command_prints_the_snapshot(fake, capsys):
    assert app.main([]) == 0
    assert set(json.loads(capsys.readouterr().out)) == {"homes", "rooms", "devices", "consumption"}


def test_status_as_text_and_json(fake, capsys):
    assert app.main(["status"]) == 0
    text = capsys.readouterr().out
    assert "Home My Home (home_123), mode schedule" in text
    assert "Room Living Room (room_456): 21.5 C, setpoint 20.0 C (schedule)" in text
    assert "Gateway gateway_001: hot water on, 55 C" in text

    assert app.main(["status", "--json"]) == 0
    home = json.loads(capsys.readouterr().out)["homes"][0]
    assert home["rooms"][0] == {
        "id": "room_456",
        "name": "Living Room",
        "temperature": 21.5,
        "setpoint": 20.0,
        "setpoint_mode": "schedule",
        "reachable": True,
    }
    assert home["gateways"] == [
        {"id": "gateway_001", "type": "NAVaillant", "dhw_enabled": True, "dhw_setpoint_temperature": 55}
    ]


def test_global_options_work_after_the_command(fake, capsys):
    assert app.main(["status", "--json", "--home-id", "home_123"]) == 0
    assert json.loads(capsys.readouterr().out)["homes"][0]["id"] == "home_123"


def test_set_temperature_sends_the_write(fake, capsys):
    assert app.main(["set-temperature", "room_456", "21.5", "--duration", "60", "--yes", "--json"]) == 0
    assert fake.writes == [
        (
            "set_temperature",
            {"home_id": "home_123", "room_id": "room_456", "temperature": 21.5, "duration": 60},
        )
    ]
    assert json.loads(capsys.readouterr().out) == {
        "command": "set-temperature",
        "home_id": "home_123",
        "room_id": "room_456",
        "temperature": 21.5,
        "duration": 60,
        "status": "ok",
    }


def test_set_mode_sends_the_home_mode(fake):
    assert app.main(["set-mode", "away", "--yes"]) == 0
    ((endpoint, payload),) = fake.writes
    assert endpoint == "sethomedata"
    assert payload["home"]["id"] == "home_123"
    assert payload["home"]["therm_mode"] == "away"


def test_boiler_writes(fake, capsys):
    assert app.main(["set-heating-curve", "gateway_001", "2.6", "--yes"]) == 0
    assert app.main(["set-hysteresis", "gateway_001", "0.5", "--yes"]) == 0
    assert app.main(["set-dhw", "gateway_001", "off", "--yes"]) == 0
    assert app.main(["set-dhw-temperature", "gateway_001", "50", "--yes"]) == 0
    assert fake.writes[0] == ("set_heating_curve", {"device_id": "gateway_001", "slope": 2.6})
    assert fake.writes[1] == ("set_hysteresis", {"device_id": "gateway_001", "hysteresis": 0.5})
    assert len(fake.writes) == 4
    assert "hot water turned off" in capsys.readouterr().out


def test_write_refused_without_a_terminal_and_without_yes(fake, capsys):
    assert app.main(["set-temperature", "room_456", "21"]) == 2
    assert fake.writes == []
    assert "pass --yes" in capsys.readouterr().err


@pytest.mark.parametrize(("answer", "expected", "writes"), [("y", 0, 1), ("n", 2, 0), ("", 2, 0)])
def test_interactive_confirmation(fake, monkeypatch, answer, expected, writes):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    assert app.main(["set-temperature", "room_456", "21"]) == expected
    assert len(fake.writes) == writes


def test_reads_never_ask_for_confirmation(fake):
    assert app.main(["status"]) == 0


@pytest.mark.parametrize(
    "argv",
    [
        ["set-temperature", "room_456", "31"],
        ["set-temperature", "room_456", "6.5"],
        ["set-temperature", "room_456", "21.3"],
        ["set-temperature", "room_456", "warm"],
        ["set-temperature", "room_456", "21", "--duration", "7"],
        ["set-temperature", "room_456", "21", "--duration", "725"],
        ["set-mode", "manual"],
        ["set-heating-curve", "gateway_001", "5.1"],
        ["set-hysteresis", "gateway_001", "0.05"],
        ["set-dhw", "gateway_001", "maybe"],
        ["set-dhw-temperature", "gateway_001", "44"],
        ["set-dhw-temperature", "gateway_001", "50.5"],
    ],
)
def test_out_of_range_values_are_refused_before_anything_is_sent(fake, argv):
    with pytest.raises(SystemExit) as error:
        app.main([*argv, "--yes"])
    assert error.value.code == 2
    assert fake.writes == []


def test_limits_are_inclusive(fake):
    assert app.main(["set-temperature", "room_456", "7", "--yes"]) == 0
    assert app.main(["set-temperature", "room_456", "30", "--duration", "720", "--yes"]) == 0
    assert app.main(["set-dhw-temperature", "gateway_001", "60", "--yes"]) == 0


def test_several_homes_need_a_home_id(monkeypatch, capsys):
    other = {**HOME, "id": "home_999", "name": "Other"}
    client = make_fake(HOME, other)
    monkeypatch.setenv("MIGO_USERNAME", "u")
    monkeypatch.setenv("MIGO_PASSWORD", "p")
    monkeypatch.setattr(app, "MigoClient", lambda *args, **kwargs: client)
    assert app.main(["set-mode", "away", "--yes"]) == 2
    err = capsys.readouterr().err
    assert "home_123" in err
    assert "home_999" in err
    assert client.writes == []
    assert app.main(["set-mode", "away", "--home-id", "home_999", "--yes"]) == 0
    assert client.writes[0][1]["home"]["id"] == "home_999"


def test_account_without_a_heating_home(monkeypatch, capsys):
    client = FakeMigo()
    monkeypatch.setenv("MIGO_USERNAME", "u")
    monkeypatch.setenv("MIGO_PASSWORD", "p")
    monkeypatch.setattr(app, "MigoClient", lambda *args, **kwargs: client)
    assert app.main(["set-mode", "away", "--yes"]) == 2
    assert "no home" in capsys.readouterr().err
    assert app.main(["status"]) == 0
    assert "No home." in capsys.readouterr().out


@pytest.mark.parametrize(
    ("error", "code"),
    [(MigoAuthError("expired"), 4), (MigoApiError("rejected"), 1), (KeyboardInterrupt(), 130)],
)
def test_errors_map_to_exit_codes_without_a_traceback(fake, monkeypatch, capsys, error, code):
    async def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(fake, "get_homes_data", fail)
    assert app.main(["status"]) == code
    assert "Traceback" not in capsys.readouterr().err


FUTURE = "2099-01-01T12:00"
FUTURE_TIMESTAMP = int(datetime.fromisoformat(FUTURE).astimezone().timestamp())


def payloads(client: FakeMigo) -> list[dict]:
    return [payload for _, payload in client.writes]


def test_set_mode_until(fake, capsys):
    assert app.main(["set-mode", "away", "--until", FUTURE, "--yes", "--json"]) == 0
    assert payloads(fake)[0]["home"]["therm_mode_endtime"] == FUTURE_TIMESTAMP
    assert json.loads(capsys.readouterr().out)["until"] == FUTURE_TIMESTAMP


def test_set_mode_without_until_clears_the_end_time(fake):
    assert app.main(["set-mode", "away", "--yes"]) == 0
    assert payloads(fake)[0]["home"]["therm_mode_endtime"] is None


def test_until_accepts_an_offset_and_refuses_the_past_and_garbage(fake):
    assert app.main(["set-mode", "hg", "--until", "2099-01-01T12:00:00+00:00", "--yes"]) == 0
    assert payloads(fake)[0]["home"]["therm_mode_endtime"] == 4070952000
    for value in ("2000-01-01T00:00", "tomorrow", "2099-13-01"):
        with pytest.raises(SystemExit) as error:
            app.main(["set-mode", "away", "--until", value, "--yes"])
        assert error.value.code == 2


def test_until_makes_no_sense_with_the_schedule_mode(fake, capsys):
    with pytest.raises(SystemExit) as error:
        app.main(["set-mode", "schedule", "--until", FUTURE, "--yes"])
    assert error.value.code == 2
    assert "away and hg" in capsys.readouterr().err
    assert fake.writes == []


def test_set_room_state(fake, capsys):
    argv = ["set-room-state", "room_456", "--mode", "manual", "--temperature", "19.5", "--until", FUTURE, "--yes"]
    assert app.main([*argv, "--json"]) == 0
    room = payloads(fake)[0]["home"]["rooms"][0]
    assert room == {
        "id": "room_456",
        "therm_setpoint_mode": "manual",
        "therm_setpoint_temperature": 19.5,
        "therm_setpoint_end_time": FUTURE_TIMESTAMP,
    }
    assert json.loads(capsys.readouterr().out)["mode"] == "manual"


def test_set_room_state_with_only_a_mode(fake):
    assert app.main(["set-room-state", "room_456", "--mode", "hg", "--yes"]) == 0
    assert payloads(fake)[0]["home"]["rooms"][0] == {"id": "room_456", "therm_setpoint_mode": "hg"}


def test_set_room_state_needs_a_mode_or_a_temperature(fake, capsys):
    with pytest.raises(SystemExit) as error:
        app.main(["set-room-state", "room_456", "--yes"])
    assert error.value.code == 2
    assert "needs --mode, --temperature or both" in capsys.readouterr().err
    assert fake.writes == []


def test_set_temperature_offset_accepts_negative_values(fake):
    assert app.main(["set-temperature-offset", "room_456", "-1.5", "--yes"]) == 0
    assert payloads(fake)[0]["home"]["rooms"] == [{"id": "room_456", "therm_setpoint_offset": -1.5}]


@pytest.mark.parametrize(("mode", "wire"), [("dhw-only", "cooling"), ("heating", "heating")])
def test_set_control_mode(fake, mode, wire):
    assert app.main(["set-control-mode", mode, "--yes"]) == 0
    assert payloads(fake)[0]["home"] == {"id": "home_123", "temperature_control_mode": wire}


def test_set_setpoint_duration(fake):
    assert app.main(["set-setpoint-duration", "90", "--yes"]) == 0
    assert payloads(fake)[0]["home"]["therm_setpoint_default_duration"] == 90


@pytest.mark.parametrize(("state", "enabled"), [("on", True), ("off", False)])
def test_set_anticipation(fake, state, enabled):
    assert app.main(["set-anticipation", state, "--yes"]) == 0
    assert payloads(fake)[0]["home"]["anticipation"] is enabled


def test_switch_schedule(fake):
    assert app.main(["switch-schedule", "schedule_001", "--yes"]) == 0
    assert payloads(fake)[0] == {"home_id": "home_123", "schedule_id": "schedule_001"}


def test_set_heating_type(fake):
    assert app.main(["set-heating-type", "gateway_001", "floor_heating", "--yes"]) == 0
    assert payloads(fake)[0] == {"device_id": "gateway_001", "heating_type": "floor_heating"}


@pytest.mark.parametrize(("state", "enabled"), [("on", True), ("off", False)])
def test_set_dhw_always_on(fake, state, enabled):
    assert app.main(["set-dhw-always-on", "gateway_001", state, "--yes"]) == 0
    assert payloads(fake)[0]["home"]["modules"] == [{"id": "gateway_001", "dhw_always_on": enabled}]


@pytest.mark.parametrize(("storage", "wire"), [("water-tank", "water_tank"), ("instantaneous", "instantaneous")])
def test_set_dhw_storage(fake, storage, wire):
    assert app.main(["set-dhw-storage", "gateway_001", storage, "--yes"]) == 0
    assert payloads(fake)[0]["home"]["modules"] == [{"id": "gateway_001", "dhw_control": wire}]


@pytest.mark.parametrize(
    "argv",
    [
        ["set-room-state", "room_456", "--mode", "off"],
        ["set-room-state", "room_456", "--temperature", "31"],
        ["set-temperature-offset", "room_456", "5.5"],
        ["set-temperature-offset", "room_456", "0.3"],
        ["set-control-mode", "cooling"],
        ["set-setpoint-duration", "4"],
        ["set-setpoint-duration", "722"],
        ["set-anticipation", "maybe"],
        ["set-heating-type", "gateway_001", "unknown"],
        ["set-dhw-always-on", "gateway_001", "maybe"],
        ["set-dhw-storage", "gateway_001", "tank"],
    ],
)
def test_new_commands_refuse_invalid_values(fake, argv):
    with pytest.raises(SystemExit) as error:
        app.main([*argv, "--yes"])
    assert error.value.code == 2
    assert fake.writes == []


NEW_WRITES = [
    ["set-room-state", "room_456", "--mode", "hg"],
    ["set-temperature-offset", "room_456", "1"],
    ["set-control-mode", "dhw-only"],
    ["set-setpoint-duration", "30"],
    ["set-anticipation", "on"],
    ["switch-schedule", "schedule_001"],
    ["set-heating-type", "gateway_001", "radiators"],
    ["set-dhw-always-on", "gateway_001", "on"],
    ["set-dhw-storage", "gateway_001", "water-tank"],
]


@pytest.mark.parametrize("argv", NEW_WRITES)
def test_every_new_write_asks_first(fake, argv, capsys):
    assert app.main(argv) == 2
    assert fake.writes == []
    assert "pass --yes" in capsys.readouterr().err


@pytest.mark.parametrize("argv", NEW_WRITES)
def test_every_new_write_reports_in_text_and_json(fake, argv, capsys):
    assert app.main([*argv, "--yes"]) == 0
    assert "(status: ok)" in capsys.readouterr().out
    assert app.main([*argv, "--yes", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["command"] == argv[0]
    assert result["status"] == "ok"


def test_status_lists_the_schedules(monkeypatch, capsys):
    home = {**HOME, "schedules": [{"id": "schedule_001", "name": "Default", "type": "therm", "selected": True}]}
    client = make_fake(home)
    monkeypatch.setenv("MIGO_USERNAME", "u")
    monkeypatch.setenv("MIGO_PASSWORD", "p")
    monkeypatch.setattr(app, "MigoClient", lambda *args, **kwargs: client)
    assert app.main(["status"]) == 0
    assert "Schedule Default (schedule_001) (active)" in capsys.readouterr().out
    assert app.main(["status", "--json"]) == 0
    schedules = json.loads(capsys.readouterr().out)["homes"][0]["schedules"]
    assert schedules == [{"id": "schedule_001", "name": "Default", "selected": True}]


def test_status_lists_thermostats_with_their_gateway(fake, capsys):
    assert app.main(["status"]) == 0
    assert "Thermostat module_789: room room_456, gateway gateway_001" in capsys.readouterr().out
    assert app.main(["status", "--json"]) == 0
    thermostats = json.loads(capsys.readouterr().out)["homes"][0]["thermostats"]
    assert thermostats == [
        {
            "id": "module_789",
            "type": "NAThermVaillant",
            "room_id": "room_456",
            "gateway_id": "gateway_001",
            "reachable": None,
        }
    ]


def test_home_status_and_configs_print_the_raw_answers(fake, capsys):
    assert app.main(["home-status"]) == 0
    assert json.loads(capsys.readouterr().out) == STATUS
    assert app.main(["configs", "--home-id", "home_123"]) == 0
    assert json.loads(capsys.readouterr().out) == CONFIG


MEASURES = {"gateway_001": {"body": {"1704153600": [100, 200], "1704240000": [5400, 81000]}}}


@pytest.fixture
def measuring(fake):
    calls = []

    async def get_measure(**kwargs):
        calls.append(kwargs)
        return MEASURES["gateway_001"]

    fake.get_measure = get_measure
    return calls


def test_measure_prints_the_raw_answer_with_the_library_defaults(measuring, capsys):
    assert app.main(["measure", "gateway_001", "module_789"]) == 0
    assert json.loads(capsys.readouterr().out) == MEASURES["gateway_001"]
    assert measuring == [
        {
            "device_id": "gateway_001",
            "module_id": "module_789",
            "scale": "1day",
            "measure_types": None,
            "date_begin": None,
            "date_end": None,
        }
    ]


def test_measure_options(measuring):
    argv = [
        "measure",
        "gateway_001",
        "module_789",
        "--scale",
        "1week",
        "--type",
        "sum_boiler_on",
        "--type",
        "sum_energy_gaz_heating",
        "--from",
        "2024-01-01T00:00:00+00:00",
        "--to",
        "2024-01-08T00:00:00+00:00",
    ]
    assert app.main(argv) == 0
    assert measuring[0]["scale"] == "1week"
    assert measuring[0]["measure_types"] == ["sum_boiler_on", "sum_energy_gaz_heating"]
    assert measuring[0]["date_begin"] == 1704067200
    assert measuring[0]["date_end"] == 1704672000


def test_measure_latest_prints_the_last_valid_daily_reading(measuring, capsys):
    assert app.main(["measure", "gateway_001", "module_789", "--latest"]) == 0
    reading = json.loads(capsys.readouterr().out)["consumption"]
    assert reading == {"timestamp": 1704240000, "sum_boiler_on": 5400, "sum_boiler_off": 81000}


def test_measure_latest_without_data_prints_null(fake, capsys):
    assert app.main(["measure", "gateway_001", "module_789", "--latest"]) == 0
    assert json.loads(capsys.readouterr().out) == {"consumption": None}


@pytest.mark.parametrize(
    "argv",
    [
        ["--scale", "1year"],
        ["--type", "sum_gas"],
        ["--from", "yesterday"],
        ["--from", "2024-02-01", "--to", "2024-01-01"],
        ["--from", "2024-01-01", "--to", "2024-01-01"],
    ],
)
def test_measure_refuses_invalid_options(measuring, argv):
    with pytest.raises(SystemExit) as error:
        app.main(["measure", "gateway_001", "module_789", *argv])
    assert error.value.code == 2
    assert measuring == []


def test_redact_hides_personal_data_in_every_raw_output(fake, capsys):
    assert app.main(["snapshot"]) == 0
    assert "My Home" in capsys.readouterr().out
    assert app.main(["snapshot", "--redact"]) == 0
    out = capsys.readouterr().out
    assert "My Home" not in out
    assert "**REDACTED**" in out
    assert "home_123" in out


def test_redact_status_keeps_the_ids_and_hides_the_names(fake, capsys):
    assert app.main(["status", "--redact"]) == 0
    text = capsys.readouterr().out
    assert "My Home" not in text
    assert "Living Room" not in text
    assert "(home_123)" in text
    assert "(room_456)" in text
    assert app.main(["status", "--redact", "--json"]) == 0
    home = json.loads(capsys.readouterr().out)["homes"][0]
    assert home["name"] == "**REDACTED**"
    assert home["rooms"][0]["name"] == "**REDACTED**"
    assert home["id"] == "home_123"


def test_redact_applies_to_the_other_raw_reads(fake, capsys, monkeypatch):
    async def configs(home_id):
        return {"body": {"home": {"city": "Somewhere", "id": home_id}}}

    monkeypatch.setattr(fake, "get_configs", configs)
    assert app.main(["configs", "--redact"]) == 0
    assert json.loads(capsys.readouterr().out) == {"body": {"home": {"city": "**REDACTED**", "id": "home_123"}}}


@pytest.fixture
def raw_logger():
    logger = logging.getLogger("pymigo_netatmo.raw")
    yield logger
    logger.setLevel(logging.NOTSET)


def test_raw_log_sets_the_level_of_the_raw_logger_itself(fake, capsys, raw_logger):
    assert raw_logger.level == logging.NOTSET
    assert app.main(["status", "--raw-log"]) == 0
    assert raw_logger.level == logging.DEBUG
    assert "personal data" in capsys.readouterr().err


def test_raw_log_is_off_by_default(fake, raw_logger):
    assert app.main(["status", "-v"]) == 0
    assert raw_logger.level == logging.NOTSET


def test_oauth_overrides_reach_the_client(monkeypatch):
    seen = {}

    def factory(*args, **kwargs):
        seen.update(kwargs)
        return make_fake()

    monkeypatch.setenv("MIGO_USERNAME", "u")
    monkeypatch.setenv("MIGO_PASSWORD", "p")
    monkeypatch.setenv("MIGO_CLIENT_SECRET", "secret")
    monkeypatch.setattr(app, "MigoClient", factory)
    assert app.main(["status", "--client-id", "my-id", "--user-prefix", "pre"]) == 0
    assert (seen["client_id"], seen["client_secret"], seen["user_prefix"]) == ("my-id", "secret", "pre")


def test_oauth_overrides_default_to_the_library_values(fake, monkeypatch):
    seen = {}

    def factory(*args, **kwargs):
        seen.update(kwargs)
        return fake

    for name in ("MIGO_CLIENT_ID", "MIGO_CLIENT_SECRET", "MIGO_USER_PREFIX"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(app, "MigoClient", factory)
    assert app.main(["status"]) == 0
    assert (seen["client_id"], seen["client_secret"], seen["user_prefix"]) == (None, None, None)


def write_token(path, account="user@example.com"):
    path.write_text(json.dumps({"account": account, "refresh_token": "stored"}))


def test_login_validates_the_password_and_never_settles_for_a_stored_token(fake, monkeypatch, tmp_path, capsys):
    token = tmp_path / "token.json"
    write_token(token)
    monkeypatch.delenv("MIGO_PASSWORD")
    asked = []
    monkeypatch.setattr(getpass, "getpass", lambda prompt: asked.append(prompt) or "typed")
    authenticated = []

    async def authenticate():
        authenticated.append(True)
        return True

    monkeypatch.setattr(fake, "authenticate", authenticate)
    assert app.main(["login", "--token-file", str(token), "--json"]) == 0
    assert asked == ["MiGO password: "]
    assert authenticated == [True]
    assert json.loads(capsys.readouterr().out) == {"signed_in": True, "token_stored": True}


def test_login_without_a_token_file_says_nothing_is_stored(fake, capsys):
    assert app.main(["login"]) == 0
    assert "nothing stored" in capsys.readouterr().out


def test_other_commands_do_not_ask_for_a_password_when_a_token_is_stored(fake, monkeypatch, tmp_path):
    token = tmp_path / "token.json"
    write_token(token)
    monkeypatch.delenv("MIGO_PASSWORD")

    def refuse(prompt):
        raise AssertionError("no password prompt expected")

    monkeypatch.setattr(getpass, "getpass", refuse)
    assert app.main(["status", "--token-file", str(token)]) == 0


def test_logout_deletes_the_token_file_without_any_prompt_or_network(monkeypatch, tmp_path, capsys):
    token = tmp_path / "token.json"
    write_token(token)
    monkeypatch.setenv("MIGO_USERNAME", "user@example.com")
    monkeypatch.delenv("MIGO_PASSWORD", raising=False)
    monkeypatch.setattr(getpass, "getpass", lambda prompt: pytest.fail("no prompt expected"))
    monkeypatch.setattr(app, "MigoClient", lambda *a, **k: pytest.fail("no client expected"))
    assert app.main(["logout", "--token-file", str(token), "--json"]) == 0
    assert not token.exists()
    assert json.loads(capsys.readouterr().out) == {"signed_out": True, "removed": True}
    assert app.main(["logout", "--token-file", str(token), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"signed_out": True, "removed": False}


def test_logout_needs_a_token_file(fake, capsys):
    with pytest.raises(SystemExit) as error:
        app.main(["logout"])
    assert error.value.code == 2
    assert "logout needs --token-file" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("error", "code", "details"),
    [
        (MigoConnectionError("service down"), 3, "remedy=retry"),
        (MigoAuthError("expired", code=401), 4, "code=401, remedy=reauthenticate"),
        (MigoApiError("rejected", code=403), 1, "code=403, remedy=unknown"),
        (MigoApiError("odd"), 1, "[remedy=unknown]"),
    ],
)
def test_errors_show_their_code_and_remedy_and_map_the_remedy_to_the_exit_code(
    fake, monkeypatch, capsys, error, code, details
):
    async def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(fake, "get_homes_data", fail)
    assert app.main(["status"]) == code
    err = capsys.readouterr().err
    assert f"Error: {error} [" in err
    assert details in err


def test_errors_as_json_on_stderr(fake, monkeypatch, capsys):
    async def fail(*args, **kwargs):
        raise MigoConnectionError("service down", code=503, placeholders={"host": "app"})

    monkeypatch.setattr(fake, "get_homes_data", fail)
    assert app.main(["status", "--json"]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {"message": "service down", "code": 503, "remedy": "retry", "placeholders": {"host": "app"}}
    }


def test_homes_data_prints_the_raw_answer_and_can_redact_it(fake, capsys):
    assert app.main(["homes-data"]) == 0
    assert json.loads(capsys.readouterr().out)["body"]["homes"][0]["name"] == "My Home"
    assert app.main(["homes-data", "--redact"]) == 0
    assert json.loads(capsys.readouterr().out)["body"]["homes"][0]["name"] == "**REDACTED**"


def test_logout_needs_no_username(monkeypatch, tmp_path):
    token = tmp_path / "token.json"
    write_token(token)
    monkeypatch.delenv("MIGO_USERNAME", raising=False)
    assert app.main(["logout", "--token-file", str(token)]) == 0
    assert not token.exists()


def test_measure_latest_refuses_a_custom_type(fake, capsys):
    with pytest.raises(SystemExit) as error:
        app.main(["measure", "gateway_001", "module_789", "--latest", "--type", "sum_energy_gaz_heating"])
    assert error.value.code == 2
    assert "--latest cannot be combined with --type" in capsys.readouterr().err


def test_values_snap_to_the_grid_of_their_step(fake):
    assert app.main(["set-hysteresis", "gateway_001", "0.2999999999999", "--yes"]) == 0
    assert app.main(["set-temperature", "room_456", "21.4999999999", "--yes"]) == 0
    writes = repr(fake.writes)
    assert "0.3" in writes
    assert "21.5" in writes


def test_confirmation_prompt_stays_off_stdout(fake, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda *prompt: "y")
    assert app.main(["set-temperature", "room_456", "21", "--json"]) == 0
    captured = capsys.readouterr()
    json.loads(captured.out)
    assert "[y/N]" in captured.err


def test_status_shows_unknown_when_the_configuration_is_missing(monkeypatch, capsys):
    client = FakeMigo(homes={"body": {"homes": [HOME]}}, statuses={"home_123": STATUS})
    monkeypatch.setenv("MIGO_USERNAME", "u")
    monkeypatch.setenv("MIGO_PASSWORD", "p")
    monkeypatch.setattr(app, "MigoClient", lambda *args, **kwargs: client)
    assert app.main(["status"]) == 0
    assert "Gateway gateway_001: hot water unknown" in capsys.readouterr().out


READS = [
    ["snapshot"],
    ["status"],
    ["homes-data"],
    ["home-status"],
    ["configs"],
    ["measure", "gateway_001", "module_789"],
]
WRITES = [
    ["set-temperature", "room_456", "21"],
    ["set-mode", "away"],
    ["set-heating-curve", "gateway_001", "2.6"],
    ["set-hysteresis", "gateway_001", "0.5"],
    ["set-dhw", "gateway_001", "off"],
    ["set-dhw-temperature", "gateway_001", "50"],
    *NEW_WRITES,
]


def test_every_command_is_either_a_read_or_a_confirmed_write():
    sample = {argv[0] for argv in WRITES} | {argv[0] for argv in READS} | {"login", "logout"}
    assert sample == set(commands.COMMANDS) | {"logout"}
    assert {argv[0] for argv in READS} | {"login"} == commands.READ_COMMANDS
    assert {argv[0] for argv in WRITES} == set(commands.COMMANDS) - commands.READ_COMMANDS


def test_the_parser_knows_exactly_the_commands_that_run():
    parser = build_parser()
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    assert set(subparsers.choices) == set(commands.COMMANDS) | {"logout"}


@pytest.mark.parametrize("argv", WRITES)
def test_every_write_is_refused_without_confirmation(fake, argv, capsys):
    assert commands.needs_confirmation(argv[0])
    assert app.main(argv) == 2
    assert fake.writes == []
    assert "pass --yes" in capsys.readouterr().err


@pytest.mark.parametrize("argv", READS)
def test_no_read_asks_for_confirmation(fake, argv):
    assert not commands.needs_confirmation(argv[0])
    assert app.main(argv) == 0


def test_a_command_missing_from_the_read_list_fails_closed(fake, monkeypatch, capsys):
    async def new_command(args, client):
        raise AssertionError("must not run without confirmation")

    monkeypatch.setitem(commands.COMMANDS, "set-new", new_command)
    assert commands.needs_confirmation("set-new")
    assert not commands.needs_confirmation("logout")
    assert not commands.needs_confirmation("not-a-command")


def test_status_does_not_request_consumption_but_snapshot_does(fake):
    calls = []

    async def get_measure(**kwargs):
        calls.append(kwargs["device_id"])
        return {"body": {}}

    fake.get_measure = get_measure
    assert app.main(["status"]) == 0
    assert calls == []
    assert app.main(["snapshot"]) == 0
    assert calls == ["gateway_001"]


def test_ctrl_c_at_the_password_prompt_exits_with_130(fake, monkeypatch, capsys):
    monkeypatch.delenv("MIGO_PASSWORD")

    def interrupted(prompt):
        raise KeyboardInterrupt

    monkeypatch.setattr(getpass, "getpass", interrupted)
    assert app.main(["status"]) == 130
    assert "Interrupted." in capsys.readouterr().err


def test_the_password_prompt_runs_on_the_main_thread_outside_an_event_loop(fake, monkeypatch):
    monkeypatch.delenv("MIGO_PASSWORD")
    seen = {}

    def prompt(text):
        seen["thread"] = threading.current_thread()
        try:
            asyncio.get_running_loop()
            seen["loop"] = True
        except RuntimeError:
            seen["loop"] = False
        return "typed"

    monkeypatch.setattr(getpass, "getpass", prompt)
    assert app.main(["status"]) == 0
    assert seen == {"thread": threading.main_thread(), "loop": False}


def test_the_password_typed_at_the_prompt_reaches_the_client(monkeypatch):
    seen = {}

    def factory(username, password, **kwargs):
        seen["password"] = password
        return make_fake()

    monkeypatch.setenv("MIGO_USERNAME", "u")
    monkeypatch.delenv("MIGO_PASSWORD", raising=False)
    monkeypatch.setattr(getpass, "getpass", lambda prompt: "typed")
    monkeypatch.setattr(app, "MigoClient", factory)
    assert app.main(["status"]) == 0
    assert seen["password"] == "typed"
