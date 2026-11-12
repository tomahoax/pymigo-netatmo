"""In-memory API fake for consumers, without a Home Assistant dependency."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from .client import MigoClient
from .models import GetConfigsResponse, GetMeasureResponse, HomesDataResponse, HomeStatusApiResponse


class FakeMigo(MigoClient):
    """A client fake with response payloads and recorded writes."""

    def __init__(
        self,
        *,
        homes: dict[str, Any] | None = None,
        statuses: dict[str, dict[str, Any]] | None = None,
        configs: dict[str, dict[str, Any]] | None = None,
        measures: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        super().__init__("fake", "fake")
        self.homes_payload = deepcopy(homes or {"body": {"homes": []}})
        self.statuses = deepcopy(statuses or {})
        self.configs = deepcopy(configs or {})
        self.measures = deepcopy(measures or {})
        self.writes: list[tuple[str, dict[str, Any]]] = []

    async def ensure_authenticated(self) -> None:
        """Fake authentication never contacts a server."""

    async def _api_request(
        self, url: str, data: dict[str, Any] | None = None, method: str = "POST", use_json: bool = True
    ) -> dict[str, Any]:
        """Record any inherited write without opening a socket."""
        endpoint = url.rsplit("/", 1)[-1]
        payload = deepcopy(data or {})
        self.writes.append((endpoint, payload))
        home = payload.get("home", {})
        home_id = home.get("id") or payload.get("home_id")
        if home_id:
            status = self.statuses.setdefault(home_id, {"body": {"home": {"id": home_id}}})["body"]["home"]
            for key, value in home.items():
                if key in {"rooms", "modules"}:
                    existing = status.setdefault(key, [])
                    for change in value:
                        target = next((item for item in existing if item.get("id") == change.get("id")), None)
                        if target is None:
                            existing.append(deepcopy(change))
                        else:
                            target.update(deepcopy(change))
                else:
                    status[key] = deepcopy(value)
            for entry in self.homes_payload.get("body", {}).get("homes", []):
                if entry.get("id") == home_id:
                    entry.update(
                        {key: deepcopy(value) for key, value in home.items() if key not in {"rooms", "modules"}}
                    )
        return {"status": "ok"}

    async def authenticate(self) -> bool:
        return True

    async def get_homes_data(self) -> HomesDataResponse:
        return cast(HomesDataResponse, deepcopy(self.homes_payload))

    async def get_home_status(self, home_id: str) -> HomeStatusApiResponse:
        return cast(HomeStatusApiResponse, deepcopy(self.statuses.get(home_id, {"body": {"home": {}}})))

    async def get_configs(self, home_id: str) -> GetConfigsResponse:
        return cast(GetConfigsResponse, deepcopy(self.configs.get(home_id, {"body": {"home": {}}})))

    async def get_measure(
        self,
        device_id: str,
        module_id: str,
        scale: str = "1day",
        measure_types: list[str] | None = None,
        date_begin: int | None = None,
        date_end: int | None = None,
    ) -> GetMeasureResponse:
        return cast(GetMeasureResponse, deepcopy(self.measures.get(device_id, {"body": {}})))

    async def set_heating_curve(self, device_id: str, slope: float) -> dict[str, Any]:
        self.writes.append(("set_heating_curve", {"device_id": device_id, "slope": slope}))
        return {"status": "ok"}

    async def set_hysteresis(self, device_id: str, hysteresis: float) -> dict[str, Any]:
        self.writes.append(("set_hysteresis", {"device_id": device_id, "hysteresis": hysteresis}))
        return {"status": "ok"}

    async def set_temperature(
        self, home_id: str, room_id: str, temperature: float, duration: int | None = None
    ) -> dict[str, Any]:
        await super().set_temperature(home_id, room_id, temperature, duration)
        self.writes[-1] = (
            "set_temperature",
            {"home_id": home_id, "room_id": room_id, "temperature": temperature, "duration": duration},
        )
        return {"status": "ok"}
