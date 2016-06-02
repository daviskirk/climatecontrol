#!/usr/bin/env python

"""
Test settings.
"""

import sys
import os
import pytest
from collections.abc import Mapping
from unittest.mock import MagicMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from climatecontrol import settings_parser


@pytest.fixture
def mock_os_environ(monkeypatch):
    mock_environ = {
        'test_stuff': 2,
        'TEST_STUFF': 5,
        'TEST_STUFF_TESTGROUP_TEST_VAR': 6,
        'TEST_STUFF_TESTGROUP_TESTVAR': 7,
        'TEST_STUFFTESTGROUP_TESTVAR': 8,
    }
    monkeypatch.setattr(os, 'environ', mock_environ)


@pytest.fixture
def mock_os_environ_toml(monkeypatch):
    mock_environ = {
        'TEST_STUFF_TESTGROUP_TEST_INT': '6',
        'TEST_STUFF_TESTGROUP_TEST_ARRAY': '[4, 5, 6]',
        'TEST_STUFF_TESTGROUP_TEST_RAW_STR': 'al//asdjk',
        'TEST_STUFF_TESTGROUP_TEST_STR': '"[4, 5, 6]"',
    }
    monkeypatch.setattr(os, 'environ', mock_environ)


@pytest.fixture
def mock_empty_os_environ(monkeypatch):
    mock_environ = {}
    monkeypatch.setattr(os, 'environ', mock_environ)


@pytest.fixture
def mock_settings_env_prefix(monkeypatch):
    monkeypatch.setattr(settings_parser.Settings, 'env_prefix', 'TEST_STUFF')


@pytest.fixture
def mock_settings_file(monkeypatch, tmpdir, mock_os_environ):
    p = tmpdir.mkdir('sub').join('settings.toml')
    s = """
    [testgroup]
    testvar = 123

    [othergroup]
    blabla = 555
    """
    p.write(s)
    return str(p)


@pytest.fixture
def mock_env_settings_file(mock_settings_file):
    os.environ['TEST_STUFF_SETTINGS_FILE'] = mock_settings_file
    return mock_settings_file


@pytest.mark.parametrize('env_prefix, max_depth, split_char, expected', [
    ('TEST_STUFF', 1, '_', {'testgroup': {'testvar': 7, 'test_var': 6}}),
    ('TEST_STUFF', 1, '-', {}),
    ('TEST_STUFF', 0, '_', {'testgroup_testvar': 7, 'testgroup_test_var': 6}),
    ('TEST_STUFF_', 1, '_', {'testgroup': {'testvar': 7, 'test_var': 6}}),
    ('TEST_STUFFING', 1, '_', {}),
])
def test_parse_environment_vars(mock_os_environ, env_prefix, max_depth, split_char, expected):
    result = settings_parser.parse_env_vars(
        env_prefix=env_prefix,
        max_depth=max_depth,
        split_char=split_char)
    assert result == expected


def test_settings_empty(mock_empty_os_environ):
    settings_map = settings_parser.Settings()
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {}


def test_settings(mock_os_environ):
    settings_map = settings_parser.Settings(env_prefix='TEST_STUFF')
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {'testgroup': {'testvar': 7, 'test_var': 6}}


def test_settings_parse(mock_os_environ):
    expected = {'bla': 'test'}
    parser = MagicMock()
    parser.return_value = expected
    settings_map = settings_parser.Settings(env_prefix='TEST_STUFF', parser=parser)
    assert parser.call_count == 1
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == expected


def test_settings_file_and_env_file(mock_settings_file, tmpdir):
    settings_map = settings_parser.Settings(
        env_prefix='TEST_STUFF',
        settings_file=mock_settings_file)
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {
        'testgroup': {
            'test_var': 6,
            'testvar': 123
        }, 'othergroup': {
            'blabla': 555
        }
    }


def test_settings_file_and_env_file_and_env(mock_env_settings_file, tmpdir):
    os.environ['TEST_STUFF_SETTINGS_FILE'] = 'asdadad'
    settings_map = settings_parser.Settings(
        env_prefix='TEST_STUFF',
        settings_file=mock_env_settings_file)
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {
        'testgroup': {
            'testvar': 123,
            'test_var': 6
        }, 'othergroup': {
            'blabla': 555
        }
    }


def test_parse_env_vars_toml(mock_os_environ_toml):
    result = settings_parser.parse_env_vars('TEST_STUFF', max_depth=1)
    expected = {
        'testgroup': {
            'test_int': 6,
            'test_array': [4, 5, 6],
            'test_raw_str': 'al//asdjk',
            'test_str': '[4, 5, 6]',
        }
    }
    assert result == expected

if __name__ == '__main__':
    sys.exit()
