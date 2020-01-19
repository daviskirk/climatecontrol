"""Test settings."""

import json
import os
import sys
from collections.abc import Mapping
from unittest.mock import MagicMock

import click
import pytest
import toml
from click.testing import CliRunner

from climatecontrol import cli_utils, settings_parser  # noqa: E402
from climatecontrol.exceptions import NoCompatibleLoaderFoundError
from climatecontrol.fragment import Fragment


def test_settings_empty(mock_empty_os_environ):
    """Check that initializing empty settings works correctly."""
    settings_map = settings_parser.Settings()
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {}
    assert str(settings_map)  # check that __repr__ works
    assert len(settings_map) == 0  # length of settings map


@pytest.mark.parametrize("update_on_init", [False, True, None])
def test_settings(mock_os_environ, update_on_init):
    """Check that initializing settings works correctly."""
    kwargs = {"prefix": "TEST_STUFF"}
    if update_on_init is None:
        pass
    else:
        kwargs["update_on_init"] = update_on_init
    settings_map = settings_parser.Settings(**kwargs)
    assert isinstance(settings_map, Mapping)
    expected = {"testgroup": {"testvar": 7, "test_var": 6}, "testgroup_test_var": 9}
    assert dict(settings_map) == expected


def test_settings_parse(mock_os_environ):
    """Check that parsing settings runs through without errors."""
    expected = {"bla": "test"}
    parser = MagicMock()
    parser.return_value = expected
    settings_map = settings_parser.Settings(prefix="TEST_STUFF", parser=parser)
    assert (
        parser.call_count == 0
    ), "Before accessing settings, the parser should not have been called"
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == expected
    assert (
        parser.call_count == 1
    ), "After accessing settings, the parser should have been called"


@pytest.mark.parametrize("original", [False, True])
@pytest.mark.parametrize("file_exists", [False, True])
def test_parse_from_file_vars(original, file_exists, mock_os_environ, tmpdir):
    """Check that the "from_file" extension works as expected.

    Adding the "from_file" suffix should result in the variable being read from
    the file and not directly.

    """
    settings_map = settings_parser.Settings()
    filepath = tmpdir.join("testvarfile")
    filename = str(filepath)
    if file_exists:
        with open(filename, "w") as f:
            f.write("apassword\n")
    update_dict = {"this_var_from_file": filename}
    if original:
        update_dict["this_var"] = "the original password"
    settings_map.update(update_dict)
    assert isinstance(settings_map, Mapping)
    actual = dict(settings_map)
    expected = {}
    if original:
        expected = {"this_var": "the original password"}
    if file_exists:
        expected = {"this_var": "apassword"}
    assert actual == expected


@pytest.mark.parametrize(
    "settings_update, var_content, expected",
    [
        ({"test_var_from_env": "MY_VAR"}, "apassword", {"test_var": "apassword"}),
        (
            {"a": {"test_var_from_env": "MY_VAR"}},
            '{"b": "apassword"}',
            {"a": {"test_var": {"b": "apassword"}}},
        ),
        (
            {"a": [0, {"test_var_from_env": "MY_VAR", "test_var2_from_env": "MY_VAR"}]},
            "1",
            {"a": [0, {"test_var": 1, "test_var2": 1}]},
        ),
        ({"test_var_from_env": "MY_WRONG_VAR", "b": 3}, "never seen", {"b": 3}),
    ],
)
def test_parse_from_env_vars(mock_os_environ, settings_update, var_content, expected):
    """Test replacing environment variables in settings."""
    settings_map = settings_parser.Settings(update_on_init=False)
    os.environ["MY_VAR"] = var_content
    settings_map.update(settings_update)
    actual = dict(settings_map)
    assert actual == expected


@pytest.mark.parametrize(
    "settings_files", ["asd;kjhaflkjhasf", ".", "/home/", [".", "asd;kjhaflkjhasf"]]
)
def test_settings_files_fail(mock_empty_os_environ, settings_files):
    """Check that passing invalid settings files really results in errors."""
    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=settings_files
    )
    with pytest.raises(NoCompatibleLoaderFoundError):
        settings_map.update()


@pytest.mark.parametrize(
    "file_str, mock_module",
    [
        ("---\na: 5", "climatecontrol.file_loaders.yaml"),
        ("[section]\na = 5", "climatecontrol.file_loaders.toml"),
    ],
)
def test_file_loader_module_import_fail(
    mock_empty_os_environ, monkeypatch, file_str, mock_module
):
    """Check that uninstalled yaml or toml really results in an error."""
    # Check that without mocking everything is file:
    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=[file_str]
    )
    settings_map.update()
    # Now fake not having imported yaml
    monkeypatch.setattr(mock_module, None)
    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=[file_str]
    )
    with pytest.raises(ImportError):
        settings_map.update()


@pytest.mark.parametrize(
    "settings_file_content",
    ["---\na:\n  b: 5\n", '{"a": {"b": 5}}', "[a]\nb=5"],  # yaml  # json  # toml
)
def test_settings_file_content(mock_empty_os_environ, settings_file_content):
    """Check parsing file content from different file types works."""
    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=settings_file_content
    )
    assert dict(settings_map) == {"a": {"b": 5}}


@pytest.mark.parametrize(
    "settings_file_content,error",
    [
        (
            "a:\n  b: 5\n",
            NoCompatibleLoaderFoundError,
        ),  # no file loader with "a" as valid start
        (
            '[{"a": {"b": 5}}]',
            toml.TomlDecodeError,
        ),  # json must be object, seeing "[" assumes a toml file
        (
            "b=5",
            NoCompatibleLoaderFoundError,
        ),  # toml file has to start with [ or it is not parsable
    ],
)
def test_settings_file_content_fail(
    mock_empty_os_environ, settings_file_content, error
):
    """Check parsing file content from different file types raises an error on incorrect file content."""
    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=settings_file_content
    )
    with pytest.raises(error):
        settings_map.update()


def test_settings_single_file(mock_empty_os_environ, mock_settings_file, tmpdir):
    """Check that setting a the "settings_files" option works correctly."""
    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=mock_settings_file[0]
    )
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == mock_settings_file[1]


def test_settings_multiple_files(mock_empty_os_environ, mock_settings_files, tmpdir):
    """Check that setting multiple files as "settings_files" option works correctly."""
    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=mock_settings_files[0]
    )
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == mock_settings_files[1]


def test_settings_multiple_files_with_glob(
    mock_empty_os_environ, mock_settings_files, tmpdir, file_extension
):
    """Check that setting multiple files as "settings_files" option works correctly."""
    directory, _ = os.path.split(mock_settings_files[0][0])
    glob_path = directory + os.path.sep + "*" + file_extension
    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=glob_path
    )
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == mock_settings_files[1]


def test_settings_env_file_and_env(mock_env_settings_file, tmpdir):
    """Check that a settings file from an env variable works together with other env variables settings.

    In the default case environment vars should override settings file vars.
    """
    settings_map = settings_parser.Settings(prefix="TEST_STUFF")
    assert isinstance(settings_map, Mapping)
    assert dict(settings_map) == {
        "testgroup": {"testvar": 7, "test_var": 6},
        "othergroup": {"blabla": 555},
        "testgroup_test_var": 9,
    }


def test_settings_multiple_files_and_env(mock_os_environ, mock_settings_files, tmpdir):
    """Check that using multiple settings files together with settings parsed from env variables works.

    Each subsequent settings file should override the last and environment vars
    should override any settings file vars.

    Additionally check that the logs are fired correctly and have the correct
    result.

    """
    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=mock_settings_files[0]
    )
    assert isinstance(settings_map, Mapping)

    assert dict(settings_map) == {
        "testgroup": {"test_var": 6, "testvar": 7, "testvar_inline_1": "foo"},
        "othergroup": {"blabla": 555, "testvar_inline_2": "bar"},
        "testgroup_test_var": 9,
    }

    expected_fragments = [
        Fragment(
            value={
                "testgroup": {
                    "testvar": 123,
                    "testvar_inline_1_from_file": str(tmpdir / "sub2" / "secret.txt"),
                },
                "othergroup": {
                    "blabla": 55,
                    "testvar_inline_2_from_file": str(tmpdir / "sub2" / "secret.txt"),
                },
            },
            source=mock_settings_files[0][0],
            path=[],
        ),
        Fragment(
            value=settings_parser.REMOVED,
            source=mock_settings_files[0][0],
            path=["testgroup", "testvar_inline_1_from_file"],
        ),
        Fragment(
            value="foo",
            source=mock_settings_files[0][0],
            path=["testgroup", "testvar_inline_1"],
        ),
        Fragment(
            value=settings_parser.REMOVED,
            source=mock_settings_files[0][0],
            path=["othergroup", "testvar_inline_2_from_file"],
        ),
        Fragment(
            value="foo",
            source=mock_settings_files[0][0],
            path=["othergroup", "testvar_inline_2"],
        ),
        Fragment(
            value={"othergroup": {"blabla": 555, "testvar_inline_2": "bar"}},
            source=mock_settings_files[0][1],
        ),
        Fragment(
            value=6,
            source="ENV:TEST_STUFF_TESTGROUP__TEST_VAR",
            path=["testgroup", "test_var"],
        ),
        Fragment(
            value=7,
            source="ENV:TEST_STUFF_TESTGROUP__TESTVAR",
            path=["testgroup", "testvar"],
        ),
        Fragment(
            value=9,
            source="ENV:TEST_STUFF_TESTGROUP_TEST_VAR",
            path=["testgroup_test_var"],
        ),
        Fragment(value={}, source="external"),
    ]

    assert len(settings_map.fragments) == len(expected_fragments)
    if sys.version_info[:2] >= (3, 6):
        # in python < 3.6 dicts are not ordered so we can't be sure what's up here in python 3.5
        assert settings_map.fragments == expected_fragments


@pytest.mark.parametrize(
    "ending, content",
    [
        (".json", '["this", "that"]\n'),
        (".yml", "[this, that]\n"),
        pytest.param(
            ".toml",
            "['this', 'that']",
            marks=pytest.mark.xfail(reason="toml literal lists are not supported"),
        ),
    ],
)
def test_parse_from_file_list(ending, content, mock_os_environ, tmpdir):
    """Check that the "from_file" extension works as expected.

    Adding the "from_file" suffix should result in the variable being read from
    the file and not directly. In addition, a file ending indicating a
    structured format (like json, toml or yaml) should allow the user to read
    structures from files (in this case simple lists).

    Note that the toml parser can not (as of 2018-11) interpret top level lists
    as such, so specifying a toml file holding only a list will not work as
    expected.

    """
    settings_map = settings_parser.Settings(update_on_init=False)
    filepath = tmpdir.join("testvarfile" + ending)
    filename = str(filepath)
    with open(filename, "w") as f:
        f.write(content)
    update_dict = {"this_var_from_file": filename}
    settings_map.update(update_dict)
    assert isinstance(settings_map, Mapping)
    actual = dict(settings_map)
    expected = {"this_var": ["this", "that"]}
    assert actual == expected


def test_nested_settings_files(tmpdir):
    """Check that parsing of nested "from_file" settings files works as expected.

    In this case a base file references as settings file (nested_1) which in
    turn references as second file (nested_2).

    """
    subfolder = tmpdir.mkdir("sub")
    p = subfolder.join("settings.json")
    nested_1_p = subfolder.join("nested_1.json")
    nested_2_p = subfolder.join("nested_2.json")

    nested_2_p.write(json.dumps({"foo": 1, "bar": 2}))
    nested_1_p.write(json.dumps({"level_2_from_file": str(nested_2_p)}))
    p.write(
        json.dumps(
            {
                "level_1_from_file": str(
                    nested_1_p
                ),  # nested_1_p references nested_2_p internally.
                "spam": "parrot",
                "list": [
                    "random",
                    {
                        "this_from_file": str(
                            nested_2_p
                        )  # dictionaries in lists should be expanded as well.
                    },
                ],
            }
        )
    )

    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=[str(p)]
    )
    assert dict(settings_map) == {
        "spam": "parrot",
        "level_1": {"level_2": {"foo": 1, "bar": 2}},
        "list": ["random", {"this": {"foo": 1, "bar": 2}}],
    }


def test_multiple_settings_files(tmpdir):
    """Check that parsing multiple files on after another works as expected.

    We assume a settings file list with multiple files and expect the files to
    be parsed in that order, the latter file overwriting the settings of
    earlier files.

    """
    subfolder = tmpdir.mkdir("sub")
    p1 = subfolder.join("settings1.json")
    p1.write(json.dumps({"foo": "test1"}))

    p2 = subfolder.join("settings2.json")
    content = subfolder.join("content.txt")
    content.write("test2")
    p2.write(json.dumps({"foo_from_file": str(content)}))

    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=[str(p1), str(p2)]
    )
    assert dict(settings_map) == {"foo": "test2"}

    p3 = subfolder.join("settings3.json")
    p3.write(json.dumps({"foo": "test3"}))

    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=[str(p1), str(p2), str(p3)]
    )
    assert dict(settings_map) == {"foo": "test3"}


def mock_parser_fcn(s):
    """Return input instead of doing some complex parsing."""
    return s


@pytest.mark.parametrize(
    "attr, value, expected",
    [
        ("settings_files", "this.toml", ["this.toml"]),
        ("settings_files", ("this.toml", "that.toml"), ["this.toml", "that.toml"]),
        ("parser", mock_parser_fcn, mock_parser_fcn),
    ],
)
def test_assign(mock_empty_os_environ, mock_env_parser, attr, value, expected):
    """Test that assigning attributes on settings object works."""
    s = settings_parser.Settings(
        prefix="this", settings_file_suffix="suffix", parser=None
    )
    assert s.settings_files == []
    setattr(s, attr, value)
    assert getattr(s, attr) == expected


@pytest.mark.parametrize("mode", ["dict", "envvar", "both"])
def test_update(mock_empty_os_environ, mode):
    """Test if updating settings after initialization works."""
    os.environ["THIS_SECTION__MY_VALUE"] = "original"
    s = settings_parser.Settings(
        prefix="this", settings_file_suffix="suffix", parser=None
    )
    original = dict(s)
    assert original == {"section": {"my_value": "original"}}

    expected = original.copy()
    if mode in ["dict", "both"]:
        update = {"section": {"my_new_value": "value"}}
        expected["section"].update({"my_new_value": "value"})
    else:
        update = None
    if mode in ["envvar", "both"]:
        os.environ["THIS_SECTION2__NEW_ENV_VALUE"] = "new_env_data"
        expected.update({"section2": {"new_env_value": "new_env_data"}})
    s.update(update)
    assert dict(s) == expected


def test_bad_config_recovery():
    """Check that parsers that cause errors can recover correctly."""

    def check(d):
        if d and "wrong" in d:
            raise KeyError("Invalid config")
        return d

    s = settings_parser.Settings(
        prefix="this", settings_file_suffix="suffix", parser=check
    )
    assert dict(s) == {}

    # Try to set incorrect config
    with pytest.raises(KeyError):
        s.update({"wrong": 2})
    assert dict(s) == {}, "Setting should not have been updated"
    assert dict(s.update_data) == {}, "No external data should have been set."

    # Updating with other fields will still trigger the error
    s.update({"right": 2})
    assert dict(s) == {"right": 2}
    assert dict(s.update_data) == {"right": 2}, "External data should have been set."


def test_temporary_changes():
    """Test that temporary changes settings context manager works.

    Within the context, settings should be changeable. After exit, the original
    settings should be restored.

    """
    s = settings_parser.Settings()
    s.update({"a": 1})
    with s.temporary_changes():
        # Change the settings within the context
        s.update({"a": 2, "b": 2})
        s.settings_files.append("test")
        assert s["a"] == 2
        assert len(s.settings_files) == 1
    # Check that outside of the context the settings are back to their old state.
    assert s["a"] == 1
    assert len(s.settings_files) == 0


@pytest.mark.parametrize("use_method", [True, False])
@pytest.mark.parametrize("option_name", ["config", "settings"])
@pytest.mark.parametrize("mode", ["config", "noconfig", "wrongfile", "noclick"])
def test_cli_utils(
    mock_empty_os_environ, mock_settings_file, mode, option_name, use_method
):
    """Check that cli utils work."""
    settings_map = settings_parser.Settings(prefix="TEST_STUFF")
    assert settings_map._data == {}

    if use_method:
        opt = cli_utils.click_settings_file_option(
            settings_map, option_name=option_name
        )
    else:
        opt = settings_map.click_settings_file_option(option_name=option_name)

    @click.command()
    @opt
    def tmp_cli():
        pass

    runner = CliRunner()
    if mode == "config":
        args = ["--" + option_name, mock_settings_file[0]]
        result = runner.invoke(tmp_cli, args)
        assert dict(settings_map) == mock_settings_file[1]
        assert result.exit_code == 0
    elif mode == "noconfig":
        args = []
        result = runner.invoke(tmp_cli, args)
        assert dict(settings_map) == {}
        assert result.exit_code == 0
    elif "wrongfile":
        args = ["--" + option_name, "badlfkjasfkj"]
        result = runner.invoke(tmp_cli, args)
        assert result.exit_code == 2
        expected_output = (
            "Usage: tmp-cli [OPTIONS]\n"
            'Try "tmp-cli --help" for help.\n\n'
            'Error: Invalid value for "--{}" / "-{}": '
            'File "badlfkjasfkj" does not exist.'
            "\n"
        ).format(option_name, option_name[0])
        assert result.output == expected_output


def test_to_config(mock_empty_os_environ, mock_settings_file, tmpdir, file_extension):
    """Test writing out an example configuration file."""
    settings_file_path, expected = mock_settings_file
    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=settings_file_path
    )
    s = settings_map.to_config(style=file_extension)
    if file_extension == ".toml":
        expected = mock_settings_file[1]
        assert toml.loads(s) == expected
    else:
        assert s

    subdir = tmpdir.mkdir("config_write_subdir")
    p = subdir.join("example_settings" + file_extension)
    s = settings_map.to_config(save_to=str(p))

    if file_extension == ".toml":
        assert toml.load(str(p)) == expected
    else:
        assert p.read()


@pytest.mark.parametrize("update", [False, "manual", "env"])
def test_setup_logging(monkeypatch, update, mock_empty_os_environ):
    """Check that the setup_logging method intializes the logger and respects updates."""
    mock_dict_config = MagicMock()
    monkeypatch.setattr(
        "climatecontrol.settings_parser.logging_config.dictConfig", mock_dict_config
    )
    if update == "env":
        os.environ["TEST_STUFF_LOGGING__ROOT__LEVEL"] = "DEBUG"
    settings_map = settings_parser.Settings(prefix="TEST_STUFF")
    if update == "manual":
        settings_map.update({"logging": {"root": {"level": "DEBUG"}}})
    settings_map.update()
    settings_map.setup_logging()
    assert mock_dict_config.call_count == 1
    assert (
        "handlers" in mock_dict_config.call_args[0][0]["root"]
    ), "Expected default logging configuration to be updated, not overwritten."
    assert (
        mock_dict_config.call_args[0][0]["root"]["level"] == "DEBUG"
        if update
        else "INFO"
    )


def test_update_log(caplog, mock_empty_os_environ, mock_settings_file):
    """Test writing out an example configuration file."""
    settings_file_path, expected = mock_settings_file
    settings_map = settings_parser.Settings(
        prefix="TEST_STUFF", settings_files=settings_file_path
    )
    assert (
        settings_map.update_log == ""
    ), "before updating, the update log should be empty"
    settings_map.update({"a": settings_parser.REMOVED, "b": 2})
    lines = settings_map.update_log.split("\n")
    assert len(lines) == 4
    expected_lines = [
        "loaded testgroup.testvar from {}".format(settings_file_path),
        "loaded othergroup.blabla from {}".format(settings_file_path),
        "removed a from external",
        "loaded b from external",
    ]
    assert set(lines) == set(expected_lines), "Unexpected lines in update_log"
