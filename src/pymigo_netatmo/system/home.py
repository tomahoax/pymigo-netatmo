"""Home-scoped control facade.

Wire conversion is owned by the client endpoint implementation, so every
consumer (facade or low-level client) uses the same conversion rules.
"""

from __future__ import annotations

from typing import Any

from ..client import MigoClient


class MigoHome:
    def __init__(self, client: MigoClient, home_id: str) -> None:
        self.client = client
        self.id = home_id

    async def set_temperature(self, room_id: str, temperature: float, duration: int | None = None) -> dict[str, Any]:
        return await self.client.set_temperature(
            home_id=self.id, room_id=room_id, temperature=temperature, duration=duration
        )

    async def set_room_state(
        self, room_id: str, mode: str | None = None, temp: float | None = None, end_time: int | None = None
    ) -> dict[str, Any]:
        return await self.client.set_room_state(self.id, room_id, mode, temp, end_time)

    async def set_therm_mode(self, mode: str, endtime: int | None = None) -> dict[str, Any]:
        return await self.client.set_home_therm_mode(self.id, mode, endtime)

    async def set_temperature_control_mode(self, mode: str) -> dict[str, Any]:
        return await self.client.set_temperature_control_mode(self.id, mode)

    async def set_dhw_enabled(self, module_id: str, enabled: bool) -> dict[str, Any]:
        return await self.client.set_dhw_enabled(self.id, module_id, enabled)

    async def set_dhw_temperature(self, module_id: str, temperature: int) -> dict[str, Any]:
        return await self.client.set_dhw_temperature(self.id, module_id, temperature)

    async def set_dhw_always_on(self, module_id: str, enabled: bool) -> dict[str, Any]:
        return await self.client.set_dhw_always_on(self.id, module_id, enabled)

    async def set_temperature_offset(self, room_id: str, offset: float) -> dict[str, Any]:
        return await self.client.set_temperature_offset(self.id, room_id, offset)

    async def set_manual_setpoint_duration(self, duration: int) -> dict[str, Any]:
        return await self.client.set_manual_setpoint_duration(self.id, duration)

    async def set_anticipation(self, enabled: bool) -> dict[str, Any]:
        return await self.client.set_anticipation(self.id, enabled)

    async def switch_schedule(self, schedule_id: str) -> dict[str, Any]:
        return await self.client.switch_home_schedule(self.id, schedule_id)

    async def set_heating_curve(self, device_id: str, slope: float) -> dict[str, Any]:
        return await self.client.set_heating_curve(device_id=device_id, slope=slope)

    async def set_hysteresis(self, device_id: str, hysteresis: float) -> dict[str, Any]:
        return await self.client.set_hysteresis(device_id=device_id, hysteresis=hysteresis)
