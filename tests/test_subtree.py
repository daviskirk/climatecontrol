"""Settings parser."""

from copy import deepcopy
import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))
from climatecontrol import settings_parser  # noqa: E402


@pytest.fixture
def subtree_data():
    """Return example subtree data."""
    return {
        'subtree1': {
            'setting1': 123,
            'setting2': 444
        },
        'subtree2': {
            'setting3': 123,
            'setting4': 444,
            'subsubtree': {
                'setting5': 5,
                'setting6': 6,
            }
        },
        'subtree3': {
            'settings7': 7
        }
    }


def test_subtree1(subtree_data):
    """Check calling a subtree without args returns an identical object."""
    expected = deepcopy(subtree_data)
    actual = settings_parser.subtree(subtree_data)
    assert actual == expected


@pytest.mark.parametrize('filters', ['subtree1', ['subtree1'], {'subtree': None}])
def test_subtree_sub(subtree_data, filters):
    """Check that subtree filters sub objects correctly."""
    original = deepcopy(subtree_data)
    expected = subtree_data['subtree1']
    actual = settings_parser.subtree(subtree_data, 'subtree1')
    assert actual == expected
    assert original == subtree_data


def test_subtree_multisub(subtree_data):
    """Check that subtree filters multiple sub-objects correctly."""
    filters = ['subtree1', 'subtree2']
    original = deepcopy(subtree_data)
    expected = {}
    expected.update(original['subtree1'])
    expected.update(original['subtree2'])
    actual = settings_parser.subtree(subtree_data, filters)
    assert actual == expected
    assert original == subtree_data


def test_subtree_subsub(subtree_data):
    """Check that subtree filters sub-objects on second hierarchical plane correctly."""
    filters = {'subtree2': 'subsubtree'}
    original = deepcopy(subtree_data)
    expected = subtree_data['subtree2']['subsubtree']
    actual = settings_parser.subtree(subtree_data, filters)
    assert actual == expected
    assert original == subtree_data


def test_subtree_fail(subtree_data):
    """Check that subtree returns an empty object when filters do not correspond with object."""
    filters = {'subtree1': 'subsubtree'}
    original = deepcopy(subtree_data)
    expected = {}
    actual = settings_parser.subtree(subtree_data, filters)
    assert actual == expected
    assert original == subtree_data


def test_subtree_fail2(subtree_data):
    """Check that incorrect filter is ignored."""
    filters = {'subtree1': 'subsubtree', 'subtree2': '*'}
    original = deepcopy(subtree_data)
    expected = subtree_data['subtree2']
    actual = settings_parser.subtree(subtree_data, filters)
    assert actual == expected
    assert original == subtree_data


if __name__ == '__main__':
    sys.exit()
