"""Private state endpoint service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..const import API_SETSTATE_URL, MODE_MANUAL

_LOGGER = logging.getLogger(__name__)


class _TransportStateService:
    if TYPE_CHECKING:

        async def _api_request(
            self, url: str, data: dict[str, Any] | None = None, method: str = "POST", use_json: bool = True
        ) -> dict[str, Any]: ...

    async def set_room_state(
        self,
        home_id: str,
        room_id: str,
        mode: str | None = None,
        temp: float | None = None,
        end_time: int | None = None,
    ) -> dict[str, Any]:
        """Set room state using the setstate API.

        Args:
            home_id: The home ID.
            room_id: The room ID.
            mode: Optional mode to set (manual, home, hg).
            temp: Optional target temperature.
            end_time: Optional Unix timestamp when the setpoint expires.
                If omitted, the backend applies therm_setpoint_default_duration.

        Returns:
            The API response.
        """
        room_data: dict[str, Any] = {"id": room_id}

        if mode is not None:
            room_data["therm_setpoint_mode"] = mode

        if temp is not None:
            room_data["therm_setpoint_temperature"] = temp

        if end_time is not None:
            room_data["therm_setpoint_end_time"] = end_time

        data = {
            "home": {
                "id": home_id,
                "rooms": [room_data],
            }
        }

        _LOGGER.debug(
            "Setting room %s state: mode=%s, temp=%s, end_time=%s",
            room_id,
            mode,
            temp,
            end_time,
        )
        return await self._api_request(API_SETSTATE_URL, data)

    async def set_temperature(
        self,
        home_id: str,
        room_id: str,
        temperature: float,
        duration: int | None = None,
    ) -> dict[str, Any]:
        """Set target temperature for a room.

        This sets the room to manual mode with the specified temperature.

        Args:
            home_id: The home ID.
            room_id: The room ID.
            temperature: The target temperature in Celsius.
            duration: Optional override duration in minutes. If omitted, the
                backend applies therm_setpoint_default_duration.

        Returns:
            The API response.
        """
        end_time: int | None = None
        if duration is not None:
            end_time = int(datetime.now(UTC).timestamp()) + duration * 60

        return await self.set_room_state(
            home_id=home_id,
            room_id=room_id,
            mode=MODE_MANUAL,
            temp=temperature,
            end_time=end_time,
        )
