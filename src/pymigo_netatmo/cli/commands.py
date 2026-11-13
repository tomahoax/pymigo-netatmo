"""The commands: snapshot, status and the writes that drive the heating."""

from __future__ import annotations

import argparse
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from ..client import MigoClient
from ..const import DEVICE_TYPE_GATEWAY, DEVICE_TYPE_THERMOSTAT
from ..redaction import redact
from ..system import MigoAccount, MigoHome, parse_consumption
from .exit_codes import EXIT_OK
from .output import UsageError, emit, emit_json

Command = Callable[[argparse.Namespace, MigoClient], Awaitable[int]]


async def _home_id(args: argparse.Namespace, client: MigoClient) -> str:
    """The home given with `--home-id`, or the only one of the account."""
    if args.home_id:
        return str(args.home_id)
    body = (await client.get_homes_data()).get("body")
    homes = body.get("homes") if isinstance(body, dict) else None
    ids = [home["id"] for home in homes or [] if home.get("id") and home.get("modules")]
    if len(ids) == 1:
        return str(ids[0])
    if not ids:
        raise UsageError("This account has no home with a heating system")
    raise UsageError(f"This account has several homes, pass --home-id with one of: {', '.join(ids)}")


def _sent(args: argparse.Namespace, response: dict[str, Any], sent: dict[str, Any], line: str) -> int:
    """Report a write the backend accepted."""
    status = response.get("status")
    emit({"command": args.command, **sent, "status": status}, [f"{line} (status: {status})"], args.json)
    return EXIT_OK


def _until_text(until: int | None) -> str:
    return "" if until is None else f" until {datetime.fromtimestamp(until).astimezone().isoformat(timespec='minutes')}"


def _on_off_text(enabled: object) -> str:
    """`unknown` when the configuration read failed and left the flag missing."""
    return "unknown" if enabled is None else "on" if enabled else "off"


def _on_off(args: argparse.Namespace) -> bool:
    return bool(args.state == "on")


async def cmd_snapshot(args: argparse.Namespace, client: MigoClient) -> int:
    snapshot = await MigoAccount(client).read_snapshot()
    emit_json(snapshot.raw, args.redact)
    return EXIT_OK


async def cmd_homes_data(args: argparse.Namespace, client: MigoClient) -> int:
    emit_json(await client.get_homes_data(), args.redact)
    return EXIT_OK


async def cmd_home_status(args: argparse.Namespace, client: MigoClient) -> int:
    emit_json(await client.get_home_status(await _home_id(args, client)), args.redact)
    return EXIT_OK


async def cmd_configs(args: argparse.Namespace, client: MigoClient) -> int:
    emit_json(await client.get_configs(await _home_id(args, client)), args.redact)
    return EXIT_OK


async def cmd_measure(args: argparse.Namespace, client: MigoClient) -> int:
    response = await client.get_measure(
        device_id=args.gateway_id,
        module_id=args.thermostat_id,
        scale=args.scale,
        measure_types=args.types,
        date_begin=args.date_begin,
        date_end=args.date_end,
    )
    if args.latest:
        reading = parse_consumption(response.get("body"))
        emit_json({"consumption": None if reading is None else reading.raw}, args.redact)
    else:
        emit_json(response, args.redact)
    return EXIT_OK


async def cmd_login(args: argparse.Namespace, client: MigoClient) -> int:
    """Validate the password and, with --token-file, store the refresh token it returns."""
    await client.authenticate()
    stored = args.token_file is not None
    line = "Signed in, refresh token stored." if stored else "Signed in. No --token-file given, nothing stored."
    emit({"signed_in": True, "token_stored": stored}, [line], args.json)
    return EXIT_OK


async def cmd_logout(args: argparse.Namespace) -> int:
    path = Path(args.token_file).expanduser()
    removed = path.exists()
    path.unlink(missing_ok=True)
    line = "Token file deleted." if removed else "No token file."
    emit({"signed_out": True, "removed": removed}, [f"{line} The token is not revoked on the server."], args.json)
    return EXIT_OK


async def cmd_status(args: argparse.Namespace, client: MigoClient) -> int:
    # `status` shows no consumption, so it skips the measure request made for each gateway.
    snapshot = await MigoAccount(client).read_snapshot(consumption=False)
    homes: list[dict[str, Any]] = []
    for home_id, home in snapshot.homes.items():
        modules = [
            (module_id, module) for module_id, module in snapshot.devices.items() if module.get("home_id") == home_id
        ]
        homes.append(
            {
                "id": home_id,
                "name": home.get("name"),
                "mode": home.get("therm_mode"),
                "rooms": [
                    {
                        "id": room_id,
                        "name": room.get("name"),
                        "temperature": room.get("therm_measured_temperature"),
                        "setpoint": room.get("therm_setpoint_temperature"),
                        "setpoint_mode": room.get("therm_setpoint_mode"),
                        "reachable": room.get("reachable"),
                    }
                    for room_id, room in snapshot.rooms.items()
                    if room.get("home_id") == home_id
                ],
                "gateways": [
                    {
                        "id": module_id,
                        "type": module.get("type"),
                        "dhw_enabled": module.get("dhw_enabled"),
                        "dhw_setpoint_temperature": module.get("dhw_setpoint_temperature"),
                    }
                    for module_id, module in modules
                    if module.get("type") == DEVICE_TYPE_GATEWAY
                ],
                "thermostats": [
                    {
                        "id": module_id,
                        "type": module.get("type"),
                        "room_id": module.get("room_id"),
                        "gateway_id": module.get("bridge"),
                        "reachable": module.get("reachable"),
                    }
                    for module_id, module in modules
                    if module.get("type") == DEVICE_TYPE_THERMOSTAT
                ],
                "schedules": [
                    {"id": schedule.get("id"), "name": schedule.get("name"), "selected": bool(schedule.get("selected"))}
                    for schedule in home.get("schedules") or []
                    if isinstance(schedule, dict) and schedule.get("type", "therm") == "therm"
                ],
            }
        )
    if args.redact:
        homes = redact(homes)
    lines: list[str] = []
    for entry in homes:
        lines.append(f"Home {entry['name']} ({entry['id']}), mode {entry['mode']}")
        lines.extend(
            f"  Room {room['name']} ({room['id']}): {room['temperature']} C, "
            f"setpoint {room['setpoint']} C ({room['setpoint_mode']})"
            for room in entry["rooms"]
        )
        lines.extend(
            f"  Gateway {gateway['id']}: hot water {_on_off_text(gateway['dhw_enabled'])}, "
            f"{gateway['dhw_setpoint_temperature']} C"
            for gateway in entry["gateways"]
        )
        lines.extend(
            f"  Thermostat {thermostat['id']}: room {thermostat['room_id']}, gateway {thermostat['gateway_id']}"
            for thermostat in entry["thermostats"]
        )
        lines.extend(
            f"  Schedule {schedule['name']} ({schedule['id']}){' (active)' if schedule['selected'] else ''}"
            for schedule in entry["schedules"]
        )
    emit({"homes": homes}, lines or ["No home."], args.json)
    return EXIT_OK


async def cmd_set_temperature(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    response = await MigoHome(client, home_id).set_temperature(args.room_id, args.temperature, args.duration)
    sent = {
        "home_id": home_id,
        "room_id": args.room_id,
        "temperature": args.temperature,
        "duration": args.duration,
    }
    return _sent(args, response, sent, f"Room {args.room_id} set to {args.temperature:g} C")


async def cmd_set_mode(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    response = await MigoHome(client, home_id).set_therm_mode(args.mode, args.until)
    sent = {"home_id": home_id, "mode": args.mode, "until": args.until}
    return _sent(args, response, sent, f"Home {home_id} set to {args.mode}{_until_text(args.until)}")


async def cmd_set_heating_curve(args: argparse.Namespace, client: MigoClient) -> int:
    response = await client.set_heating_curve(device_id=args.gateway_id, slope=args.slope)
    sent = {"gateway_id": args.gateway_id, "slope": args.slope}
    return _sent(args, response, sent, f"Gateway {args.gateway_id} heating curve set to {args.slope:g}")


async def cmd_set_hysteresis(args: argparse.Namespace, client: MigoClient) -> int:
    response = await client.set_hysteresis(device_id=args.gateway_id, hysteresis=args.hysteresis)
    sent = {"gateway_id": args.gateway_id, "hysteresis": args.hysteresis}
    return _sent(args, response, sent, f"Gateway {args.gateway_id} hysteresis set to {args.hysteresis:g}")


async def cmd_set_dhw(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    enabled = _on_off(args)
    response = await MigoHome(client, home_id).set_dhw_enabled(args.gateway_id, enabled)
    sent = {"home_id": home_id, "gateway_id": args.gateway_id, "enabled": enabled}
    return _sent(args, response, sent, f"Gateway {args.gateway_id} hot water turned {args.state}")


async def cmd_set_dhw_temperature(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    response = await MigoHome(client, home_id).set_dhw_temperature(args.gateway_id, args.temperature)
    sent = {"home_id": home_id, "gateway_id": args.gateway_id, "temperature": args.temperature}
    return _sent(args, response, sent, f"Gateway {args.gateway_id} hot water set to {args.temperature} C")


async def cmd_set_room_state(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    response = await MigoHome(client, home_id).set_room_state(args.room_id, args.mode, args.temperature, args.until)
    sent = {
        "home_id": home_id,
        "room_id": args.room_id,
        "mode": args.mode,
        "temperature": args.temperature,
        "until": args.until,
    }
    return _sent(args, response, sent, f"Room {args.room_id} state sent{_until_text(args.until)}")


async def cmd_set_temperature_offset(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    response = await MigoHome(client, home_id).set_temperature_offset(args.room_id, args.offset)
    sent = {"home_id": home_id, "room_id": args.room_id, "offset": args.offset}
    return _sent(args, response, sent, f"Room {args.room_id} offset set to {args.offset:g}")


async def cmd_set_control_mode(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    wire = "cooling" if args.mode == "dhw-only" else "heating"
    response = await MigoHome(client, home_id).set_temperature_control_mode(wire)
    sent = {"home_id": home_id, "mode": args.mode, "temperature_control_mode": wire}
    return _sent(args, response, sent, f"Home {home_id} control mode set to {args.mode}")


async def cmd_set_setpoint_duration(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    response = await MigoHome(client, home_id).set_manual_setpoint_duration(args.minutes)
    sent = {"home_id": home_id, "minutes": args.minutes}
    return _sent(args, response, sent, f"Home {home_id} manual setpoint duration set to {args.minutes} min")


async def cmd_set_anticipation(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    response = await MigoHome(client, home_id).set_anticipation(_on_off(args))
    sent = {"home_id": home_id, "enabled": _on_off(args)}
    return _sent(args, response, sent, f"Home {home_id} anticipation turned {args.state}")


async def cmd_switch_schedule(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    response = await MigoHome(client, home_id).switch_schedule(args.schedule_id)
    sent = {"home_id": home_id, "schedule_id": args.schedule_id}
    return _sent(args, response, sent, f"Home {home_id} switched to schedule {args.schedule_id}")


async def cmd_set_heating_type(args: argparse.Namespace, client: MigoClient) -> int:
    response = await client.set_heating_type(device_id=args.gateway_id, heating_type=args.heating_type)
    sent = {"gateway_id": args.gateway_id, "heating_type": args.heating_type}
    return _sent(args, response, sent, f"Gateway {args.gateway_id} heating type set to {args.heating_type}")


async def cmd_set_dhw_always_on(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    response = await MigoHome(client, home_id).set_dhw_always_on(args.gateway_id, _on_off(args))
    sent = {"home_id": home_id, "gateway_id": args.gateway_id, "enabled": _on_off(args)}
    return _sent(args, response, sent, f"Gateway {args.gateway_id} hot water always on turned {args.state}")


async def cmd_set_dhw_storage(args: argparse.Namespace, client: MigoClient) -> int:
    home_id = await _home_id(args, client)
    tank = args.storage == "water-tank"
    response = await client.set_dhw_storage(home_id, args.gateway_id, tank)
    sent = {"home_id": home_id, "gateway_id": args.gateway_id, "storage": args.storage}
    return _sent(args, response, sent, f"Gateway {args.gateway_id} hot water storage set to {args.storage}")


COMMANDS: dict[str, Command] = {
    "snapshot": cmd_snapshot,
    "status": cmd_status,
    "homes-data": cmd_homes_data,
    "home-status": cmd_home_status,
    "configs": cmd_configs,
    "measure": cmd_measure,
    "login": cmd_login,
    "set-temperature": cmd_set_temperature,
    "set-room-state": cmd_set_room_state,
    "set-temperature-offset": cmd_set_temperature_offset,
    "set-mode": cmd_set_mode,
    "set-control-mode": cmd_set_control_mode,
    "set-setpoint-duration": cmd_set_setpoint_duration,
    "set-anticipation": cmd_set_anticipation,
    "switch-schedule": cmd_switch_schedule,
    "set-heating-curve": cmd_set_heating_curve,
    "set-hysteresis": cmd_set_hysteresis,
    "set-heating-type": cmd_set_heating_type,
    "set-dhw": cmd_set_dhw,
    "set-dhw-temperature": cmd_set_dhw_temperature,
    "set-dhw-always-on": cmd_set_dhw_always_on,
    "set-dhw-storage": cmd_set_dhw_storage,
}


#: Commands that never change anything on the account. Every other command is a write.
#: Listing the reads rather than the writes makes a forgotten entry fail closed: a command
#: added to COMMANDS without being declared here asks for confirmation.
READ_COMMANDS = frozenset({"snapshot", "status", "homes-data", "home-status", "configs", "measure", "login"})


def needs_confirmation(command: str) -> bool:
    """Whether a command drives the heating and so must be confirmed first."""
    return command in COMMANDS and command not in READ_COMMANDS


def check(args: argparse.Namespace) -> str | None:
    """A combination of options argparse cannot express, as an error message."""
    if args.command == "set-room-state" and args.mode is None and args.temperature is None:
        return "set-room-state needs --mode, --temperature or both"
    if args.command == "set-mode" and args.until is not None and args.mode == "schedule":
        return "--until applies to the away and hg modes only"
    if args.command == "measure" and args.latest and args.types:
        return "--latest cannot be combined with --type"
    if args.command == "logout" and args.token_file is None:
        return "logout needs --token-file"
    if args.command == "measure" and None not in (args.date_begin, args.date_end) and args.date_begin >= args.date_end:
        return "--from must be before --to"
    return None


def describe(args: argparse.Namespace) -> str:
    """What a write is about to do, for the confirmation question."""
    until = _until_text(getattr(args, "until", None))
    match args.command:
        case "set-temperature":
            return f"set room {args.room_id} to {args.temperature:g} C"
        case "set-room-state":
            parts = [f"mode {args.mode}" if args.mode else "", f"{args.temperature:g} C" if args.temperature else ""]
            return f"set room {args.room_id} to {' and '.join(part for part in parts if part)}{until}"
        case "set-temperature-offset":
            return f"set the offset of room {args.room_id} to {args.offset:g}"
        case "set-mode":
            return f"set the home mode to {args.mode}{until}"
        case "set-control-mode":
            return f"set the control mode to {args.mode}"
        case "set-setpoint-duration":
            return f"set the manual setpoint duration to {args.minutes} min"
        case "set-anticipation":
            return f"turn anticipation {args.state}"
        case "switch-schedule":
            return f"switch to schedule {args.schedule_id}"
        case "set-heating-curve":
            return f"set the heating curve of {args.gateway_id} to {args.slope:g}"
        case "set-hysteresis":
            return f"set the hysteresis of {args.gateway_id} to {args.hysteresis:g}"
        case "set-heating-type":
            return f"set the heating type of {args.gateway_id} to {args.heating_type}"
        case "set-dhw":
            return f"turn hot water {args.state} on {args.gateway_id}"
        case "set-dhw-temperature":
            return f"set the hot water of {args.gateway_id} to {args.temperature} C"
        case "set-dhw-always-on":
            return f"turn hot water always on {args.state} on {args.gateway_id}"
        case "set-dhw-storage":
            return f"set the hot water storage of {args.gateway_id} to {args.storage}"
    raise ValueError(f"not a write command: {args.command}")
