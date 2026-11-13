"""Reading a snapshot with and without the consumption request."""

from pymigo_netatmo import MigoAccount
from pymigo_netatmo.testing import FakeMigo

HOMES = {
    "body": {
        "homes": [
            {
                "id": "home_123",
                "modules": [
                    {"id": "gateway_001", "type": "NAVaillant"},
                    {"id": "module_789", "type": "NAThermVaillant", "bridge": "gateway_001"},
                ],
            }
        ]
    }
}
MEASURE = {"body": {"1704240000": [5400, 81000]}}


def recording_fake() -> tuple[FakeMigo, list[str]]:
    fake = FakeMigo(homes=HOMES)
    calls: list[str] = []

    async def get_measure(**kwargs):
        calls.append(kwargs["device_id"])
        return MEASURE

    fake.get_measure = get_measure
    return fake, calls


async def test_consumption_is_read_by_default():
    fake, calls = recording_fake()
    snapshot = await MigoAccount(fake).read_snapshot()
    assert calls == ["gateway_001"]
    assert snapshot.consumption["gateway_001"]["sum_boiler_on"] == 5400


async def test_consumption_can_be_skipped():
    fake, calls = recording_fake()
    snapshot = await MigoAccount(fake).read_snapshot(consumption=False)
    assert calls == []
    assert snapshot.consumption == {}
    assert set(snapshot.devices) == {"gateway_001", "module_789"}


async def test_skipping_keeps_the_readings_the_account_already_holds():
    fake, calls = recording_fake()
    account = MigoAccount(fake)
    await account.read_snapshot()
    snapshot = await account.read_snapshot(consumption=False)
    assert calls == ["gateway_001"]
    assert snapshot.consumption["gateway_001"]["sum_boiler_off"] == 81000
