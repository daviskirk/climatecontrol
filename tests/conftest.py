"""Test settings."""
from collections import OrderedDict
import itertools
import sys
import os
import pytest
import json
from textwrap import dedent
import toml
import yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from climatecontrol import settings_parser  # noqa: E402


@pytest.fixture
def mock_os_environ(monkeypatch):
    """Mock os environment and set a few settings with environment variables."""
    mock_environ = OrderedDict([
        ('test_stuff', 2),
        ('TEST_STUFF', 5),
        ('TEST_STUFF_TESTGROUP__TEST_VAR', 6),
        ('TEST_STUFF_TESTGROUP__TESTVAR', 7),
        ('TEST_STUFFTESTGROUP__TESTVAR', 8),
        ('TEST_STUFF_TESTGROUP_TEST_VAR', 9),
    ])
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


@pytest.fixture(params=list(itertools.product(['.toml', '.yml', '.yaml', '.json'], [False, True])))
def file_extension(request, monkeypatch):
    """Fixture for providing file extension to use in settings files.

    This fixture is parametrized to mock out all "unneeded" modules to make
    sure that unneeded libraries do not need to be installed.

    """
    ext, mock_other = request.param
    if mock_other:
        if ext == '.toml':
            monkeypatch.setattr('climatecontrol.file_loaders.yaml', None)
        elif ext in {'.yml', '.yaml'}:
            monkeypatch.setattr('climatecontrol.file_loaders.toml', None)
        else:
            monkeypatch.setattr('climatecontrol.file_loaders.yaml', None)
            monkeypatch.setattr('climatecontrol.file_loaders.toml', None)
    return ext


@pytest.fixture
def mock_settings_file(request, monkeypatch, tmpdir, file_extension):
    """Temporarily write a settings file and return the filepath and the expected settings outcome."""
    ext = file_extension
    p = tmpdir.mkdir('sub').join('settings' + ext)

    expected_result = {
        'testgroup': {
            'testvar': 123
        }, 'othergroup': {
            'blabla': 555
        }
    }

    if ext == '.toml':
        p.write(toml.dumps(expected_result))
    elif ext in ['.yml', '.yaml']:
        p.write('---\n' + yaml.dump(expected_result))
    elif ext == '.json':
        p.write(json.dumps(expected_result))
    else:
        raise NotImplementedError('Invalid file extension :{}.'.format(ext))

    return str(p), expected_result


@pytest.fixture
def mock_settings_files(request, monkeypatch, tmpdir, mock_settings_file, file_extension):
    """Temporarily write multiple settings file and return the filepaths and the expected settings outcome."""
    subdir = tmpdir.mkdir('sub2')
    ext = file_extension

    # File to load in settings file by adding "from_file" to the variable we want.
    inline_path = subdir.join('secret.txt')
    inline_path.write('foo')

    if ext == '.toml':
        s1 = dedent("""\
        [testgroup]
        testvar = 123
        testvar_inline_1_from_file = "{}"

        [othergroup]
        blabla = 55
        testvar_inline_2_from_file = "{}"
        """.format(str(inline_path), str(inline_path)))

        s2 = dedent("""\

        [othergroup]
        blabla = 555
        testvar_inline_2 = "bar"
        """)
    elif ext in ('.yml', '.yaml'):
        s1 = dedent("""\
        testgroup:
          testvar: 123
          testvar_inline_1_from_file: {}

        othergroup:
          blabla: 55
          testvar_inline_2_from_file: {}
        """.format(str(inline_path), str(inline_path)))

        s2 = dedent("""\

        othergroup:
          blabla: 555
          testvar_inline_2: bar
        """)
    elif ext == '.json':
        s1 = dedent("""\
        {
            "testgroup": {"testvar": 123, "testvar_inline_1_from_file": "%s"},
            "othergroup": {"blabla": 55, "testvar_inline_2_from_file": "%s"}
        }
        """) % (str(inline_path), str(inline_path))

        s2 = dedent("""\
        {"othergroup": {"blabla": 555, "testvar_inline_2": "bar"}}
        """)
    else:
        raise NotImplementedError('Invalid file extension :{}.'.format(ext))
    p1 = subdir.join('settings' + ext)
    p1.write(s1)
    p2 = subdir.join('settings2' + ext)
    p2.write(s2)

    expected_result = {
        'testgroup': {
            'testvar': 123,
            'testvar_inline_1': 'foo'
        }, 'othergroup': {
            'blabla': 555,  # Overridden by file 2
            'testvar_inline_2': 'bar'  # Overridden by file 2
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
