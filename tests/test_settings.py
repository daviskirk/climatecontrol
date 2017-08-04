"""Test settings."""

import click
from click.testing import CliRunner
import sys
import os
import pytest
from collections.abc import Mapping
from unittest.mock import MagicMock
import toml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from climatecontrol import settings_parser, cli_utils  # noqa: E402


def test_settings_empty(mock_empty_os_environ):
    """Check that initializing empty settings works correctly."""
    settings_map = settings_parser.Settings()
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {}
    assert str(settings_map)  # check that __repr__ works


@pytest.mark.parametrize('update_on_init', [False, True, None])
def test_settings(mock_os_environ, update_on_init):
    """Check that initializing settings works correctly."""
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
    """Check that parsing settings runs through without errors."""
    expected = {'bla': 'test'}
    parser = MagicMock()
    parser.return_value = expected
    settings_map = settings_parser.Settings(prefix='TEST_STUFF', parser=parser)
    assert parser.call_count == 1
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == expected


def test_parse_from_file_vars(mock_os_environ, tmpdir):
    """Check that the "from_file" extension works as expected.

    Adding the "from_file" suffix should result in the variable being read from
    the file and not directly.

    """
    settings_map = settings_parser.Settings(update_on_init=False)
    filepath = tmpdir.join('testvarfile')
    filename = str(filepath)
    with open(filename, 'w') as f:
        f.write('apassword\n')
    settings_map.update({'this_var_from_file': filename})
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {'this_var': 'apassword'}


@pytest.mark.parametrize('settings_files', ['asd;kjhaflkjhasf', '.', '/home/', ['.', 'asd;kjhaflkjhasf']])
def test_settings_files_fail(mock_empty_os_environ, settings_files):
    """Check that passing invalid settings files really results in errors."""
    with pytest.raises(settings_parser.SettingsFileError):
        settings_parser.Settings(prefix='TEST_STUFF',
                                 settings_files='asdlijasdlkjaa')


def test_yaml_import_fail(mock_empty_os_environ, monkeypatch):
    """Check that uninstalled yaml really results in an error."""
    # Check that without mocking everything is file:
    settings_parser.Settings(prefix='TEST_STUFF', settings_files='---\na: 5')
    # Now fake not having imported yaml
    monkeypatch.setattr('climatecontrol.settings_parser.yaml', None)
    with pytest.raises(ImportError):
        settings_parser.Settings(prefix='TEST_STUFF', settings_files='---\na: 5')


@pytest.mark.parametrize('settings_file_content', ['---\na:\n  b: 5\n', '{"a": {"b": 5}}', '[a]\nb=5'])
def test_settings_file_content(mock_empty_os_environ, settings_file_content):
    """Check parsing file content from different file types works."""
    settings_map = settings_parser.Settings(prefix='TEST_STUFF', settings_files=settings_file_content)
    assert dict(settings_map) == {'a': {'b': 5}}


@pytest.mark.parametrize('settings_file_content,error', [
    ('a:\n  b: 5\n', settings_parser.SettingsFileError),  # no file loader with "a" as valid start
    ('[{"a": {"b": 5}}]', toml.TomlDecodeError),  # json must be object, seeing "[" assumes a toml file
    ('b=5', settings_parser.SettingsFileError)  # toml file has to start with [ or it is not parsable
])
def test_settings_file_content_fail(mock_empty_os_environ, settings_file_content, error):
    """Check parsing file content from different file types raises an error on incorrect file content."""
    with pytest.raises(error):
        settings_parser.Settings(prefix='TEST_STUFF', settings_files=settings_file_content)


def test_settings_files_file(mock_empty_os_environ, mock_settings_file, tmpdir):
    """Check that setting a the "settings_files" option works correctly."""
    settings_map = settings_parser.Settings(prefix='TEST_STUFF',
                                            settings_files=mock_settings_file[0])
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == mock_settings_file[1]


def test_settings_files_files(mock_empty_os_environ, mock_settings_files, tmpdir):
    """Check that setting multiple files as "settings_files" option works correctly."""
    settings_map = settings_parser.Settings(prefix='TEST_STUFF',
                                            settings_files=mock_settings_files[0])
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == mock_settings_files[1]


def test_settings_files_and_env_file(mock_os_environ, mock_settings_files, tmpdir):
    """Check that using a settings file together with settings parsed from env variables works."""
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
    """Check that a settings file from an env variable works together with other env variables settings."""
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


@pytest.mark.parametrize('order, expected', [
    (None, {'testgroup': {'testvar': 'external'}}),
    (('env', 'env_file', 'files', 'external'), {'testgroup': {'testvar': 'external'}}),
    (('env', 'env_file', 'external', 'files'), {'testgroup': {'testvar': 'file'}}),
    (('env', 'external', 'files', 'env_file'), {'testgroup': {'testvar': 'env_file'}}),
    (('external', 'env_file', 'files', 'env'), {'testgroup': {'testvar': 'env'}})
])
def test_settings_parsing_order(tmpdir, order, expected):
    """Check that parsing order can be changed."""
    os.environ['TEST_STUFF_TESTGROUP_TESTVAR'] = 'env'
    os.environ['TEST_STUFF_SETTINGS_FILE'] = '[testgroup]\ntestvar = "env_file"'
    subdir = tmpdir.mkdir('order_subdir')
    p = subdir.join('settings.toml')
    p.write('[testgroup]\ntestvar = "file"')
    settings_map = settings_parser.Settings(prefix='TEST_STUFF',
                                            parse_order=order,
                                            settings_files=[str(p)],
                                            update_on_init=False)
    settings_map.update({'testgroup': {'testvar': 'external'}})
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == expected


def mock_parser_fcn(s):
    """Return input instead of doing some complex parsing."""
    return s


@pytest.mark.parametrize('attr, value, expected', [
    ('settings_files', 'this.toml', ['this.toml']),
    ('settings_files', ('this.toml', 'that.toml'), ['this.toml', 'that.toml']),
    ('parser', mock_parser_fcn, mock_parser_fcn)
])
def test_assign(mock_empty_os_environ, mock_env_parser, attr, value, expected):
    """Test that assigning attributes on settings object works."""
    s = settings_parser.Settings(prefix='this', settings_file_suffix='suffix', parser=None)
    assert s.settings_files == []
    setattr(s, attr, value)
    assert getattr(s, attr) == expected


@pytest.mark.parametrize('mode', [
    'dict', 'envvar', 'both'
])
def test_update(mock_empty_os_environ, mode):
    """Test if updating settings after initialization works."""
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
    """Test filter functionality based on docstring example."""
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
def test_cli_utils(mock_empty_os_environ, mock_settings_file, mode, option_name, use_method):
    """Check that cli utils work."""
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
            'Error: Invalid value for "--{}" / "-{}": '
            'Path "badlfkjasfkj" does not exist.'
            '\n').format(option_name, option_name[0])


def test_get_configuration_file(mock_empty_os_environ, mock_settings_file, tmpdir):
    """Test writing out an example configuration file."""
    settings_file_path, expected = mock_settings_file
    settings_map = settings_parser.Settings(prefix='TEST_STUFF',
                                            settings_files=settings_file_path)
    s = settings_map.get_configuration_file()
    expected = mock_settings_file[1]
    assert toml.loads(s) == expected

    subdir = tmpdir.mkdir('config_write_subdir')
    p = subdir.join('example_settings.toml')
    s = settings_map.get_configuration_file(str(p))

    assert toml.load(str(p)) == expected
