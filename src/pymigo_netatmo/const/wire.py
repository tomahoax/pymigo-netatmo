"""Wire protocol constants."""

from typing import Final

API_BASE_URL: Final = "https://app.netatmo.net"
API_AUTH_URL: Final = f"{API_BASE_URL}/oauth2/token"
API_HOMESDATA_URL: Final = f"{API_BASE_URL}/api/homesdata"
API_HOMESTATUS_URL: Final = f"{API_BASE_URL}/api/homestatus"
API_SETSTATE_URL: Final = f"{API_BASE_URL}/api/setstate"
API_SETHOMEDATA_URL: Final = f"{API_BASE_URL}/api/sethomedata"
API_SWITCHHOMESCHEDULE_URL: Final = f"{API_BASE_URL}/api/switchhomeschedule"
API_CHANGEHEATINGCURVE_URL: Final = f"{API_BASE_URL}/api/changeheatingcurve"
API_SETHEATINGSYSTEM_URL: Final = f"{API_BASE_URL}/api/setheatingsystem"
API_SETCONFIGS_URL: Final = f"{API_BASE_URL}/syncapi/v1/setconfigs"
API_CHANGEHEATINGALGO_URL: Final = f"{API_BASE_URL}/api/changeheatingalgo"
API_GETMEASURE_URL: Final = f"{API_BASE_URL}/api/getmeasure"
API_GETCONFIGS_URL: Final = f"{API_BASE_URL}/syncapi/v1/getconfigs"
CLIENT_ID: Final = "na_client_ios_sdbg"
CLIENT_SECRET: Final = "2139e4db25b33c417c62b779ada3f4e4"
USER_PREFIX: Final = "sdbg"
SCOPE: Final = "all_scopes"
GRANT_TYPE_PASSWORD: Final = "password"
GRANT_TYPE_REFRESH: Final = "refresh_token"
DEVICE_TYPE_GATEWAY: Final = "NAVaillant"
DEVICE_TYPE_THERMOSTAT: Final = "NAThermVaillant"
APP_IDENTIFIER: Final = "app_thermostat_sdbg"
APP_TYPE: Final = "app_thermostat_sdbg"
MODE_SCHEDULE: Final = "schedule"
MODE_AWAY: Final = "away"
MODE_FROST_GUARD: Final = "hg"
MODE_MANUAL: Final = "manual"
MODE_HOME: Final = "home"
MODE_OFF: Final = "off"
BOILER_MODE_NORMAL: Final = "normal"
BOILER_MODE_DHW_ONLY: Final = "dhw_only"
BOILER_MODE_FROST_GUARD: Final = "frost_guard"
SCHEDULE_TYPE_THERM: Final = "therm"
SCHEDULE_TYPE_EVENT: Final = "event"
MEASURE_BOILER_ON: Final = "sum_boiler_on"
MEASURE_BOILER_OFF: Final = "sum_boiler_off"
MEASURE_GAS_HEATING: Final = "sum_energy_gaz_heating"
MEASURE_GAS_HOT_WATER: Final = "sum_energy_gaz_hot_water"
MEASURE_ELEC_HEATING: Final = "sum_energy_elec_heating"
MEASURE_ELEC_HOT_WATER: Final = "sum_energy_elec_hot_water"
MEASURE_TYPES: Final = (
    MEASURE_BOILER_ON,
    MEASURE_BOILER_OFF,
    MEASURE_GAS_HEATING,
    MEASURE_GAS_HOT_WATER,
    MEASURE_ELEC_HEATING,
    MEASURE_ELEC_HOT_WATER,
)
WH_PER_KWH: Final = 1000
KEY_BODY: Final = "body"
KEY_HOME: Final = "home"
KEY_HOMES: Final = "homes"
KEY_ROOMS: Final = "rooms"
KEY_MODULES: Final = "modules"
TOKEN_EXPIRY_BUFFER: Final = 300
API_TIMEOUT: Final = 30
DEFAULT_MANUAL_SETPOINT_DURATION: Final = 180
DEFAULT_BOOST_DURATION: Final = 60
DEFAULT_DHW_TEMPERATURE: Final = 60
DEFAULT_HYSTERESIS: Final = 1.6
DEFAULT_TEMP_OFFSET: Final = 0.0
