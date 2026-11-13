"""Argparse construction: the subcommand tree and its input validators."""

from __future__ import annotations

import argparse
import functools
import os
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from ..const import (
    DHW_TEMP_MAX,
    DHW_TEMP_MIN,
    DHW_TEMP_STEP,
    HEATING_CURVE_MAX,
    HEATING_CURVE_MIN,
    HEATING_CURVE_STEP,
    HYSTERESIS_MAX,
    HYSTERESIS_MIN,
    HYSTERESIS_STEP,
    MANUAL_SETPOINT_DURATION_MAX,
    MANUAL_SETPOINT_DURATION_MIN,
    MANUAL_SETPOINT_DURATION_STEP,
    MEASURE_TYPES,
    TEMP_MAX,
    TEMP_MIN,
    TEMP_OFFSET_MAX,
    TEMP_OFFSET_MIN,
    TEMP_OFFSET_STEP,
    TEMP_STEP,
)

HOME_MODES = ("schedule", "away", "hg")
ROOM_MODES = ("manual", "home", "hg")
CONTROL_MODES = ("heating", "dhw-only")
HEATING_TYPES = ("radiators", "convector", "floor_heating")
DHW_STORAGES = ("water-tank", "instantaneous")
MEASURE_SCALES = ("30min", "1hour", "3hours", "1day", "1week", "1month")


def _stepped_float(low: float, high: float, step: float, name: str) -> Callable[[str], float]:
    def validator(value: str) -> float:
        try:
            number = float(value)
        except ValueError as err:
            raise argparse.ArgumentTypeError(f"{name} must be a number") from err
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f"{name} must be between {low:g} and {high:g}")
        if abs((number - low) - round((number - low) / step) * step) > 1e-9:
            raise argparse.ArgumentTypeError(f"{name} must go by steps of {step:g} from {low:g}")
        # Snap to the grid: the check above tolerates float noise, the library truncates what it sends.
        return round(number, 6)

    return validator


def _stepped_int(low: int, high: int, step: int, name: str) -> Callable[[str], int]:
    def validator(value: str) -> int:
        try:
            number = int(value)
        except ValueError as err:
            raise argparse.ArgumentTypeError(f"{name} must be an integer") from err
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f"{name} must be between {low} and {high}")
        if (number - low) % step:
            raise argparse.ArgumentTypeError(f"{name} must go by steps of {step} from {low}")
        return number

    return validator


def _moment(name: str) -> Callable[[str], int]:
    """An ISO 8601 date and time as a Unix timestamp. A time without an offset is local."""

    def parse(value: str) -> int:
        try:
            moment = datetime.fromisoformat(value)
        except ValueError as err:
            raise argparse.ArgumentTypeError(
                f"{name} must be an ISO 8601 date and time, like 2026-11-20T18:00"
            ) from err
        return int(moment.astimezone().timestamp())

    return parse


def _until(value: str) -> int:
    timestamp = _moment("--until")(value)
    if timestamp <= time.time():
        raise argparse.ArgumentTypeError("--until must be in the future")
    return timestamp


def _add_global_options(parser: argparse.ArgumentParser, *, defaults: bool) -> None:
    """Options every command accepts, before or after its name."""

    def default(value: object) -> object:
        return value if defaults else argparse.SUPPRESS

    parser.add_argument(
        "--username", default=default(os.environ.get("MIGO_USERNAME")), help="account email (default: MIGO_USERNAME)"
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        default=default(None),
        help="persist the refresh token in a private account-bound file",
    )
    parser.add_argument("--home-id", default=default(None), help="home to use (default: the only home of the account)")
    parser.add_argument(
        "--client-id",
        default=default(os.environ.get("MIGO_CLIENT_ID")),
        help="OAuth client id (default: MIGO_CLIENT_ID)",
    )
    parser.add_argument(
        "--user-prefix",
        default=default(os.environ.get("MIGO_USER_PREFIX")),
        help="OAuth user prefix (default: MIGO_USER_PREFIX)",
    )
    parser.add_argument(
        "--redact",
        action="store_true",
        default=default(False),
        help="replace personal data in the printed backend data",
    )
    parser.add_argument(
        "--raw-log",
        action="store_true",
        default=default(False),
        help="log unredacted API payloads on stderr (personal data)",
    )
    parser.add_argument("--json", action="store_true", default=default(False), help="machine readable output")
    parser.add_argument("-y", "--yes", action="store_true", default=default(False), help="skip the confirmation")
    parser.add_argument("-v", "--verbose", action="store_true", default=default(False), help="debug logging")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pymigo-netatmo",
        description="Read and control a MiGO heating system. Without a command, prints the account snapshot.",
        epilog="Exit codes: 0 success, 1 error, 2 usage, 3 retry later, 4 authentication failure.",
    )
    _add_global_options(parser, defaults=True)
    # The same options again on every subcommand, so they also work after it. There they default
    # to nothing, which leaves the value given before the subcommand in place.
    shared = argparse.ArgumentParser(add_help=False)
    _add_global_options(shared, defaults=False)

    sub = parser.add_subparsers(dest="command", required=False)
    command = functools.partial(sub.add_parser, parents=[shared])

    command("snapshot", help="print the raw account snapshot as JSON (the default command)")
    command("status", help="homes, rooms, temperatures, gateways, thermostats and schedules")
    command("homes-data", help="print the raw homes, rooms and modules of the account as JSON")
    command("home-status", help="print the raw live status of a home as JSON")
    command("configs", help="print the raw configuration of a home as JSON")
    command("login", help="sign in with the password, and store the refresh token with --token-file")
    command("logout", help="delete the token file (the token is not revoked on the server)")

    measure = command("measure", help="print consumption measurements of a gateway and its thermostat as JSON")
    measure.add_argument("gateway_id", help="gateway id (type NAVaillant), from `status`")
    measure.add_argument("thermostat_id", help="thermostat id (type NAThermVaillant), from `status`")
    measure.add_argument("--scale", choices=MEASURE_SCALES, default="1day", help="time scale (default: 1day)")
    measure.add_argument(
        "--type",
        dest="types",
        action="append",
        choices=MEASURE_TYPES,
        help="measure to retrieve, repeatable (default: sum_boiler_on and sum_boiler_off)",
    )
    measure.add_argument("--from", dest="date_begin", type=_moment("--from"), help="ISO 8601 start of the period")
    measure.add_argument("--to", dest="date_end", type=_moment("--to"), help="ISO 8601 end of the period")
    measure.add_argument("--latest", action="store_true", help="print only the latest valid daily reading")

    temperature = command("set-temperature", help="set a room temperature (drives real heating)")
    temperature.add_argument("room_id", help="room id, from `status`")
    temperature.add_argument(
        "temperature", type=_stepped_float(TEMP_MIN, TEMP_MAX, TEMP_STEP, "temperature"), help="degrees Celsius"
    )
    temperature.add_argument(
        "--duration",
        type=_stepped_int(
            MANUAL_SETPOINT_DURATION_MIN,
            MANUAL_SETPOINT_DURATION_MAX,
            MANUAL_SETPOINT_DURATION_STEP,
            "--duration",
        ),
        help="minutes before the setpoint expires (default: the backend's default duration)",
    )

    mode = command("set-mode", help="set the home mode (drives real heating)")
    mode.add_argument("mode", choices=HOME_MODES, help="schedule, away or hg (frost guard)")
    mode.add_argument("--until", type=_until, help="ISO 8601 date and time the mode ends (away and hg only)")

    curve = command("set-heating-curve", help="set the heating curve slope (drives a real boiler)")
    curve.add_argument("gateway_id", help="gateway id, from `status`")
    curve.add_argument("slope", type=_stepped_float(HEATING_CURVE_MIN, HEATING_CURVE_MAX, HEATING_CURVE_STEP, "slope"))

    hysteresis = command("set-hysteresis", help="set the hysteresis (drives a real boiler)")
    hysteresis.add_argument("gateway_id", help="gateway id, from `status`")
    hysteresis.add_argument(
        "hysteresis", type=_stepped_float(HYSTERESIS_MIN, HYSTERESIS_MAX, HYSTERESIS_STEP, "hysteresis")
    )

    dhw = command("set-dhw", help="turn domestic hot water on or off (drives a real boiler)")
    dhw.add_argument("gateway_id", help="gateway id, from `status`")
    dhw.add_argument("state", choices=("on", "off"))

    dhw_temperature = command("set-dhw-temperature", help="set the hot water temperature (drives a real boiler)")
    dhw_temperature.add_argument("gateway_id", help="gateway id, from `status`")
    dhw_temperature.add_argument(
        "temperature",
        type=_stepped_int(DHW_TEMP_MIN, DHW_TEMP_MAX, DHW_TEMP_STEP, "temperature"),
        help="degrees Celsius",
    )

    room_state = command("set-room-state", help="set a room mode and or setpoint (drives real heating)")
    room_state.add_argument("room_id", help="room id, from `status`")
    room_state.add_argument("--mode", choices=ROOM_MODES, help="manual, home or hg (frost guard)")
    room_state.add_argument(
        "--temperature", type=_stepped_float(TEMP_MIN, TEMP_MAX, TEMP_STEP, "--temperature"), help="degrees Celsius"
    )
    room_state.add_argument("--until", type=_until, help="ISO 8601 date and time the setpoint expires")

    offset = command("set-temperature-offset", help="set a room temperature offset (drives real heating)")
    offset.add_argument("room_id", help="room id, from `status`")
    offset.add_argument(
        "offset", type=_stepped_float(TEMP_OFFSET_MIN, TEMP_OFFSET_MAX, TEMP_OFFSET_STEP, "offset"), help="degrees"
    )

    control = command("set-control-mode", help="heating, or hot water only (drives a real boiler)")
    control.add_argument("mode", choices=CONTROL_MODES)

    duration = command("set-setpoint-duration", help="default duration of a manual setpoint (drives real heating)")
    duration.add_argument(
        "minutes",
        type=_stepped_int(
            MANUAL_SETPOINT_DURATION_MIN, MANUAL_SETPOINT_DURATION_MAX, MANUAL_SETPOINT_DURATION_STEP, "minutes"
        ),
    )

    anticipation = command("set-anticipation", help="turn heating anticipation on or off (drives real heating)")
    anticipation.add_argument("state", choices=("on", "off"))

    schedule = command("switch-schedule", help="activate another weekly schedule (drives real heating)")
    schedule.add_argument("schedule_id", help="schedule id, from `status`")

    heating_type = command("set-heating-type", help="set the heating system type (drives a real boiler)")
    heating_type.add_argument("gateway_id", help="gateway id, from `status`")
    heating_type.add_argument("heating_type", choices=HEATING_TYPES)

    always_on = command("set-dhw-always-on", help="keep hot water production always on (drives a real boiler)")
    always_on.add_argument("gateway_id", help="gateway id, from `status`")
    always_on.add_argument("state", choices=("on", "off"))

    storage = command("set-dhw-storage", help="hot water from a tank or instantaneous (drives a real boiler)")
    storage.add_argument("gateway_id", help="gateway id, from `status`")
    storage.add_argument("storage", choices=DHW_STORAGES)

    return parser
