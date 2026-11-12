"""Public protocol constants."""

from typing import Final

from .limits import *  # noqa: F403
from .semantics import BoilerMode as BoilerMode
from .semantics import HeatingAlgorithm as HeatingAlgorithm
from .semantics import ThermMode as ThermMode
from .wire import *  # noqa: F403

VERSION: Final = "0.1.0"
