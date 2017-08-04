"""Test settings."""

import sys
import os
import pytest
import json
import toml
import yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from climatecontrol import settings_parser  # noqa: E402


@pytest.fixture
def mock_os_environ(monkeypatch):
    """Mock os environment and set a few settings with environment variables."""
    mock_environ = {
        'test_stuff': 2,
        'TEST_STUFF': 5,
        'TEST_STUFF_TESTGROUP_TEST_VAR': 6,
        'TEST_STUFF_TESTGROUP_TESTVAR': 7,
        'TEST_STUFFTESTGROUP_TESTVAR': 8,
    }
    monkeypatch.setattr(os, 'environ', mock_environ)


@pytest.fixture
def mock_empty_os_environ(monkeypatch):
    """Mock os environment so it seems completely empty."""
    mock_environ = {}
    monkeypatch.setattr(os, 'environ', mock_environ)


@pytest.fixture
def mock_settings_prefix(monkeypatch):
    """Mock default settings prefix."""
    monkeypatch.setattr(settings_parser.Settings, 'prefix', 'TEST_STUFF')


@pytest.fixture(params=['.toml', '.yml', '.json'])
def mock_settings_file(request, monkeypatch, tmpdir):
    """Temporarily write a settings file and return the filepath and the expected settings outcome."""
    p = tmpdir.mkdir('sub').join('settings' + request.param)
    s = """
    [testgroup]
    testvar = 123

    [othergroup]
    blabla = 555
    """
    p.write(s)

    expected_result = {
        'testgroup': {
            'testvar': 123
        }, 'othergroup': {
            'blabla': 555
        }
    }

    if request.param == '.toml':
        p.write(toml.dumps(expected_result))
    elif request.param == '.yml':
        p.write('---\n' + yaml.dump(expected_result))
    elif request.param == '.json':
        p.write(json.dumps(expected_result))

    return str(p), expected_result


@pytest.fixture
def mock_settings_files(monkeypatch, tmpdir, mock_settings_file):
    """Temporarily write multiple settings file and return the filepaths and the expected settings outcome."""
    subdir = tmpdir.mkdir('sub2')
    p1 = subdir.join('settings.toml')
    s = """
    [testgroup]
    testvar = 123

    [othergroup]
    blabla = 55
    """
    p1.write(s)

    p2 = subdir.join('settings2.toml')
    s = """

    [othergroup]
    blabla = 555
    """
    p2.write(s)

    expected_result = {
        'testgroup': {
            'testvar': 123
        }, 'othergroup': {
            'blabla': 555
        }
    }
    return [str(p1), str(p2)], expected_result


@pytest.fixture
def mock_env_settings_file(mock_os_environ, mock_settings_file):
    """Set the settings file env variable to a temporary settings file."""
    os.environ['TEST_STUFF_SETTINGS_FILE'] = mock_settings_file[0]
    return mock_settings_file


@pytest.fixture
def mock_env_parser(mocker):
    """Mock out environment variable parser."""
    return mocker.patch('climatecontrol.settings_parser.EnvParser')
