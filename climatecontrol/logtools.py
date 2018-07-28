"""Logging utilities."""

import logging
import logging.config as logging_config  # noqa: F401
import time
from typing import cast, Optional, Dict, Any  # noqa: F401

formatter = logging.Formatter  # type: Any
formatter.converter = time.gmtime
logger = logging.getLogger(__name__)  # type: logging.Logger


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
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console']
    }
}
