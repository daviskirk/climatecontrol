"""Logging utilities."""

import logging
import time
from logging import config as logging_config
from typing import Any

formatter: Any = logging.Formatter
formatter.converter = time.gmtime
logger: logging.Logger = logging.getLogger(__name__)


DEFAULT_LOG_SETTINGS = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s UTC [%(levelname)s] %(name)s: %(message)s"}
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "DEBUG",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}


__ALL__ = [DEFAULT_LOG_SETTINGS, logging, logger, logging_config]
