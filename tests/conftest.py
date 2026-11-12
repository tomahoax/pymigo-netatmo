"""Pure API payload fixtures, independent of Home Assistant."""

from typing import Any

import pytest


@pytest.fixture
def homes_data_response() -> dict[str, Any]:
    """Return mock homes data response."""
    return {
        "body": {
            "user": {"email": "test@example.com", "country": "FR"},
            "homes": [
                {
                    "id": "home_123",
                    "name": "My Home",
                    "therm_mode": "schedule",
                    "coordinates": [49.123456, 2.654321],
                    "city": "Somewhere",
                    "country": "FR",
                    "altitude": 120,
                    "timezone": "Europe/Paris",
                    "invitation_code": ["ZsdApbpjOstMdOn1"],
                    "rooms": [
                        {"id": "room_456", "name": "Living Room", "type": "living_room", "module_ids": ["module_789"]}
                    ],
                    "modules": [
                        {"id": "gateway_001", "type": "NAVaillant", "subtype": "NAEbusSdbg", "oem_serial": "SN123456"},
                        {"id": "module_789", "type": "NAThermVaillant", "room_id": "room_456", "bridge": "gateway_001"},
                    ],
                    "schedules": [
                        {"id": "schedule_001", "name": "Default", "type": "therm", "selected": True, "default": True}
                    ],
                }
            ],
        },
        "status": "ok",
    }


@pytest.fixture
def home_status_response() -> dict[str, Any]:
    """Return mock home status response."""
    return {
        "body": {
            "home": {
                "id": "home_123",
                "rooms": [
                    {
                        "id": "room_456",
                        "therm_measured_temperature": 21.5,
                        "therm_setpoint_temperature": 20.0,
                        "therm_setpoint_mode": "schedule",
                        "reachable": True,
                        "anticipating": False,
                    }
                ],
                "modules": [
                    {
                        "id": "gateway_001",
                        "type": "NAVaillant",
                        "wifi_strength": 70,
                        "firmware_revision": 1030,
                        "dhw_enabled": True,
                        "ebus_error": False,
                        "boiler_error": [],
                    },
                    {
                        "id": "module_789",
                        "type": "NAThermVaillant",
                        "battery_percent": 85,
                        "battery_state": "high",
                        "rf_strength": 65,
                        "firmware_revision": 72,
                        "reachable": True,
                        "boiler_status": True,
                    },
                ],
            }
        },
        "status": "ok",
    }


@pytest.fixture
def configs_response() -> dict[str, Any]:
    """Return mock getconfigs response."""
    return {
        "body": {"home": {"id": "home_123", "modules": [{"id": "gateway_001", "dhw_setpoint_temperature": 55}]}},
        "status": "ok",
    }


@pytest.fixture
def consumption_response() -> dict[str, Any]:
    """Return mock consumption data response from /api/getmeasure.

    A dict keyed by timestamp, each value one row in const.MEASURE_TYPES order:
    [boiler_on, boiler_off, gas_heating, gas_hot_water, elec_heating,
     elec_hot_water]. Boiler times are seconds; energy is Wh at whole-kWh
    resolution, which is what the real API returns.
    """
    return {
        "body": {
            "1704067200": [3600, 82800, 12000, 3000, 100, 50],
            "1704153600": [7200, 79200, 24000, 4000, 200, 100],
            "1704240000": [5400, 81000, 18000, 2000, 150, 75],
        },
        "status": "ok",
        "time_exec": 0.05,
        "time_server": 1704326400,
    }


@pytest.fixture
def token_response() -> dict[str, Any]:
    """Return mock token response."""
    return {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 10800,
        "scope": ["all_scopes"],
    }
