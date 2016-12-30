#!/usr/bin/env python

"""
Test logging.
"""

import sys
import os
import logging
from contextlib import redirect_stderr
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from climatecontrol import logtools  # noqa: E402


def test_logging(monkeypatch, tmpdir):

    with io.StringIO() as buf, redirect_stderr(buf):
        # monkeypatch(settings_parser.Settings, )
        logger = logging.getLogger('test_logging_logger')
        logger.error('test before')
        logtools.setup_logging()
        logger.info('test after')
        logging_output = buf.getvalue()
        assert 'UTC [WARNING] climatecontrol.logtools: Custom log settings not found.  Using defaults.\n' in logging_output  # noqa: E501
        assert 'UTC [INFO] test_logging_logger: test after\n' in logging_output
