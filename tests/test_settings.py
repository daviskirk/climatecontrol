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
from climatecontrol import settings_parser, cli_utils
import click
from click.testing import CliRunner


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
def mock_settings_file(monkeypatch, tmpdir):
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
def mock_env_settings_file(mock_os_environ, mock_settings_file):
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


@pytest.mark.parametrize('update_on_init', [False, True, None])
def test_settings(mock_os_environ, update_on_init):
    kwargs = {'env_prefix': 'TEST_STUFF'}
    if update_on_init is None:
        pass
    else:
        kwargs['update_on_init'] = update_on_init
    settings_map = settings_parser.Settings(**kwargs)
    assert isinstance(settings_map, Mapping)
    if update_on_init is False:
        expected = {}
    else:
        expected = {'testgroup': {'testvar': 7, 'test_var': 6}}
    assert dict(settings_map) == expected


def test_settings_parse(mock_os_environ):
    expected = {'bla': 'test'}
    parser = MagicMock()
    parser.return_value = expected
    settings_map = settings_parser.Settings(env_prefix='TEST_STUFF', parser=parser)
    assert parser.call_count == 1
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == expected


@pytest.mark.parametrize('settings_file', ['asd;kjhaflkjhasf', '.', '/home/'])
def test_settings_file_fail(mock_empty_os_environ, settings_file):
    settings_map = settings_parser.Settings(
        env_prefix='TEST_STUFF',
        settings_file='asdlijasdlkjaa')
    assert isinstance(settings_map, Mapping)
    assert settings_map == {}


def test_settings_file_file(mock_empty_os_environ, mock_settings_file, tmpdir):
    settings_map = settings_parser.Settings(
        env_prefix='TEST_STUFF',
        settings_file=mock_settings_file)
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {
        'testgroup': {
            'testvar': 123
        }, 'othergroup': {
            'blabla': 555
        }
    }

def test_settings_file_and_env_file(mock_os_environ, mock_settings_file, tmpdir):
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


def mock_parser_fcn(s):
    return s


@pytest.mark.parametrize('attr, value, expected', [
    ('env_prefix', 'that', 'THAT'),
    ('settings_file_env_suffix', 'suffix2', 'suffix2'),
    ('settings_file_env_var', 'wrongval', None),
    ('parser', mock_parser_fcn, mock_parser_fcn)
])
def test_assign(mock_empty_os_environ, attr, value, expected):
    s = settings_parser.Settings(env_prefix='this', settings_file_env_suffix='suffix', parser=None)
    assert s.env_prefix == 'THIS'
    assert s.settings_file_env_suffix == 'suffix'
    assert s.settings_file_env_var == 'THIS_SUFFIX'

    if attr == 'settings_file_env_var':
        with pytest.raises(AttributeError):
            setattr(s, attr, value)
    else:
        setattr(s, attr, value)
        assert getattr(s, attr) == expected
        if attr == 'settings_file_env_suffix':
            assert s.settings_file_env_var == 'THIS_' + expected.upper()


@pytest.mark.parametrize('mode', [
    'dict', 'envvar', 'both'
])
def test_update(mock_empty_os_environ, mode):
    """Test if updating settings after initialization works"""
    os.environ['THIS_SECTION_MY_VALUE'] = 'original'
    s = settings_parser.Settings(env_prefix='this', settings_file_env_suffix='suffix', parser=None)
    original = dict(s)
    assert original == {'section': {'my_value': 'original'}}

    expected = original.copy()
    if mode in ['dict', 'both']:
        update = {'section': {'my_new_value': 'value'}}
        expected['section'].update({'my_new_value': 'value'})
    else:
        update = None
    if mode in ['envvar', 'both']:
        os.environ['THIS_SECTION2_NEW_ENV_VALUE'] = 'new_env_data'
        expected.update({'section2': {'new_env_value': 'new_env_data'}})
    s.update(update)
    assert dict(s) == expected


def test_filters(mock_empty_os_environ):
    """test filter functionality based on docstring example"""
    os.environ.update(dict(
        MY_APP_SECTION1_SUBSECTION1='test1',
        MY_APP_SECTION2_SUBSECTION2='test2',
        MY_APP_SECTION2_SUBSECTION3='test3',
        MY_APP_SECTION3='not_captured',
    ))
    settings_map = settings_parser.Settings(env_prefix='MY_APP', filters=['section1', {'section2': '*'}])
    # assert dict(settings_map) == {'subsection1': 'test1'}, 'section2': {'subsection2': 'test2', 'subsection3': 'test3'}}


@pytest.mark.parametrize('use_method', [True, False])
@pytest.mark.parametrize('option_name', ['config', 'settings'])
@pytest.mark.parametrize('mode', ['config', 'noconfig', 'wrongfile', 'noclick'])
def test_cli_utils1(mock_empty_os_environ, mock_settings_file, mode, option_name, use_method):
    settings_map = settings_parser.Settings(
        env_prefix='TEST_STUFF')
    assert settings_map._data == {}

    if use_method:
        opt = cli_utils.click_settings_file_option(settings_map, option_name=option_name)
    else:
        opt = settings_map.click_settings_file_option(option_name=option_name)

    @click.command()
    @opt
    def tmp_cli():
        pass

    runner = CliRunner()
    if mode == 'config':
        args = ['--' + option_name, mock_settings_file]
        result = runner.invoke(tmp_cli, args)
        expected = {
            'testgroup': {
                'testvar': 123
            }, 'othergroup': {
                'blabla': 555
            }
        }
        assert dict(settings_map) == expected
        assert result.exit_code == 0
    elif mode == 'noconfig':
        args = []
        result = runner.invoke(tmp_cli, args)
        assert dict(settings_map) == {}
        assert result.exit_code == 0
    elif 'wrongfile':
        args = ['--' + option_name, 'badlfkjasfkj']
        result = runner.invoke(tmp_cli, args)
        assert result.exit_code == 2
        assert result.output == (
            'Usage: tmp_cli [OPTIONS]\n\n'
            'Error: Invalid value for "--{}": '
            'Path "badlfkjasfkj" does not exist.'
            '\n').format(option_name)
