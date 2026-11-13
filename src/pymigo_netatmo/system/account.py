"""Read a coherent account snapshot using the MiGO API."""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any, cast

from ..client import MigoClient
from ..const import MEASURE_TYPES
from ..exceptions import MigoApiError, MigoAuthError
from ..models.snapshot import AccountSnapshot, Consumption, Home, Module, Room
from .home import MigoHome


def consumption_record(values: Sequence[Any], timestamp: int) -> dict[str, Any]:
    record: dict[str, Any] = {"timestamp": timestamp}
    for index in range(0, min(len(values), len(MEASURE_TYPES)) - 1, 2):
        record[MEASURE_TYPES[index]] = values[index]
        record[MEASURE_TYPES[index + 1]] = values[index + 1]
    return record


def parse_consumption(body: object) -> Consumption | None:
    """Extract the latest non-null daily reading from either getmeasure shape."""
    if isinstance(body, dict):
        timestamps = sorted((int(key), key) for key in body if isinstance(key, str) and key.isdigit())
        for timestamp, key in reversed(timestamps):
            values = body[key]
            if isinstance(values, list) and len(values) >= 2 and values[0] is not None:
                return Consumption.from_json(consumption_record(values, timestamp))
    elif isinstance(body, list) and body and isinstance(body[0], dict):
        entry = body[0]
        series = entry.get("value") or []
        begin = entry.get("beg_time")
        step = entry.get("step_time") or 86400
        if not isinstance(begin, (int, float)) or not isinstance(step, (int, float)) or not isinstance(series, list):
            return None
        for index in range(len(series) - 1, -1, -1):
            values = series[index]
            if isinstance(values, list) and len(values) >= 2 and values[0] is not None:
                return Consumption.from_json(consumption_record(values, int(begin + index * step)))
    return None


class MigoAccount:
    """The account-facing read API, independent of any host polling framework."""

    def __init__(self, client: MigoClient) -> None:
        self.client = client
        self._consumption: dict[str, Consumption] = {}

    def home(self, home_id: str) -> MigoHome:
        return MigoHome(self.client, home_id)

    async def read_snapshot(self, *, consumption: bool = True) -> AccountSnapshot:
        """Read homes, rooms and modules, and by default the latest daily consumption.

        With `consumption=False`, the one `getmeasure` request per gateway is skipped and the
        snapshot keeps whatever consumption this account object already holds, which is nothing
        on a first read. Use it when the readings are not needed.
        """
        response = await self.client.get_homes_data()
        body = response.get("body")
        if not isinstance(body, dict):
            raise MigoApiError("Invalid response from API: missing 'body'")
        homes: dict[str, Home] = {}
        rooms: dict[str, Room] = {}
        devices: dict[str, Module] = {}
        for home in body.get("homes") or []:
            home_id = home.get("id")
            if not home_id or not home.get("modules"):
                continue
            homes[home_id] = Home.from_json(home)
            status: dict[str, Any] = {}
            configs: dict[str, Any] = {}
            try:
                status_response = await self.client.get_home_status(home_id)
                status = cast(dict[str, Any], (status_response.get("body") or {}).get("home") or {})
            except MigoAuthError:
                raise
            except MigoApiError:
                pass
            try:
                config_response = await self.client.get_configs(home_id)
                configs = cast(dict[str, Any], (config_response.get("body") or {}).get("home") or {})
            except MigoAuthError:
                raise
            except MigoApiError:
                pass
            room_status = {entry["id"]: entry for entry in status.get("rooms") or [] if entry.get("id")}
            module_status = {entry["id"]: entry for entry in status.get("modules") or [] if entry.get("id")}
            module_configs = {entry["id"]: entry for entry in configs.get("modules") or [] if entry.get("id")}
            for room in home.get("rooms") or []:
                if room.get("id"):
                    room_id = room["id"]
                    rooms[room_id] = Room.from_json(
                        {
                            **room,
                            **room_status.get(room_id, {}),
                            "home_id": home_id,
                            "home_name": home.get("name", "Home"),
                        }
                    )
            for module in home.get("modules") or []:
                if module.get("id"):
                    module_id = module["id"]
                    devices[module_id] = Module.from_json(
                        {
                            **module,
                            **module_configs.get(module_id, {}),
                            **module_status.get(module_id, {}),
                            "home_id": home_id,
                        }
                    )
        if not consumption:
            return AccountSnapshot(homes, rooms, devices, dict(self._consumption))
        for device_id, device in devices.items():
            if device.get("type") != "NAVaillant":
                continue
            thermostat = next(
                (
                    key
                    for key, value in devices.items()
                    if value.get("type") == "NAThermVaillant"
                    and value.get("home_id") == device.get("home_id")
                    and value.get("bridge") == device_id
                ),
                None,
            )
            if thermostat is None:
                continue
            try:
                measures = await self.client.get_measure(
                    device_id=device_id,
                    module_id=thermostat,
                    scale="1day",
                    measure_types=list(MEASURE_TYPES),
                    date_begin=int(time.time()) - 604800,
                )
                reading = parse_consumption(measures.get("body"))
                if reading is not None:
                    self._consumption[device_id] = reading
            except MigoAuthError:
                raise
            except MigoApiError:
                pass
        return AccountSnapshot(homes, rooms, devices, dict(self._consumption))
