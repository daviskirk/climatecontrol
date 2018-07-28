"""CLIMATECONTROL controls your apps configuration environment.

It is a Python library for loading app configurations from files and/or
namespaced environment variables.

:licence: MIT, see LICENSE file for more details.

"""

from .exceptions import SettingsLoadError, SettingsValidationError
from .settings_parser import Settings


__all__ = ['Settings', 'SettingsValidationError', 'SettingsLoadError']
