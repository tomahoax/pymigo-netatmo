"""Pure API interpretation helpers."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from ..const import (
    BOILER_MODE_DHW_ONLY,
    BOILER_MODE_FROST_GUARD,
    BOILER_MODE_NORMAL,
    MODE_FROST_GUARD,
    SCHEDULE_TYPE_EVENT,
    SCHEDULE_TYPE_THERM,
)

MINUTES_PER_WEEK = 7 * 24 * 60
_LOGGER = logging.getLogger(__name__)


def safe_float(value: Any, default: float | None = None) -> float | None:
    """Safely convert a value to float.

    Args:
        value: The value to convert.
        default: The default value if conversion fails.

    Returns:
        The float value or the default.
    """
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        _LOGGER.debug("Failed to convert %r to float", value)
        return default


def derive_boiler_mode(
    therm_mode: str | None,
    room_setpoint_modes: Iterable[str | None],
) -> str:
    """Derive the home-level boiler quick-action mode.

    MiGo's "Actions rapides" (Normal / DHW only / Frost guard) are not
    returned as a single field by homesdata/homestatus. They can be derived
    from the home's `therm_mode` and the rooms' `therm_setpoint_mode`:
    frost guard is `therm_mode == "hg"`; DHW-only shows up as a room in
    `therm_setpoint_mode == "hg"` while the home itself is not; anything
    else is normal heating. This is independent of the Away preset
    (`therm_mode == "away"`), which is an orthogonal setting.

    Args:
        therm_mode: The home's `therm_mode` field.
        room_setpoint_modes: The `therm_setpoint_mode` of each room in the home.

    Returns:
        One of BOILER_MODE_NORMAL, BOILER_MODE_DHW_ONLY, BOILER_MODE_FROST_GUARD.
    """
    if therm_mode == MODE_FROST_GUARD:
        return BOILER_MODE_FROST_GUARD
    if MODE_FROST_GUARD in room_setpoint_modes:
        return BOILER_MODE_DHW_ONLY
    return BOILER_MODE_NORMAL


def current_week_minutes(now: datetime | None = None) -> int:
    """Return minutes elapsed since Monday 00:00 in the local timezone.

    Args:
        now: Optional reference time, mainly for tests. Defaults to the
            current local time in Home Assistant's configured timezone.

    Returns:
        Minutes since Monday 00:00:00, in the range [0, 10080).
    """
    if now is None:
        now = datetime.now().astimezone()
    return now.weekday() * 1440 + now.hour * 60 + now.minute


def resolve_timetable_zone(
    timetable: list[dict[str, Any]],
    week_minutes: int,
) -> int | None:
    """Resolve the active zone_id for a timetable at a given point in the week.

    The API does not guarantee `timetable` is sorted by `m_offset`, so this
    sorts it first. Picks the last entry whose offset is not in the future,
    wrapping around to the last entry of the week when `week_minutes`
    precedes the first offset (e.g. early Monday morning, before the first
    slot of the week starts).

    Args:
        timetable: List of {"zone_id": int, "m_offset": int} entries.
        week_minutes: Minutes since Monday 00:00 to resolve against. Values
            outside [0, MINUTES_PER_WEEK) are wrapped rather than trusted
            as-is - currently only `current_week_minutes()` calls this, which
            always returns an in-range value, but nothing else in this
            function's contract enforces that for a future caller.

    Returns:
        The zone_id of the active entry, or None if the timetable is empty.
    """
    if not timetable:
        return None

    week_minutes %= MINUTES_PER_WEEK

    sorted_entries = sorted(timetable, key=lambda entry: entry.get("m_offset", 0))

    active = None
    for entry in sorted_entries:
        if entry.get("m_offset", 0) <= week_minutes:
            active = entry
        else:
            break

    if active is None:
        # week_minutes precedes the first offset of the week: the active
        # slot is whichever one started last, i.e. the last entry.
        active = sorted_entries[-1]

    return active.get("zone_id")


def _linked_event_schedule_id(linked_schedules: Any, therm_schedule_id: str) -> str | None:
    """Best-effort lookup of the event schedule id linked to a therm schedule id.

    The exact shape of `linked_schedules` in the homesdata response is not
    documented by Netatmo. This defensively handles the shapes plausible for
    an id-pairing structure: a mapping of {id: id} (either direction), or a
    list of pairs (as a dict of arbitrary key names, or a 2-tuple/list).

    Args:
        linked_schedules: The raw `linked_schedules` value from a home.
        therm_schedule_id: The id of the selected therm schedule.

    Returns:
        The paired event schedule id, or None if it cannot be resolved.
    """
    # IDs are strings throughout this API - the explicit str() calls below
    # just prove that to mypy for a value that arrived as Any, not change
    # behavior for the real, always-string-keyed data this handles.
    if isinstance(linked_schedules, dict):
        if therm_schedule_id in linked_schedules:
            return str(linked_schedules[therm_schedule_id])
        for key, value in linked_schedules.items():
            if value == therm_schedule_id:
                return str(key)
        return None

    if isinstance(linked_schedules, list):
        for entry in linked_schedules:
            ids: list[Any] = []
            if isinstance(entry, dict):
                ids = list(entry.values())
            elif isinstance(entry, (list, tuple)):
                ids = list(entry)
            if therm_schedule_id in ids:
                others = [i for i in ids if i != therm_schedule_id]
                if others:
                    return str(others[0])

    return None


def get_event_schedule(home: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return the DHW (event) schedule paired with the active heating schedule.

    Prefers the explicit `linked_schedules` pairing when present and
    resolvable, falling back to the event schedule that is independently
    marked `selected` (the app selects a therm and an event schedule in
    parallel, under the same name).

    Args:
        home: A home configuration dict (as stored in coordinator.homes).

    Returns:
        The event schedule dict, or None if none can be resolved.
    """
    schedules: list[dict[str, Any]] = home.get("schedules", [])
    therm_schedules = [s for s in schedules if s.get("type") == SCHEDULE_TYPE_THERM]
    event_schedules = [s for s in schedules if s.get("type") == SCHEDULE_TYPE_EVENT]

    selected_therm = next((s for s in therm_schedules if s.get("selected")), None)
    linked_schedules = home.get("linked_schedules")

    selected_therm_id = selected_therm.get("id") if selected_therm is not None else None
    if selected_therm_id is not None and linked_schedules:
        linked_id = _linked_event_schedule_id(linked_schedules, selected_therm_id)
        if linked_id is not None:
            for schedule in event_schedules:
                if schedule.get("id") == linked_id:
                    return schedule

    # Fallback: the event schedule independently marked selected.
    return next((s for s in event_schedules if s.get("selected")), None)
