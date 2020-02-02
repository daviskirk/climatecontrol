"""CLIMATECONTROL controls your apps configuration environment.

It is a Python library for loading app configurations from files and/or
namespaced environment variables.

:licence: MIT, see LICENSE file for more details.

"""
from .exceptions import SettingsLoadError, SettingsValidationError
from .core import Climate

climate = Climate()
Settings = Climate  # for backwards compatibility

__all__ = [
    "climate",
    "Climate",
    "Settings",
    "SettingsValidationError",
    "SettingsLoadError",
]
