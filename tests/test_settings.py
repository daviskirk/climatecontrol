#!/usr/bin/env python

"""
Test settings.
"""

import click
from click.testing import CliRunner
import sys
import os
import pytest
from collections.abc import Mapping
from unittest.mock import MagicMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from climatecontrol import settings_parser, cli_utils  # noqa: E402


def test_settings_empty(mock_empty_os_environ):
    settings_map = settings_parser.Settings()
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {}


@pytest.mark.parametrize('update_on_init', [False, True, None])
def test_settings(mock_os_environ, update_on_init):
    kwargs = {'prefix': 'TEST_STUFF'}
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
    settings_map = settings_parser.Settings(prefix='TEST_STUFF', parser=parser)
    assert parser.call_count == 1
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == expected


@pytest.mark.parametrize('settings_files', ['asd;kjhaflkjhasf', '.', '/home/', ['.', 'asd;kjhaflkjhasf']])
def test_settings_files_fail(mock_empty_os_environ, settings_files):
    with pytest.raises(settings_parser.SettingsFileError):
        settings_parser.Settings(prefix='TEST_STUFF',
                                 settings_files='asdlijasdlkjaa')


def test_settings_files_file(mock_empty_os_environ, mock_settings_file, tmpdir):
    settings_map = settings_parser.Settings(prefix='TEST_STUFF',
                                            settings_files=mock_settings_file[0])
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == mock_settings_file[1]


def test_settings_files_files(mock_empty_os_environ, mock_settings_files, tmpdir):
    settings_map = settings_parser.Settings(prefix='TEST_STUFF',
                                            settings_files=mock_settings_files[0])
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == mock_settings_files[1]


def test_settings_files_and_env_file(mock_os_environ, mock_settings_files, tmpdir):
    settings_map = settings_parser.Settings(
        prefix='TEST_STUFF',
        settings_files=mock_settings_files[0])
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {
        'testgroup': {
            'test_var': 6,
            'testvar': 123
        }, 'othergroup': {
            'blabla': 555
        }
    }


def test_settings_files_and_env_file_and_env(mock_env_settings_file, tmpdir):
    # os.environ['TEST_STUFF_SETTINGS_FILES'] = 'asdadad'
    settings_map = settings_parser.Settings(prefix='TEST_STUFF')
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {
        'testgroup': {
            'testvar': 123,
            'test_var': 6
        }, 'othergroup': {
            'blabla': 555
        }
    }


def mock_parser_fcn(s):
    return s


@pytest.mark.parametrize('attr, value, expected', [
    ('settings_files', 'this.toml', ['this.toml']),
    ('settings_files', ('this.toml', 'that.toml'), ['this.toml', 'that.toml']),
    ('parser', mock_parser_fcn, mock_parser_fcn)
])
def test_assign(mock_empty_os_environ, mock_env_parser, attr, value, expected):
    s = settings_parser.Settings(prefix='this', settings_file_suffix='suffix', parser=None)
    assert s.settings_files == []
    setattr(s, attr, value)
    assert getattr(s, attr) == expected


@pytest.mark.parametrize('mode', [
    'dict', 'envvar', 'both'
])
def test_update(mock_empty_os_environ, mode):
    """Test if updating settings after initialization works"""
    os.environ['THIS_SECTION_MY_VALUE'] = 'original'
    s = settings_parser.Settings(prefix='this', settings_file_suffix='suffix', parser=None)
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
    settings_map = settings_parser.Settings(prefix='MY_APP', filters=['section1', {'section2': '*'}])
    assert dict(settings_map) == {'subsection1': 'test1', 'subsection2': 'test2', 'subsection3': 'test3'}


@pytest.mark.parametrize('use_method', [True, False])
@pytest.mark.parametrize('option_name', ['config', 'settings'])
@pytest.mark.parametrize('mode', ['config', 'noconfig', 'wrongfile', 'noclick'])
def test_cli_utils1(mock_empty_os_environ, mock_settings_file, mode, option_name, use_method):
    settings_map = settings_parser.Settings(prefix='TEST_STUFF')
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
        args = ['--' + option_name, mock_settings_file[0]]
        result = runner.invoke(tmp_cli, args)
        assert dict(settings_map) == mock_settings_file[1]
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
