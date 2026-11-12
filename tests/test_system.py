from pymigo_netatmo import MigoAccount
from pymigo_netatmo.models import Home, Room
from pymigo_netatmo.testing import FakeMigo


async def test_snapshot_merges_status_over_configs_and_preserves_unknown_fields():
    fake = FakeMigo(
        homes={
            "body": {
                "homes": [
                    {
                        "id": "home",
                        "name": "House",
                        "extra": 42,
                        "rooms": [{"id": "room", "name": "Living room"}],
                        "modules": [
                            {"id": "gateway", "type": "NAVaillant"},
                            {"id": "therm", "type": "NAThermVaillant", "bridge": "gateway"},
                        ],
                    }
                ]
            }
        },
        statuses={
            "home": {
                "body": {
                    "home": {
                        "rooms": [{"id": "room", "therm_measured_temperature": 21}],
                        "modules": [{"id": "gateway", "reachable": True}],
                    }
                }
            }
        },
        configs={
            "home": {"body": {"home": {"modules": [{"id": "gateway", "reachable": False, "dhw_always_on": True}]}}}
        },
        measures={"gateway": {"body": {"100": [1, 2, 3000, 4000, 5000, 6000]}}},
    )
    snapshot = await MigoAccount(fake).read_snapshot()
    assert snapshot.homes["home"].raw["extra"] == 42
    assert snapshot.rooms["room"]["therm_measured_temperature"] == 21
    assert snapshot.rooms["room"]["home_name"] == "House"
    assert snapshot.devices["gateway"]["reachable"] is True
    assert snapshot.consumption["gateway"]["sum_energy_gaz_heating"] == 3000
    assert dict(snapshot)["rooms"] == snapshot.rooms


def test_models_tolerate_missing_fields_and_own_raw_copy():
    data = {"id": "home", "future": {"x": 1}}
    home = Home.from_json(data)
    data["future"]["x"] = 2
    assert home.raw["future"] == {"x": 1}
    assert Room.from_json(None).id is None


async def test_home_write_converts_curve_hysteresis_and_duration():
    fake = FakeMigo()
    home = MigoAccount(fake).home("home")
    await home.set_heating_curve("gateway", 2.6)
    await home.set_hysteresis("gateway", 0.4)
    await home.set_temperature("room", 22, duration=60)
    assert fake.writes[0] == ("set_heating_curve", {"device_id": "gateway", "slope": 2.6})
    assert fake.writes[1] == ("set_hysteresis", {"device_id": "gateway", "hysteresis": 0.4})
    assert fake.writes[2][1]["home_id"] == "home"


async def test_fake_applies_room_and_hot_water_writes_without_network():
    fake = FakeMigo(
        homes={
            "body": {
                "homes": [
                    {"id": "home", "modules": [{"id": "gateway", "type": "NAVaillant"}], "rooms": [{"id": "room"}]}
                ]
            }
        }
    )
    await fake.set_room_state("home", "room", "manual", 23)
    await fake.set_dhw_enabled("home", "gateway", True)
    snapshot = await MigoAccount(fake).read_snapshot()
    assert snapshot.rooms["room"]["therm_setpoint_temperature"] == 23
    assert snapshot.devices["gateway"]["dhw_enabled"] is True
