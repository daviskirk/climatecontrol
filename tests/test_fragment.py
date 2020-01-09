"""Tests for fragments."""

import pytest

from climatecontrol.fragment import Fragment, FragmentPath, EMPTY, FragmentKind


def test_fragment_path():
    """Test fragment path construction."""
    assert not FragmentPath()  # empty path is falsy
    assert FragmentPath([]) == FragmentPath(), 'empty fragment paths should be equal'
    assert FragmentPath(['a', 'stuff', 1]) == FragmentPath(['a', 'stuff', 1]), 'Unexpected equality result'
    assert FragmentPath(['a', 'stuff', 1]) != FragmentPath(['a', 'wrong', 1]), 'Unexpected inequality result'
    assert list(FragmentPath(['a', 'stuff', 1])) == ['a', 'stuff', 1], 'Unexpected list conversion result'
    assert str(FragmentPath(['a', 'stuff', 1])) == "FragmentPath(['a', 'stuff', 1])", 'Unexpected string representation'
    assert FragmentPath(['a', 'stuff', 1])[1] == 'stuff', 'unexpected indexing'


def test_fragment_path_expand():
    """Test expansion of fragment path."""
    assert FragmentPath(['a']).expand('test') == {'a': 'test'}
    assert (
        FragmentPath(['a', 'stuff', 1, 'bla']).expand() ==
        {
            'a': {
                'stuff': [
                    EMPTY,
                    {'bla': EMPTY}
                ]
            }
        }
    )


@pytest.mark.parametrize('a,b,expected', [
    (['a'], ['b'], []),
    ([], [], []),
    ([1, 2, 3], [1, 2, 4, 5], [1, 2]),
    (['a', 'b', 'c'], ['a', 'b'], ['a', 'b']),
    (['a', 'b', 'c'], ['a', 'b', 'd'], ['a', 'b']),
    (['a', 'b', 'c'], ['wrong', 'b', 'c'], []),
])
def test_fragment_path_common(a, b, expected):
    """Test common path."""
    assert FragmentPath(a).common(b) == FragmentPath(expected)


def test_fragment():
    """Test fragment constructor and representation."""
    fragment = Fragment(value='bla', source='test', path=['a', 'b'], kind=FragmentKind.REMOVE)
    assert fragment
    assert str(fragment) == \
        "Fragment(value='bla', source='test', path=FragmentPath(['a', 'b']), kind=<FragmentKind.REMOVE: 'REMOVE'>)", \
        'unexpected string representation'


def test_fragment_equality():
    """Test fragment equality."""
    assert (
        Fragment(value='bla', source='test', path=['a', 'b'], kind=FragmentKind.REMOVE) ==
        Fragment(value='bla', source='test', path=['a', 'b'], kind=FragmentKind.REMOVE)
    )
    assert Fragment(value='bla') == Fragment(value='bla')
    assert Fragment(value='bla') != Fragment(value='blub')
    assert Fragment(value='bla', source='a') != Fragment(value='bla', source='b')
    assert Fragment(value='bla', path=['a']) != Fragment(value='bla', path=['b'])
    assert Fragment(value='bla', kind=FragmentKind.MERGE) != Fragment(value='bla', kind=FragmentKind.REMOVE)


def test_fragment_clone():
    """Test the fragments clone method."""
    fragment = Fragment('bla')
    assert fragment.clone() == fragment
    assert fragment.clone() is not fragment
    cloned = fragment.clone(source=['a'])
    assert cloned != fragment
    assert cloned == Fragment('bla', source=['a'])


def test_fragment_iter_leaves():
    """Test that iterating over fragment leaves gives expected result."""
    fragment = Fragment('bla')
    assert list(Fragment('bla').iter_leaves()) == [fragment]
    actual = list(Fragment({
        'a': 4,
        'b': 'test',
        'c': {
            'd': [
                2,
                {
                    'e': None,
                    'f': 'test2'
                }
            ]
        }
    }).iter_leaves())

    expected = [
        Fragment(value=4, path=['a']),
        Fragment(value='test', path=['b']),
        Fragment(value=2, path=['c', 'd', 0]),
        Fragment(value=None, path=['c', 'd', 1, 'e']),
        Fragment(value='test2', path=['c', 'd', 1, 'f'])
    ]

    assert actual == expected


def test_expand_value_with_path():
    """Test expanding fragment value with path."""
    actual = Fragment('bla', path=['a', 'b']).expand_value_with_path()
    expected = {'a': {'b': 'bla'}}
    assert actual == expected


@pytest.mark.parametrize('a_kw, b_kw, expected_kw', [
    (
        {'value': 4, 'path': ['a']},
        {'value': {'a': 5}},
        {'value': 5, 'path': ['a']}
    ),
    (
        {'value': {'a': 4, 'b': ['c', 'd', 'e']}, 'path': ['root']},
        {'value': {'bla': 2}, 'path': ['root', 'a', 'b', 1]},
        {'value': {'a': 4, 'b': ['c', {'bla': 2}, 'e']}, 'path': ['root']}
    ),
    (
        {'value': {'a': 4, 'b': {'c': 'd'}}, 'path': ['root']},
        {'value': {'b': 2}, 'path': ['root', 'a']},
        {'value': {'a': 4, 'b': 2}, 'path': ['root']}
    ),
    (
        {'value': 3},
        {'value': 5},
        {'value': 5}
    ),
    (
        {'value': {'a': {'b': {'this': 'that'}, 'c': 'test'}, 'bla': 4}},
        {'value': {'b': 5}, 'kind': FragmentKind.REMOVE, 'path': ['a']},
        {'value': {'a': {'c': 'test'}, 'bla': 4}},
    )
])
def test_fragment_apply(a_kw, b_kw, expected_kw):
    """Test the apply method of the fragment class."""
    actual = Fragment(**a_kw).apply(Fragment(value=b_kw))
    expected = Fragment(**expected_kw)
    assert actual == expected
