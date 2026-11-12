"""Private heating endpoint service."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..const import API_CHANGEHEATINGALGO_URL, API_CHANGEHEATINGCURVE_URL, API_SETHEATINGSYSTEM_URL, API_SETHOMEDATA_URL

_LOGGER = logging.getLogger(__name__)


class _TransportHeatingService:
    if TYPE_CHECKING:

        async def _api_request(
            self, url: str, data: dict[str, Any] | None = None, method: str = "POST", use_json: bool = True
        ) -> dict[str, Any]: ...

    async def set_anticipation(
        self,
        home_id: str,
        enabled: bool,
    ) -> dict[str, Any]:
        """Enable or disable heating anticipation.

        Args:
            home_id: The home ID.
            enabled: True to enable anticipation, False to disable.

        Returns:
            The API response.
        """
        data = {
            "home": {
                "id": home_id,
                "anticipation": enabled,
            }
        }

        _LOGGER.debug("Setting anticipation=%s for home %s", enabled, home_id)
        return await self._api_request(API_SETHOMEDATA_URL, data)

    async def set_heating_curve(
        self,
        device_id: str,
        slope: float,
    ) -> dict[str, Any]:
        """Set heating curve (slope).

        Args:
            device_id: The gateway device ID.
            slope: The slope value in UI (0.0-5.0). API uses slope * 10.

        Returns:
            The API response.
        """
        # Convert UI value (0.0-5.0) to API value (0-50)
        api_slope = int(slope * 10)
        data = {
            "device_id": device_id,
            "slope": api_slope,
        }

        _LOGGER.debug(
            "Setting heating curve slope=%s (api=%s) for device %s",
            slope,
            api_slope,
            device_id,
        )
        return await self._api_request(API_CHANGEHEATINGCURVE_URL, data)

    async def set_heating_type(
        self,
        device_id: str,
        heating_type: str,
    ) -> dict[str, Any]:
        """Set heating system type.

        No entity exposes this yet: it is kept as a wrapper over a real
        endpoint, ready for a "heating type" select. Do not delete it as
        unused without also dropping that plan.

        Args:
            device_id: The gateway device ID.
            heating_type: The heating type (radiators, convector, floor_heating, unknown).

        Returns:
            The API response.
        """
        data = {
            "device_id": device_id,
            "heating_type": heating_type,
        }

        _LOGGER.debug("Setting heating type=%s for device %s", heating_type, device_id)
        return await self._api_request(API_SETHEATINGSYSTEM_URL, data)

    async def set_hysteresis(
        self,
        device_id: str,
        hysteresis: float,
    ) -> dict[str, Any]:
        """Set hysteresis threshold for heating algorithm.

        Args:
            device_id: The gateway device ID (e.g., "70:ee:50:6b:e3:6a").
            hysteresis: Hysteresis value in °C (0.1 to 2.0).

        Returns:
            The API response.
        """
        # API uses high_deadband = hysteresis * 10 - 1
        # e.g., 0.4°C -> high_deadband = 3, 1.8°C -> high_deadband = 17
        high_deadband = int(hysteresis * 10 - 1)

        data = {
            "device_id": device_id,
            "algo_type": "simple_algo",
            "algo_params": {
                "high_deadband": high_deadband,
            },
        }

        _LOGGER.debug(
            "Setting hysteresis=%s (high_deadband=%s) for device %s",
            hysteresis,
            high_deadband,
            device_id,
        )
        return await self._api_request(API_CHANGEHEATINGALGO_URL, data)
