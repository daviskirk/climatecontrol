"""Utility functions."""

from typing import Type  # noqa: F401
from typing import Dict, Iterator, Mapping, Sequence, Union


def update_nested(d: Dict, u: Mapping) -> Dict:
    """Update nested mapping ``d`` with nested mapping ``u``."""
    for k, v in u.items():
        if isinstance(v, Mapping):
            r = update_nested(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


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
