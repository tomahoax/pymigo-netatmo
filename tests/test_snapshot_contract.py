"""Preserve the original integration's merged account contract."""

import json
from pathlib import Path

import pytest

from pymigo_netatmo import MigoAccount, MigoApiError, MigoAuthError
from pymigo_netatmo.models import AccountSnapshot, Home
from pymigo_netatmo.system.account import parse_consumption
from pymigo_netatmo.testing import FakeMigo


async def test_original_coordinator_golden(
    homes_data_response, home_status_response, configs_response, consumption_response
):
    fake = FakeMigo(
        homes=homes_data_response,
        statuses={"home_123": home_status_response},
        configs={"home_123": configs_response},
        measures={"gateway_001": consumption_response},
    )
    snapshot = await MigoAccount(fake).read_snapshot()
    assert snapshot.raw == json.loads((Path(__file__).parent / "fixtures/account_snapshot.json").read_text())


@pytest.mark.parametrize(
    "body,expected",
    [
        ({"9": [1, 2], "10": [3, 4], "latest": [5, 6]}, {"timestamp": 10, "sum_boiler_on": 3, "sum_boiler_off": 4}),
        (
            [{"beg_time": 100, "step_time": 10, "value": [[1, 2], [3, 4], None]}],
            {"timestamp": 110, "sum_boiler_on": 3, "sum_boiler_off": 4},
        ),
        ([{"value": [[1, 2]]}], None),
        (None, None),
        ({"100": [None, None]}, None),
    ],
)
def test_consumption_shapes_and_numeric_order(body, expected):
    reading = parse_consumption(body)
    assert (reading.raw if reading else None) == expected


async def test_missing_homes_body_rejected():
    with pytest.raises(MigoApiError):
        await MigoAccount(FakeMigo(homes={"invalid": True})).read_snapshot()


async def test_optional_reads_fail_without_losing_homes(homes_data_response):
    class Partial(FakeMigo):
        async def get_home_status(self, home_id):
            raise MigoApiError("offline")

        async def get_configs(self, home_id):
            raise MigoApiError("offline")

        async def get_measure(self, *args, **kwargs):
            raise MigoApiError("offline")

    snapshot = await MigoAccount(Partial(homes=homes_data_response)).read_snapshot()
    assert "home_123" in snapshot.homes
    assert snapshot.consumption == {}


async def test_optional_read_auth_failure_propagates(homes_data_response):
    class Reauth(FakeMigo):
        async def get_home_status(self, home_id):
            raise MigoAuthError("expired")

    with pytest.raises(MigoAuthError):
        await MigoAccount(Reauth(homes=homes_data_response)).read_snapshot()


def test_snapshot_mapping_and_copy():
    snapshot = AccountSnapshot(homes={"h": Home.from_json({"id": "h"})})
    assert len(snapshot) == 4
    assert list(snapshot) == ["homes", "rooms", "devices", "consumption"]
    with pytest.raises(KeyError):
        snapshot["unknown"]
    assert len(snapshot.homes["h"]) == 1
    assert list(snapshot.homes["h"]) == ["id"]
    snapshot.raw["homes"]["h"]["id"] = "changed"
    assert snapshot.homes["h"].id == "h"


async def test_all_home_commands_are_offline():
    fake = FakeMigo()
    home = MigoAccount(fake).home("h")
    await home.set_room_state("r", "manual", 22)
    await home.set_therm_mode("away")
    await home.set_temperature_control_mode("cooling")
    await home.set_dhw_enabled("m", True)
    await home.set_dhw_temperature("m", 55)
    await home.set_dhw_always_on("m", True)
    await home.set_temperature_offset("r", 0.5)
    await home.set_manual_setpoint_duration(60)
    await home.set_anticipation(True)
    await home.switch_schedule("s")
    assert len(fake.writes) == 10
    assert fake._session is None
