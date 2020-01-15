"""Utility functions."""

from copy import deepcopy
from enum import Enum
import json
from itertools import zip_longest
from typing import Any, Mapping, Sequence, Union


def get_nested(obj: Union[Mapping, Sequence], path: Sequence) -> Any:
    """Get element of a sequence or map based on multiple nested keys.

    Args:
        obj: Object to index from
        path: Sequence of nested keys.

    Example:
        >>> get_nested({'a': {'b': [1, 2]}}, ['a', 'b', 0])
        1

    """
    result = obj
    for subpath in path:
        result = result[subpath]
    return result


def merge_nested(d: Any, u: Any) -> Any:
    """Merge nested mapping or sequence ``d`` with nested mapping or sequence ``u``.

    Dictionaries are merge recursively while sequences are merged by index (and
    expanded automatically if longer). Note that the special value
    :data:``EMPTY`` can be used in `u` to NOT overwrite a sequence item.

    Example:
        merge_nested({'a': {'b': [3, {'c': 4}, 5]}}, {'a': {'b': [EMPTY, {'d': 6}]}})
        {'a': {'b': [3, {'c': 4, 'd': 6}, 5]}}

    """
    if isinstance(d, Mapping):
        new_dict = dict(**d)  # type: dict
        if not isinstance(u, Mapping):
            return deepcopy(u)
        for k, u_v in u.items():
            new_dict[k] = merge_nested(d.get(k), u_v)
        return new_dict
    elif isinstance(d, Sequence) and not isinstance(d, str):
        if not isinstance(u, Sequence) or isinstance(u, str):
            return deepcopy(u)
        new_list = [
            merge_nested(d_item, u_item) if u_item is not EMPTY else d_item
            for d_item, u_item
            in zip_longest(d, u, fillvalue=EMPTY)
        ]
        return new_list
    return deepcopy(u)


def parse_as_json_if_possible(v: str) -> Any:
    """Parse a string value as json if possible, but fallback to the string if not."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            pass
    return v


class _Empty(Enum):
    """Object representing an empty item."""

    EMPTY = None

    def __repr__(self):
        return '<EMPTY>'  # pragma: nocover


EMPTY = _Empty.EMPTY
