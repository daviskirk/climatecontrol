"""CLIMATECONTROL controls your apps configuration environment.

It is a Python library for loading app configurations from files and/or
namespaced environment variables.

:licence: MIT, see LICENSE file for more details.

"""
from .core import Climate
from .exceptions import SettingsLoadError, SettingsValidationError

climate = Climate()
Settings = Climate  # for backwards compatibility

__all__ = [
    "climate",
    "Climate",
    "Settings",
    "SettingsValidationError",
    "SettingsLoadError",
]
