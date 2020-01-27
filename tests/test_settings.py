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
    climate = settings_parser.Climate()
    assert isinstance(climate.settings, Mapping)
    assert dict(climate.settings) == {}
    assert str(climate)  # check that __repr__ works
    assert str(climate.settings)  # check that __repr__ works
    assert len(climate.settings) == 0  # length of settings map


@pytest.mark.parametrize("update_on_init", [False, True, None])
def test_settings(mock_os_environ, update_on_init):
    """Check that initializing settings works correctly."""
    kwargs = {"prefix": "TEST_STUFF"}
    if update_on_init is None:
        pass
    else:
        kwargs["update_on_init"] = update_on_init
    climate = settings_parser.Climate(**kwargs)
    assert isinstance(climate.settings, Mapping)
    expected = {"testgroup": {"testvar": 7, "test_var": 6}, "testgroup_test_var": 9}
    assert dict(climate.settings) == expected


def test_settings_parse(mock_os_environ):
    """Check that parsing settings runs through without errors."""
    expected = {"bla": "test"}
    parser = MagicMock()
    parser.return_value = expected
    climate = settings_parser.Climate(prefix="TEST_STUFF", parser=parser)
    assert (
        parser.call_count == 0
    ), "Before accessing settings, the parser should not have been called"
    assert isinstance(climate.settings, Mapping)
    assert dict(climate.settings) == expected
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
    climate = settings_parser.Climate()
    filepath = tmpdir.join("testvarfile")
    filename = str(filepath)
    if file_exists:
        with open(filename, "w") as f:
            f.write("apassword\n")
    update_dict = {"this_var_from_file": filename}
    if original:
        update_dict["this_var"] = "the original password"
    climate.update(update_dict)
    assert isinstance(climate.settings, Mapping)
    actual = dict(climate.settings)
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
    climate = settings_parser.Climate(update_on_init=False)
    os.environ["MY_VAR"] = var_content
    climate.update(settings_update)
    actual = dict(climate.settings)
    assert actual == expected


@pytest.mark.parametrize(
    "settings_files", ["asd;kjhaflkjhasf", ".", "/home/", [".", "asd;kjhaflkjhasf"]]
)
def test_settings_files_fail(mock_empty_os_environ, settings_files):
    """Check that passing invalid settings files really results in errors."""
    climate = settings_parser.Climate(
        prefix="TEST_STUFF", settings_files=settings_files
    )
    with pytest.raises(NoCompatibleLoaderFoundError):
        climate.update()


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
    climate = settings_parser.Climate(prefix="TEST_STUFF", settings_files=[file_str])
    climate.update()
    # Now fake not having imported yaml
    monkeypatch.setattr(mock_module, None)
    climate = settings_parser.Climate(prefix="TEST_STUFF", settings_files=[file_str])
    with pytest.raises(ImportError):
        climate.update()


@pytest.mark.parametrize(
    "settings_file_content",
    ["---\na:\n  b: 5\n", '{"a": {"b": 5}}', "[a]\nb=5"],  # yaml  # json  # toml
)
def test_settings_file_content(mock_empty_os_environ, settings_file_content):
    """Check parsing file content from different file types works."""
    climate = settings_parser.Climate(
        prefix="TEST_STUFF", settings_files=settings_file_content
    )
    assert dict(climate.settings) == {"a": {"b": 5}}


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
    climate = settings_parser.Climate(
        prefix="TEST_STUFF", settings_files=settings_file_content
    )
    with pytest.raises(error):
        climate.update()


def test_settings_single_file(mock_empty_os_environ, mock_settings_file, tmpdir):
    """Check that setting a the "settings_files" option works correctly."""
    climate = settings_parser.Climate(
        prefix="TEST_STUFF", settings_files=mock_settings_file[0]
    )
    assert isinstance(climate.settings, Mapping)
    assert dict(climate.settings) == mock_settings_file[1]


def test_settings_multiple_files(mock_empty_os_environ, mock_settings_files, tmpdir):
    """Check that setting multiple files as "settings_files" option works correctly."""
    climate = settings_parser.Climate(
        prefix="TEST_STUFF", settings_files=mock_settings_files[0]
    )
    assert isinstance(climate.settings, Mapping)
    assert dict(climate.settings) == mock_settings_files[1]


def test_settings_multiple_files_with_glob(
    mock_empty_os_environ, mock_settings_files, tmpdir, file_extension
):
    """Check that setting multiple files as "settings_files" option works correctly."""
    directory, _ = os.path.split(mock_settings_files[0][0])
    glob_path = directory + os.path.sep + "*" + file_extension
    climate = settings_parser.Climate(prefix="TEST_STUFF", settings_files=glob_path)
    assert isinstance(climate.settings, Mapping)
    assert dict(climate.settings) == mock_settings_files[1]


def test_settings_env_file_and_env(mock_env_settings_file, tmpdir):
    """Check that a settings file from an env variable works together with other env variables settings.

    In the default case environment vars should override settings file vars.
    """
    climate = settings_parser.Climate(prefix="TEST_STUFF")
    assert isinstance(climate.settings, Mapping)
    assert dict(climate.settings) == {
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
    climate = settings_parser.Climate(
        prefix="TEST_STUFF", settings_files=mock_settings_files[0]
    )
    assert isinstance(climate.settings, Mapping)

    assert dict(climate.settings) == {
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
    ]

    assert len(climate._fragments) == len(expected_fragments)
    if sys.version_info[:2] >= (3, 6):  # pragma: nocover
        # in python < 3.6 dicts are not ordered so we can't be sure what's up here in python 3.5
        assert climate._fragments == expected_fragments


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
    climate = settings_parser.Climate(update_on_init=False)
    filepath = tmpdir.join("testvarfile" + ending)
    filename = str(filepath)
    with open(filename, "w") as f:
        f.write(content)
    update_dict = {"this_var_from_file": filename}
    climate.update(update_dict)
    assert isinstance(climate.settings, Mapping)
    actual = dict(climate.settings)
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

    climate = settings_parser.Climate(prefix="TEST_STUFF", settings_files=[str(p)])
    assert dict(climate.settings) == {
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

    climate = settings_parser.Climate(
        prefix="TEST_STUFF", settings_files=[str(p1), str(p2)]
    )
    assert dict(climate.settings) == {"foo": "test2"}

    p3 = subfolder.join("settings3.json")
    p3.write(json.dumps({"foo": "test3"}))

    climate = settings_parser.Climate(
        prefix="TEST_STUFF", settings_files=[str(p1), str(p2), str(p3)]
    )
    assert dict(climate.settings) == {"foo": "test3"}


def mock_parser_fcn(s):
    """Return input instead of doing some complex parsing."""


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
    s = settings_parser.Climate(
        prefix="this", settings_file_suffix="suffix", parser=None
    )
    assert s.settings_files == []
    setattr(s, attr, value)
    assert getattr(s, attr) == expected


@pytest.mark.parametrize("update", [False, True])
@pytest.mark.parametrize("envvar", [False, True])
@pytest.mark.parametrize("clear", [False, True])
@pytest.mark.parametrize("reload", [False, True])
def test_update_clear_reload(mock_empty_os_environ, update, envvar, clear, reload):
    """Test if updating settings after initialization works."""
    os.environ["THIS_SECTION__MY_VALUE"] = "original"
    climate = settings_parser.Climate(
        prefix="this", settings_file_suffix="suffix", parser=None
    )
    original = dict(climate.settings)
    assert original == {"section": {"my_value": "original"}}

    expected = original.copy()
    if update:
        climate.update({"section": {"my_new_value": "value"}})
        if not clear:
            expected["section"].update({"my_new_value": "value"})
    if envvar:
        os.environ["THIS_SECTION2__NEW_ENV_VALUE"] = "new_env_data"
        if reload or clear:
            expected.update({"section2": {"new_env_value": "new_env_data"}})
    if clear:
        climate.clear()
    if reload:
        climate.reload()
    assert dict(climate.settings) == expected


def test_bad_config_recovery(mock_empty_os_environ):
    """Check that parsers that cause errors can recover correctly."""

    def check(d):
        if d and "wrong" in d:
            raise KeyError("Invalid config")
        return d

    climate = settings_parser.Climate(
        prefix="this", settings_file_suffix="suffix", parser=check
    )
    assert dict(climate.settings) == {}

    # Try to set incorrect config
    with pytest.raises(KeyError):
        climate.update({"wrong": 2})
    assert dict(climate.settings) == {}, "Setting should not have been updated"
    assert climate._updates == [], "No external data should have been set."

    # Updating with other fields will still trigger the error
    climate.update({"right": 2})
    assert dict(climate.settings) == {"right": 2}
    assert climate._updates == [{"right": 2}], "External data should have been set."


def test_temporary_changes():
    """Test that temporary changes settings context manager works.

    Within the context, settings should be changeable. After exit, the original
    settings should be restored.

    """
    climate = settings_parser.Climate()
    climate.update({"a": 1})
    with climate.temporary_changes():
        # Change the settings within the context
        climate.update({"a": 2, "b": 2})
        climate.settings_files.append("test")
        assert climate.settings["a"] == 2
        assert len(climate.settings_files) == 1
    # Check that outside of the context the settings are back to their old state.
    assert climate.settings["a"] == 1
    assert len(climate.settings_files) == 0


@pytest.mark.parametrize("use_method", [True, False])
@pytest.mark.parametrize("option_name", ["config", "settings"])
@pytest.mark.parametrize("mode", ["config", "noconfig", "wrongfile", "noclick"])
def test_cli_utils(
    mock_empty_os_environ, mock_settings_file, mode, option_name, use_method
):
    """Check that cli utils work."""
    climate = settings_parser.Climate(prefix="TEST_STUFF")
    # test equality here as _data is not only NoneType but also a proxy so "is" comparison would alwas evaluate to false.
    assert isinstance(climate._data, type(None))

    if use_method:
        opt = cli_utils.click_settings_file_option(climate, option_name=option_name)
    else:
        opt = climate.click_settings_file_option(option_name=option_name)

    @click.command()
    @opt
    def tmp_cli():
        pass

    runner = CliRunner()
    if mode == "config":
        args = ["--" + option_name, mock_settings_file[0]]
        result = runner.invoke(tmp_cli, args)
        assert dict(climate.settings) == mock_settings_file[1]
        assert result.exit_code == 0
    elif mode == "noconfig":
        args = []
        result = runner.invoke(tmp_cli, args)
        assert dict(climate.settings) == {}
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


def test_settings_items(mock_empty_os_environ):
    """Test that item selection, assignment and deletion work as expected."""
    climate = settings_parser.Climate()
    climate.update({"a": {"b": {"c": [1, 2, 3]}}, "d": [{"e": "f"}, {"g": "h"}]})
    assert climate.settings["a"] == {"b": {"c": [1, 2, 3]}}
    assert climate.settings.a == {"b": {"c": [1, 2, 3]}}
    assert climate.settings.a.b.c[0] == 1

    # test assignment
    for value in [{"new": "data"}, "blaaa", [3, 4, 5]]:
        with pytest.raises(TypeError):
            climate.settings.a.b.c = value
        climate.update({"a": {"b": {"c": value}}})
        assert climate.settings.a.b.c == value

    for value in [{"new": "data"}, "blaaa", 100]:
        with pytest.raises(TypeError):
            climate.settings.a.b.c[0] = value
        climate.update({"a": {"b": {"c": [value]}}})
        assert climate.settings.a.b.c[0] == value

    # test deletion
    with pytest.raises(TypeError):
        del climate.settings.a.b["c"]
    climate.update({"a": {"b": {"c": settings_parser.REMOVED}}})
    assert climate.settings.a.b == {}
    climate.update()
    assert climate.settings.a.b == {}

    # test attribute deletion
    with pytest.raises(TypeError):
        del climate.settings.d[0].e
    climate.update({"d": [{"e": settings_parser.REMOVED}]})
    assert climate.settings.d == [{}, {"g": "h"}]
    climate.update()
    assert climate.settings.d == [{}, {"g": "h"}]

    # test sequence item deletion
    climate.update({"d": [settings_parser.REMOVED]})
    assert climate.settings.d == [{"g": "h"}]
    climate.update()
    assert climate.settings.d == [{"g": "h"}]

    # test second deletion at index to make sure that it is applied after the previous deletion
    climate.update({"d": [settings_parser.REMOVED]})
    assert climate.settings.d == []
    climate.update()
    assert climate.settings.d == []


@pytest.mark.parametrize("update", [False, "manual", "env"])
def test_setup_logging(monkeypatch, update, mock_empty_os_environ):
    """Check that the setup_logging method intializes the logger and respects updates."""
    mock_dict_config = MagicMock()
    monkeypatch.setattr(
        "climatecontrol.settings_parser.logging_config.dictConfig", mock_dict_config
    )
    if update == "env":
        os.environ["TEST_STUFF_LOGGING__ROOT__LEVEL"] = "DEBUG"
    climate = settings_parser.Climate(prefix="TEST_STUFF")
    if update == "manual":
        climate.update({"logging": {"root": {"level": "DEBUG"}}})
    climate.update()
    climate.setup_logging()
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
    climate = settings_parser.Climate(
        prefix="TEST_STUFF", settings_files=settings_file_path
    )
    assert climate.update_log == "", "before updating, the update log should be empty"
    climate.update({"a": settings_parser.REMOVED, "b": 2})
    lines = climate.update_log.split("\n")
    assert len(lines) == 4
    expected_lines = [
        "loaded testgroup.testvar from {}".format(settings_file_path),
        "loaded othergroup.blabla from {}".format(settings_file_path),
        "removed a from external",
        "loaded b from external",
    ]
    assert set(lines) == set(expected_lines), "Unexpected lines in update_log"
