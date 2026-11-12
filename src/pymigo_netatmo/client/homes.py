"""Private homes endpoint service."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from ..const import (
    API_HOMESDATA_URL,
    API_HOMESTATUS_URL,
    API_SETHOMEDATA_URL,
    API_SWITCHHOMESCHEDULE_URL,
    APP_IDENTIFIER,
    APP_TYPE,
    DEVICE_TYPE_GATEWAY,
)
from ..models.wire import HomesDataResponse, HomeStatusApiResponse

_LOGGER = logging.getLogger(__name__)


class _TransportHomesService:
    if TYPE_CHECKING:

        async def _api_request(
            self, url: str, data: dict[str, Any] | None = None, method: str = "POST", use_json: bool = True
        ) -> dict[str, Any]: ...

    async def get_homes_data(self) -> HomesDataResponse:
        """Get homes data (static configuration) from API.

        This returns the structure of all homes, rooms, modules, and schedules.

        Returns:
            The homesdata response containing home configurations.
        """
        data = {
            "device_types": [DEVICE_TYPE_GATEWAY],
            "sync_measurements": True,
            "app_identifier": APP_IDENTIFIER,
            "home_id": None,
            "app_type": APP_TYPE,
        }

        _LOGGER.debug("Fetching homes data")
        return cast(HomesDataResponse, await self._api_request(API_HOMESDATA_URL, data))

    async def get_home_status(self, home_id: str) -> HomeStatusApiResponse:
        """Get home status (real-time data) from API.

        This returns current temperatures, states, and device status.

        Args:
            home_id: The ID of the home to get status for.

        Returns:
            The homestatus response containing real-time data.
        """
        data = {"home_id": home_id}

        _LOGGER.debug("Fetching home status for: %s", home_id)
        return cast(HomeStatusApiResponse, await self._api_request(API_HOMESTATUS_URL, data))

    async def set_home_therm_mode(
        self,
        home_id: str,
        mode: str,
        endtime: int | None = None,
    ) -> dict[str, Any]:
        """Set the home-level therm_mode via sethomedata, optionally with an end time.

        Unlike `set_therm_mode` (the setthermmode endpoint), this supports an
        optional Unix timestamp after which the mode automatically reverts -
        used for a "return home at" time when activating Away, which the
        MiGo app itself offers but setthermmode has no documented parameter
        for. `endtime` is always sent explicitly (including as `None`), so a
        call with no end time also clears out any previously-set one.

        Always sends `temperature_control_mode: "heating"` too, matching
        every `sethomedata` call the MiGo app itself makes for every mode
        except DHW-only (see `set_temperature_control_mode` for that one -
        confirmed live, the two cannot be combined in a single call). The
        API rejects any `therm_mode` change with a 403 ("Cannot change
        therm_mode while being in temperature_control_mode cooling") if the
        account's `temperature_control_mode` is `"cooling"` - sending
        "heating" here resets a value left over from DHW-only rather than
        reproducing that 403, confirmed live to work reliably (unlike
        pairing therm_mode with "cooling" in the same call, which never
        works no matter what mode is requested alongside it - see
        `set_temperature_control_mode`'s docstring for the full story).

        Args:
            home_id: The home ID.
            mode: The mode (schedule, away, hg).
            endtime: Optional Unix timestamp when the mode should end.
                None means indefinite.

        Returns:
            The API response.
        """
        data = {
            "home": {
                "id": home_id,
                "temperature_control_mode": "heating",
                "therm_mode": mode,
                "therm_mode_endtime": endtime,
            }
        }

        _LOGGER.debug(
            "Setting home %s therm_mode=%s endtime=%s via sethomedata",
            home_id,
            mode,
            endtime,
        )
        return await self._api_request(API_SETHOMEDATA_URL, data)

    async def set_temperature_control_mode(
        self,
        home_id: str,
        mode: str,
    ) -> dict[str, Any]:
        """Set the home's temperature_control_mode alone via sethomedata, no therm_mode field at all.

        Used to enter MiGo's "Eau chaude seulement" (DHW only) quick action
        (`mode="cooling"` - despite the name, not a literal cooling mode;
        this boiler line has no air conditioning, it's just the flag this
        account's real DHW-only quick action runs under).

        Deliberately omits `therm_mode`/`therm_mode_endtime` entirely,
        rather than resending the home's current therm_mode alongside the
        new temperature_control_mode the way `set_home_therm_mode` does.
        Reported live and confirmed: a `sethomedata` call that includes
        both `therm_mode` and `temperature_control_mode: "cooling"` gets
        rejected with a 403 ("Cannot change therm_mode while being in
        temperature_control_mode cooling"), regardless of whether
        `therm_mode`'s value actually changes from what it already was -
        the same combination with `"heating"` instead (`set_home_therm_mode`,
        used by every other home-level write in this integration) works
        fine. The restriction is specific to requesting "cooling" alongside
        a therm_mode field, not to reading/being in "cooling" generally.

        Args:
            home_id: The home ID.
            mode: "cooling" to enter DHW-only, "heating" to leave it
                without also touching therm_mode (prefer
                `set_home_therm_mode` when a therm_mode change is wanted
                too - it resets this field to "heating" as part of the
                same call).

        Returns:
            The API response.
        """
        data = {
            "home": {
                "id": home_id,
                "temperature_control_mode": mode,
            }
        }

        _LOGGER.debug("Setting home %s temperature_control_mode=%s via sethomedata", home_id, mode)
        return await self._api_request(API_SETHOMEDATA_URL, data)

    async def switch_home_schedule(
        self,
        home_id: str,
        schedule_id: str,
    ) -> dict[str, Any]:
        """Switch to a different schedule.

        Args:
            home_id: The home ID.
            schedule_id: The schedule ID to activate.

        Returns:
            The API response.
        """
        data = {
            "home_id": home_id,
            "schedule_id": schedule_id,
        }

        _LOGGER.debug("Switching home %s to schedule: %s", home_id, schedule_id)
        return await self._api_request(API_SWITCHHOMESCHEDULE_URL, data)
