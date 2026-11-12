"""Tolerant snapshot containers retaining unknown wire fields."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Self


@dataclass(frozen=True)
class JsonModel(Mapping[str, Any]):
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, value: object) -> Self:
        return cls(deepcopy(value) if isinstance(value, dict) else {})

    @property
    def id(self) -> str | None:
        value = self.raw.get("id")
        return value if isinstance(value, str) else None

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.raw)

    def __len__(self) -> int:
        return len(self.raw)


@dataclass(frozen=True)
class Home(JsonModel):
    """Home configuration retaining all unrecognised fields."""


@dataclass(frozen=True)
class Room(JsonModel):
    """Merged static and realtime room data."""


@dataclass(frozen=True)
class Module(JsonModel):
    """Merged module configuration, settings and realtime status."""


@dataclass(frozen=True)
class Consumption(JsonModel):
    """Latest valid daily runtime and energy reading."""


@dataclass(frozen=True)
class AccountSnapshot(Mapping[str, Any]):
    homes: dict[str, Home] = field(default_factory=dict)
    rooms: dict[str, Room] = field(default_factory=dict)
    devices: dict[str, Module] = field(default_factory=dict)
    consumption: dict[str, Consumption] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        if key not in {"homes", "rooms", "devices", "consumption"}:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(("homes", "rooms", "devices", "consumption"))

    def __len__(self) -> int:
        return 4

    @property
    def raw(self) -> dict[str, Any]:
        return {name: {key: deepcopy(value.raw) for key, value in self[name].items()} for name in self}
