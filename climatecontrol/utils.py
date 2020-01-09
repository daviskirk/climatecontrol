"""Utility functions."""

from copy import deepcopy
from typing import Type  # noqa: F401
from typing import Any, Dict, Iterator, Mapping, Sequence, Union
from itertools import zip_longest


class _Empty:
    """Object representing an empty item."""

    def __repr__(self):
        return '<EMPTY>'

    def __bool__(self):
        return False


EMPTY = _Empty()


def get_nested(obj: Union[Mapping, Sequence], path: Sequence[str]) -> Any:
    """Get element of a sequence or map based on multiple nested keys."""
    result = obj
    for subpath in path:
        result = result[subpath]
    return result


def merge_nested(d: Any, u: Any, _update: bool = False) -> Any:
    """Merge nested mapping ``d`` with nested mapping ``u``."""
    if isinstance(d, Mapping):
        new_dict: dict = dict(**d)
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
            in zip(*zip_longest(d, u, fillvalue=EMPTY))
        ]
        return new_list
    return deepcopy(u)


def iter_hierarchy(data: Union[Mapping, Sequence], levels: Sequence[str] = ()) -> Iterator[Sequence[str]]:
    """Iterate over nested keys and yield a tuple describing the level of hierarchy of each leaf.

    Args:
        data: Nested mapping or non-string sequence.

    Example:
        >>> list(_iter_hierarchy({'a': {'b': [{'c': 'item'}, 123]}}))
        [('a', 'b', '[0]', 'c'), ('a', 'b', '[1]')]

    """
    levels = list(levels)
    if not data:
        yield levels
        return data
    elif isinstance(data, Mapping):
        level_type = Mapping  # type: Type
        items = tuple(data.items())
    elif isinstance(data, Sequence) and not isinstance(data, str):
        level_type = Sequence
        items = tuple(enumerate(data))
    else:
        yield levels
        return
    for k, v in items:
        new_level = '[{}]'.format(k) if level_type is Sequence else str(k)
        new_levels = tuple(levels + [new_level])
        if isinstance(v, (Mapping, Sequence)) and not isinstance(v, str):
            yield from iter_hierarchy(v, new_levels)
        else:
            yield new_levels
