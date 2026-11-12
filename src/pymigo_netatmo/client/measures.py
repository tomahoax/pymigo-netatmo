"""Private measures endpoint service."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from ..const import API_GETMEASURE_URL
from ..models.wire import GetMeasureResponse

_LOGGER = logging.getLogger(__name__)


class _TransportMeasuresService:
    if TYPE_CHECKING:

        async def _api_request(
            self, url: str, data: dict[str, Any] | None = None, method: str = "POST", use_json: bool = True
        ) -> dict[str, Any]: ...

    async def get_measure(
        self,
        device_id: str,
        module_id: str,
        scale: str = "1day",
        measure_types: list[str] | None = None,
        date_begin: int | None = None,
        date_end: int | None = None,
    ) -> GetMeasureResponse:
        """Get measurements (historical data) from API using device/module IDs.

        This is the endpoint used by Vaillant vSmart integration for boiler runtime.
        Unlike getroommeasure which uses home/room IDs, this uses device/module IDs.

        Args:
            device_id: The ID of the gateway device (NAVaillant).
            module_id: The ID of the thermostat module (NAThermVaillant).
            scale: Time scale for measurements (30min, 1hour, 3hours, 1day, 1week, 1month).
            measure_types: List of measure types to retrieve. If None, defaults to
                          ["sum_boiler_on", "sum_boiler_off"].
            date_begin: Optional start timestamp (Unix timestamp).
            date_end: Optional end timestamp (Unix timestamp).

        Returns:
            The getmeasure response containing historical measurements.
        """
        if measure_types is None:
            measure_types = [
                "sum_boiler_on",
                "sum_boiler_off",
            ]

        data: dict[str, Any] = {
            "device_id": device_id,
            "module_id": module_id,
            "scale": scale,
            "type": ",".join(measure_types),
        }

        if date_begin is not None:
            data["date_begin"] = date_begin
        if date_end is not None:
            data["date_end"] = date_end

        _LOGGER.debug(
            "Fetching measure for device=%s, module=%s, scale=%s, types=%s",
            device_id,
            module_id,
            scale,
            measure_types,
        )
        # getmeasure uses form data, not JSON (legacy API)
        return cast(GetMeasureResponse, await self._api_request(API_GETMEASURE_URL, data, use_json=False))
