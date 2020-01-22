"""Test settings."""

import os
import sys

import pytest

from climatecontrol.env_parser import EnvParser  # noqa: I100
from climatecontrol.fragment import Fragment


@pytest.mark.parametrize(
    "attr, value, expected",
    [
        ("prefix", "that", "THAT_"),
        ("settings_file_suffix", "suffix2", "suffix2"),
        ("settings_file_env_var", "wrongval", None),
    ],
)
def test_envparser_assign(mock_empty_os_environ, attr, value, expected):
    """Check that we can assign attributes of env parser."""
    s = EnvParser(prefix="this", settings_file_suffix="suffix")
    assert s.prefix == "THIS_"
    assert s.settings_file_suffix == "suffix"
    assert s.settings_file_env_var == "THIS_SUFFIX"

    if attr == "settings_file_env_var":
        with pytest.raises(AttributeError):
            setattr(s, attr, value)
    else:
        setattr(s, attr, value)
        assert getattr(s, attr) == expected
        if attr == "settings_file_suffix":
            assert s.settings_file_env_var == "THIS_" + expected.upper()


@pytest.mark.parametrize(
    "prefix, implicit_depth, split_char, expected_kws",
    [
        (
            "TEST_STUFF",
            1,
            "_",
            [
                dict(
                    value=6,
                    source="ENV:TEST_STUFF_TESTGROUP__TEST_VAR",
                    path=["testgroup", "test_var"],
                ),
                dict(
                    value=7,
                    source="ENV:TEST_STUFF_TESTGROUP__TESTVAR",
                    path=["testgroup", "testvar"],
                ),
                dict(
                    value=9,
                    source="ENV:TEST_STUFF_TESTGROUP_TEST_VAR",
                    path=["testgroup", "test_var"],
                ),
            ],
        ),
        ("TEST_STUFF", 1, "-", []),
        (
            "TEST_STUFF",
            0,
            "_",
            [
                dict(
                    value=6,
                    source="ENV:TEST_STUFF_TESTGROUP__TEST_VAR",
                    path=["testgroup", "test_var"],
                ),
                dict(
                    value=7,
                    source="ENV:TEST_STUFF_TESTGROUP__TESTVAR",
                    path=["testgroup", "testvar"],
                ),
                dict(
                    value=9,
                    source="ENV:TEST_STUFF_TESTGROUP_TEST_VAR",
                    path=["testgroup_test_var"],
                ),
            ],
        ),
        (
            "TEST_STUFF_",
            1,
            "_",
            [
                dict(
                    value=6,
                    source="ENV:TEST_STUFF_TESTGROUP__TEST_VAR",
                    path=["testgroup", "test_var"],
                ),
                dict(
                    value=7,
                    source="ENV:TEST_STUFF_TESTGROUP__TESTVAR",
                    path=["testgroup", "testvar"],
                ),
                dict(
                    value=9,
                    source="ENV:TEST_STUFF_TESTGROUP_TEST_VAR",
                    path=["testgroup", "test_var"],
                ),
            ],
        ),
        ("TEST_STUFFING", 1, "_", []),
    ],
)
def test_envparser_args_iter_load(
    mock_os_environ, prefix, implicit_depth, split_char, expected_kws
):
    """Check that we can parse settings from variables."""
    env_parser = EnvParser(
        prefix=prefix, split_char=split_char, implicit_depth=implicit_depth
    )
    expected = [Fragment(**kw) for kw in expected_kws]
    results = list(env_parser.iter_load())
    assert results == expected


@pytest.mark.parametrize(
    "environ, expected_kw",
    [
        pytest.param(
            {
                "TEST_STUFF_TESTGROUP__TEST_INT": "6",
                "TEST_STUFF_TESTGROUP__TEST_ARRAY": "[4, 5, 6]",
                "TEST_STUFF_TESTGROUP__TEST_RAW_STR": "al//asdjk",
                "TEST_STUFF_TESTGROUP__TEST_STR": '"[4, 5, 6]"',
                "TEST_STUFF_TESTGROUP__TEST_COMPLEX_RAW_STR": "amqp://guest:guest@127.0.0.1:5672//",
            },
            [
                {
                    "value": 6,
                    "source": "ENV:TEST_STUFF_TESTGROUP__TEST_INT",
                    "path": ["testgroup", "test_int"],
                },
                {
                    "value": [4, 5, 6],
                    "source": "ENV:TEST_STUFF_TESTGROUP__TEST_ARRAY",
                    "path": ["testgroup", "test_array"],
                },
                {
                    "value": "al//asdjk",
                    "source": "ENV:TEST_STUFF_TESTGROUP__TEST_RAW_STR",
                    "path": ["testgroup", "test_raw_str"],
                },  # noqa: E501
                {
                    "value": "[4, 5, 6]",
                    "source": "ENV:TEST_STUFF_TESTGROUP__TEST_STR",
                    "path": ["testgroup", "test_str"],
                },
                {
                    "value": "amqp://guest:guest@127.0.0.1:5672//",
                    "source": "ENV:TEST_STUFF_TESTGROUP__TEST_COMPLEX_RAW_STR",
                    "path": ["testgroup", "test_complex_raw_str"],
                },  # noqa: E501
            ],
            id="json value",
        ),
        pytest.param(
            {"TEST_STUFF_TESTLIST__5": "v1"},
            [
                {
                    "value": "v1",
                    "source": "ENV:TEST_STUFF_TESTLIST__5",
                    "path": ["testlist", 5],
                }
            ],
            id="list index variable",
        ),
        pytest.param(
            {"TEST_STUFF_TESTLIST__1__TEST": "v1"},
            [
                {
                    "value": "v1",
                    "source": "ENV:TEST_STUFF_TESTLIST__1__TEST",
                    "path": ["testlist", 1, "test"],
                }
            ],
            id="list index with dict variable",
        ),
    ],
)
def test_env_parser_iter_load(monkeypatch, environ, expected_kw):
    """Check that iter_load correctly interprets environment variables and their values."""
    monkeypatch.setattr(os, "environ", environ)
    env_parser = EnvParser(prefix="TEST_STUFF")
    expected = [Fragment(**kw) for kw in expected_kw]
    result = list(env_parser.iter_load())
    if sys.version_info[:2] >= (3, 6):  # pragma: nocover
        assert result == expected
    else:  # pragma: nocover
        # python 3.5 doesn't order dicts so we can't test the exact order
        def to_set(fragments):
            return set(str(f) for f in fragments)

        assert to_set(result) == to_set(expected)
