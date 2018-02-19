"""Test settings."""

import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from climatecontrol import settings_parser  # noqa: E402


@pytest.mark.parametrize('attr, value, expected', [
    ('prefix', 'that', 'THAT_'),
    ('settings_file_suffix', 'suffix2', 'suffix2'),
    ('settings_file_env_var', 'wrongval', None),
])
def test_env_parser_assign(mock_empty_os_environ, attr, value, expected):
    """Check that we can assign attributes of env parser."""
    s = settings_parser.EnvParser(prefix='this', settings_file_suffix='suffix')
    assert s.prefix == 'THIS_'
    assert s.settings_file_suffix == 'suffix'
    assert s.settings_file_env_var == 'THIS_SUFFIX'

    if attr == 'settings_file_env_var':
        with pytest.raises(AttributeError):
            setattr(s, attr, value)
    else:
        setattr(s, attr, value)
        assert getattr(s, attr) == expected
        if attr == 'settings_file_suffix':
            assert s.settings_file_env_var == 'THIS_' + expected.upper()


@pytest.mark.parametrize('implicit_depth_arg', ['max_depth', 'implicit_depth'])
@pytest.mark.parametrize('prefix, implicit_depth, split_char, expected', [
    ('TEST_STUFF', 1, '_', {'testgroup': {'testvar': 7, 'test_var': 9}}),
    ('TEST_STUFF', 1, '-', {}),
    ('TEST_STUFF', 0, '_', {'testgroup': {'testvar': 7, 'test_var': 6}, 'testgroup_test_var': 9}),
    ('TEST_STUFF_', 1, '_', {'testgroup': {'testvar': 7, 'test_var': 9}}),
    ('TEST_STUFFING', 1, '_', {}),
])
def test_parse_environment_vars(mock_os_environ, prefix, implicit_depth_arg, implicit_depth, split_char, expected):
    """Check that we can parse settings from variables."""
    implicit_depth_kwarg = {implicit_depth_arg: implicit_depth}
    env_parser = settings_parser.EnvParser(
        prefix=prefix,
        split_char=split_char,
        **implicit_depth_kwarg)
    result = env_parser.parse()
    assert result == expected


@pytest.mark.parametrize('implicit_depth, environ, expected', [
    (
        1,
        {
            'TEST_STUFF_TESTGROUP_TEST_INT': '6',
            'TEST_STUFF_TESTGROUP_TEST_ARRAY': '[4, 5, 6]',
            'TEST_STUFF_TESTGROUP_TEST_RAW_STR': 'al//asdjk',
            'TEST_STUFF_TESTGROUP_TEST_STR': '"[4, 5, 6]"',
            'TEST_STUFF_TESTGROUP_TEST_AMQP': 'amqp://guest:guest@127.0.0.1:5672//'
        },
        {
            'testgroup': {
                'test_int': 6,
                'test_array': [4, 5, 6],
                'test_raw_str': 'al//asdjk',
                'test_str': '[4, 5, 6]',
                'test_amqp': 'amqp://guest:guest@127.0.0.1:5672//',
            }
        }
    ),
    (
        2,
        {
            'TEST_STUFF_TESTGROUP_TEST_INT': '6',
            'TEST_STUFF_TESTGROUP_TEST_ARRAY': '[4, 5, 6]',
            'TEST_STUFF_TESTGROUP_TEST_RAW_STR': 'al//asdjk',
            'TEST_STUFF_TESTGROUP_TEST_STR': '"[4, 5, 6]"',
            'TEST_STUFF_TESTGROUP_TEST_AMQP': 'amqp://guest:guest@127.0.0.1:5672//'
        },
        {
            'testgroup': {
                'test': {
                    'int': 6,
                    'array': [4, 5, 6],
                    'raw_str': 'al//asdjk',
                    'str': '[4, 5, 6]',
                    'amqp': 'amqp://guest:guest@127.0.0.1:5672//',
                }
            }
        }
    ),
    (
        -1,
        {
            'TEST_STUFF_TESTGROUP__TEST_INT': '6',
            'TEST_STUFF_TESTGROUP__TEST_ARRAY': '[4, 5, 6]',
            'TEST_STUFF_TESTGROUP__TEST_RAW_STR': 'al//asdjk',
            'TEST_STUFF_TESTGROUP__TEST_STR': '"[4, 5, 6]"',
            'TEST_STUFF_TESTGROUP__TEST_AMQP': 'amqp://guest:guest@127.0.0.1:5672//'
        },
        {
            'testgroup': {
                'test_int': 6,
                'test_array': [4, 5, 6],
                'test_raw_str': 'al//asdjk',
                'test_str': '[4, 5, 6]',
                'test_amqp': 'amqp://guest:guest@127.0.0.1:5672//',
            }
        }
    ),

])
def test_parse_toml(monkeypatch, implicit_depth, environ, expected):
    """Check that we can parse toml from environment variables."""
    monkeypatch.setattr(os, 'environ', environ)
    env_parser = settings_parser.EnvParser(prefix='TEST_STUFF', implicit_depth=implicit_depth)
    result = env_parser.parse()
    assert result == expected
