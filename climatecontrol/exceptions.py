"""Exceptions used in climatecontrol."""


class SettingsValidationError(ValueError):
    """Failed to validate settings."""


class SettingsLoadError(ValueError):
    """Settings file is neither path nor content."""


class ContentLoadError(SettingsLoadError):
    """Contents could not be loaded."""


class FileLoadError(SettingsLoadError):
    """Contents could not be loaded."""


class NoCompatibleLoaderFoundError(SettingsLoadError):
    """Settings could not be loaded do to format or file being incompatible."""
