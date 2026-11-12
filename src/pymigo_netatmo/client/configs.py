"""Private configs endpoint service."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from ..const import API_GETCONFIGS_URL, API_SETCONFIGS_URL, API_SETHOMEDATA_URL, API_SETSTATE_URL
from ..models.wire import GetConfigsResponse

_LOGGER = logging.getLogger(__name__)


class _TransportConfigsService:
    if TYPE_CHECKING:

        async def _api_request(
            self, url: str, data: dict[str, Any] | None = None, method: str = "POST", use_json: bool = True
        ) -> dict[str, Any]: ...

    async def get_configs(self, home_id: str) -> GetConfigsResponse:
        """Get module configurations from API.

        This returns configuration data that may not be in homesdata/homestatus,
        such as DHW setpoint temperature.

        Args:
            home_id: The ID of the home to get configs for.

        Returns:
            The getconfigs response containing module configurations.
        """
        data = {"home_id": home_id}

        _LOGGER.debug("Fetching configs for: %s", home_id)
        return cast(GetConfigsResponse, await self._api_request(API_GETCONFIGS_URL, data))

    async def set_dhw_enabled(
        self,
        home_id: str,
        module_id: str,
        enabled: bool,
    ) -> dict[str, Any]:
        """Enable or disable domestic hot water (DHW/ECS).

        Args:
            home_id: The home ID.
            module_id: The NAVaillant module ID (gateway).
            enabled: True to enable DHW, False to disable.

        Returns:
            The API response.
        """
        data = {
            "home": {
                "id": home_id,
                "modules": [
                    {
                        "id": module_id,
                        "dhw_enabled": enabled,
                    }
                ],
            }
        }

        _LOGGER.debug("Setting DHW enabled=%s for module %s", enabled, module_id)
        return await self._api_request(API_SETSTATE_URL, data)

    async def set_dhw_storage(
        self,
        home_id: str,
        module_id: str,
        use_water_tank: bool,
    ) -> dict[str, Any]:
        """Set DHW storage mode (water tank vs instantaneous).

        No entity exposes this yet: it is kept as a wrapper over a real
        endpoint, ready for a DHW storage switch. Do not delete it as
        unused without also dropping that plan.

        Args:
            home_id: The home ID.
            module_id: The gateway module ID.
            use_water_tank: True for water tank, False for instantaneous.

        Returns:
            The API response.
        """
        dhw_control = "water_tank" if use_water_tank else "instantaneous"
        data = {
            "home": {
                "id": home_id,
                "modules": [
                    {
                        "id": module_id,
                        "dhw_control": dhw_control,
                    }
                ],
            }
        }

        _LOGGER.debug("Setting DHW storage=%s for module %s", dhw_control, module_id)
        return await self._api_request(API_SETHOMEDATA_URL, data)

    async def set_dhw_temperature(
        self,
        home_id: str,
        module_id: str,
        temperature: int,
    ) -> dict[str, Any]:
        """Set domestic hot water temperature.

        Args:
            home_id: The home ID.
            module_id: The gateway module ID.
            temperature: The DHW temperature (45-65°C).

        Returns:
            The API response.
        """
        # Based on mitmproxy capture: the API expects home_id at root level
        # and home.modules[].dhw_setpoint_temperature for the value
        data = {
            "home_id": home_id,
            "home": {
                "modules": [
                    {
                        "id": module_id,
                        "dhw_setpoint_temperature": temperature,
                    }
                ],
            },
        }

        _LOGGER.debug("Setting DHW temperature=%s for module %s", temperature, module_id)
        return await self._api_request(API_SETCONFIGS_URL, data)

    async def set_dhw_always_on(
        self,
        home_id: str,
        module_id: str,
        enabled: bool,
    ) -> dict[str, Any]:
        """Set whether DHW production always stays on, overriding the schedule.

        `dhw_always_on` is undocumented by Netatmo, confirmed via a live
        debug-log capture of `/syncapi/v1/getconfigs`'s response - it sits
        on the same module entry as `dhw_setpoint_temperature`, which is
        why this follows the exact same request shape as
        `set_dhw_temperature` rather than `set_dhw_enabled` (which is a
        `setstate` call, a different endpoint entirely, for the per-slot
        schedule flag `dhw_always_on` overrides).

        Args:
            home_id: The home ID.
            module_id: The gateway module ID.
            enabled: True to force DHW production always on.

        Returns:
            The API response.
        """
        data = {
            "home_id": home_id,
            "home": {
                "modules": [
                    {
                        "id": module_id,
                        "dhw_always_on": enabled,
                    }
                ],
            },
        }

        _LOGGER.debug("Setting DHW always-on=%s for module %s", enabled, module_id)
        return await self._api_request(API_SETCONFIGS_URL, data)

    async def set_temperature_offset(
        self,
        home_id: str,
        room_id: str,
        offset: float,
    ) -> dict[str, Any]:
        """Set room temperature offset.

        Args:
            home_id: The home ID.
            room_id: The room ID.
            offset: The temperature offset (-5.0 to +5.0°C).

        Returns:
            The API response.
        """
        # setconfigs's other calls (set_dhw_temperature, set_dhw_always_on) were
        # confirmed via mitmproxy capture to need home_id at the root level, not
        # just nested under home.id - this call was missing that root-level key,
        # which is the likely reason it silently failed to take effect server-side
        # (reported live: neither sets nor reads back the real value). home.id is
        # kept too, matching the shape captured for this specific rooms variant.
        data = {
            "home_id": home_id,
            "home": {
                "id": home_id,
                "rooms": [
                    {
                        "id": room_id,
                        "therm_setpoint_offset": offset,
                    }
                ],
            },
        }

        _LOGGER.debug("Setting temperature offset=%s for room %s", offset, room_id)
        return await self._api_request(API_SETCONFIGS_URL, data)

    async def set_manual_setpoint_duration(
        self,
        home_id: str,
        duration: int,
    ) -> dict[str, Any]:
        """Set default duration for manual setpoints.

        Args:
            home_id: The home ID.
            duration: Duration in minutes (5-720, i.e., 5min to 12h).

        Returns:
            The API response.
        """
        data = {
            "home": {
                "id": home_id,
                "therm_setpoint_default_duration": duration,
            }
        }

        _LOGGER.debug("Setting manual setpoint duration=%s for home %s", duration, home_id)
        return await self._api_request(API_SETHOMEDATA_URL, data)
