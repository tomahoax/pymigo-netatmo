"""Semantic values with an explicit unknown state."""

from enum import StrEnum


class ThermMode(StrEnum):
    SCHEDULE = "schedule"
    AWAY = "away"
    FROST_GUARD = "hg"
    MANUAL = "manual"
    HOME = "home"
    OFF = "off"
    MAX = "max"
    UNKNOWN = "unknown"


class BoilerMode(StrEnum):
    NORMAL = "normal"
    DHW_ONLY = "dhw_only"
    FROST_GUARD = "frost_guard"
    UNKNOWN = "unknown"


class HeatingAlgorithm(StrEnum):
    """Only the simple algorithm has a confirmed wire value (issue #44)."""

    SIMPLE = "simple_algo"
    UNKNOWN = "unknown"
