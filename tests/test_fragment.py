"""Tests for fragments."""

import sys

import pytest

from climatecontrol.fragment import EMPTY, Fragment, FragmentPath, merge_nested


def test_fragment_path():
    """Test fragment path construction."""
    assert not FragmentPath()  # empty path is falsy
    assert FragmentPath([]) == FragmentPath(), "empty fragment paths should be equal"
    assert FragmentPath(["a", "stuff", 1]) == FragmentPath(
        ["a", "stuff", 1]
    ), "Unexpected equality result"
    assert FragmentPath(["a", "stuff", 1]) != FragmentPath(
        ["a", "wrong", 1]
    ), "Unexpected inequality result"
    assert list(FragmentPath(["a", "stuff", 1])) == [
        "a",
        "stuff",
        1,
    ], "Unexpected list conversion result"
    assert (
        str(FragmentPath(["a", "stuff", 1])) == "FragmentPath(['a', 'stuff', 1])"
    ), "Unexpected string representation"
    assert FragmentPath(["a", "stuff", 1])[1] == "stuff", "unexpected indexing"


@pytest.mark.parametrize(
    "path, expected",
    [
        (["a"], {"a": "test"}),
        (["a", "stuff", 1, "bla"], {"a": {"stuff": [EMPTY, {"bla": "test"}]}}),
        ([2, "a"], [EMPTY, EMPTY, {"a": "test"}]),
        ([2, 1], [EMPTY, EMPTY, [EMPTY, "test"]]),
    ],
)
def test_fragment_path_expand(path, expected):
    """Test expansion of fragment path."""
    assert FragmentPath(path).expand("test") == expected


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (["a"], ["b"], []),
        ([], [], []),
        ([1, 2, 3], [1, 2, 4, 5], [1, 2]),
        (["a", "b", "c"], ["a", "b"], ["a", "b"]),
        (["a", "b", "c"], ["a", "b", "d"], ["a", "b"]),
        (["a", "b", "c"], ["wrong", "b", "c"], []),
    ],
)
def test_fragment_path_common(a, b, expected):
    """Test common path."""
    assert FragmentPath(a).common(b) == FragmentPath(expected)


def test_fragment():
    """Test fragment constructor and representation."""
    fragment = Fragment(value="bla", source="test", path=["a", "b"])
    assert fragment
    assert (
        str(fragment)
        == "Fragment(value='bla', source='test', path=FragmentPath(['a', 'b']))"
    ), "unexpected string representation"


def test_fragment_equality():
    """Test fragment equality."""
    assert Fragment(value="bla", source="test", path=["a", "b"]) == Fragment(
        value="bla", source="test", path=["a", "b"]
    )
    assert Fragment(value="bla") == Fragment(value="bla")
    assert Fragment(value="bla") != Fragment(value="blub")
    assert Fragment(value="bla", source="a") != Fragment(value="bla", source="b")
    assert Fragment(value="bla", path=["a"]) != Fragment(value="bla", path=["b"])


def test_fragment_clone():
    """Test the fragments clone method."""
    fragment = Fragment("bla")
    assert fragment.clone() == fragment
    assert fragment.clone() is not fragment
    cloned = fragment.clone(source=["a"])
    assert cloned != fragment
    assert cloned == Fragment("bla", source=["a"])


def test_fragment_iter_leaves():
    """Test that iterating over fragment leaves gives expected result."""
    fragment = Fragment("bla")
    assert list(Fragment("bla").iter_leaves()) == [fragment]
    actual = list(
        Fragment(
            {"a": 4, "b": "test", "c": {"d": [2, {"e": None, "f": "test2"}]}}
        ).iter_leaves()
    )

    expected = [
        Fragment(value=4, path=["a"]),
        Fragment(value="test", path=["b"]),
        Fragment(value=2, path=["c", "d", 0]),
        Fragment(value=None, path=["c", "d", 1, "e"]),
        Fragment(value="test2", path=["c", "d", 1, "f"]),
    ]

    if sys.version_info[:2] >= (3, 6):  # pragma: nocover
        assert actual == expected
    else:  # pragma: nocover

        def to_set(fragment_list):
            return set((item.value, tuple(item.path)) for item in fragment_list)

        assert to_set(actual) == to_set(expected)


def test_expand_value_with_path():
    """Test expanding fragment value with path."""
    actual = Fragment("bla", path=["a", "b"]).expand_value_with_path()
    expected = {"a": {"b": "bla"}}
    assert actual == expected


@pytest.mark.parametrize(
    "a, b, expected",
    [
        pytest.param({"a": 5}, {"b": 6}, {"a": 5, "b": 6}, id="simple dict update"),
        pytest.param(
            {"a": 5},
            {"b": 6, "a": 4},
            {"a": 4, "b": 6},
            id="simple dict update with overwrite",
        ),
        pytest.param(
            {"a": {"b": 1, "c": 2}},
            {"d": 3, "a": {"b": "new"}},
            {"a": {"b": "new", "c": 2}, "d": 3},
            id="nested dict update",
        ),
        pytest.param([1, 2, 3], [1, 4], [1, 4, 3], id="list update"),
        pytest.param(
            {"a": [1, {"b": 2}, 3]},
            {"a": [EMPTY, 2]},
            {"a": [1, 2, 3]},
            id="nested dict list update",
        ),
        pytest.param(
            {"a": [1, {"b": 2}, 3]},
            {"a": [EMPTY, {"c": 4}]},
            {"a": [1, {"b": 2, "c": 4}, 3]},
            id="nested dict list update",
        ),
        pytest.param(1, 2, 2, id="simple object overwrite"),
        pytest.param([1], 2, 2, id="simple object overwrite"),
    ],
)
def test_merge_nested(a, b, expected):
    """Testing nested merge."""
    assert merge_nested(a, b) == expected


@pytest.mark.parametrize(
    "a_kw, b_kw, expected_kw",
    [
        ({"value": 4, "path": ["a"]}, {"value": {"a": 5}}, {"value": {"a": 5}}),
        (
            {"value": {"a": 4, "b": ["c", "d", "e"]}, "path": ["root"]},
            {"value": {"bla": 2}, "path": ["root", "b", 1]},
            {"value": {"a": 4, "b": ["c", {"bla": 2}, "e"]}, "path": ["root"]},
        ),
        (
            {"value": {"a": 4, "b": {"c": "d"}}, "path": ["root"]},
            {"value": {"b": 2}, "path": ["root"]},
            {"value": {"a": 4, "b": 2}, "path": ["root"]},
        ),
        ({"value": 3}, {"value": 5}, {"value": 5}),
    ],
)
def test_fragment_merge(a_kw, b_kw, expected_kw):
    """Test the apply method of the fragment class."""
    actual = Fragment(**a_kw).merge(Fragment(**b_kw))
    expected = Fragment(**expected_kw)
    assert actual == expected
