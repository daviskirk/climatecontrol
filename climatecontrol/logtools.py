#!/usr/bin/env python

"""
Logging utilities.
"""

import os
import logging
import logging.config as logging_config

from functools import wraps
from copy import deepcopy
import time
from typing import Optional


logging.Formatter.converter = time.gmtime
logger = logging.getLogger(__name__)  # type: logging.Logger


def log_exception(logger):
    def log_exception_decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                logger.exception(e)
                raise

        return wrapper
    return log_exception_decorator

DEFAULT_LOG_SETTINGS = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s UTC [%(levelname)s] %(name)s: %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': 'DEBUG'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'maxBytes': 104857600,
            'filename': 'athion.log',
            'backupCount': 3,
            'formatter': 'default',
            'level': 'DEBUG'
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ["console"]
    }
}


def setup_logging(settings_file: Optional[str] = None,
                  env_prefix: str = 'APP_SETTINGS',
                  settings_file_env_suffix: str = 'SETTINGS_FILE',
                  logging_section: str = 'LOGGING'):
    """

    args:
        settings_file: pass to `settings_parser.Settings`
        env_prefix: passed to `settings_parser.Settings`
        settings_file_env_suffix: passed to `settings_parser.Settings`
        logging_section: string indicating what section of the configuration should be used as logging settings.
    """

    from .settings_parser import Settings, update_nested

    using_custom = False

    def parse(data):
        """Parse logging configuration data"""
        default_settings = deepcopy(DEFAULT_LOG_SETTINGS)
        logging_settings = data.get(logging_section.lower(), {})
        nonlocal using_custom
        using_custom = bool(logging_settings)
        try:
            logging_filename = logging_settings['filename']
        except KeyError:
            logging_filename = None
        else:
            del logging_settings['filename']
        logging_settings = update_nested(default_settings, logging_settings)
        if logging_filename:
            logging_settings['handlers']['file']['filename'] = logging_filename
        return logging_settings

    logging_settings = Settings(settings_file=settings_file,
                                env_prefix=env_prefix,
                                settings_file_env_suffix=settings_file_env_suffix,
                                parser=parse)
    logging_config.dictConfig(logging_settings)

    if not using_custom:
        logger.warning('Custom log settings not found.  Using defaults.')
