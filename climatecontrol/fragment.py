"""Module for defining settings fragments."""

from copy import deepcopy
from enum import Enum
from itertools import zip_longest
from typing import Any, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

from .utils import EMPTY, get_nested, merge_nested


class FragmentKind(Enum):
    """Fragment kind."""

    MERGE = 'MERGE'
    REMOVE = 'REMOVE'


class FragmentPath(Sequence):
    """Path indicating nested levels of a fragment value."""

    def __init__(self, iterable: Iterable = ()):
        """Assign initial iterable data."""
        self._data: list = list(iterable)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator:
        yield from self._data

    def __getitem__(self, index) -> Any:
        return self._data[index]

    def __repr__(self) -> str:
        return '{}({})'.format(type(self).__qualname__, repr(self._data))

    def __eq__(self, other):
        return type(self) == type(other) and self._data == other._data

    def expand(self, value=EMPTY):
        """Expand path to object.

        Depending on each entry of the path a dictionary or list is created.
        Entries that are not defined are will with the :data:`EMPTY` object.

        Example:

            >>> FragmentPath(['a', 1, 'b']).expand()
            {'a': [<EMPTY>, {'b': <EMPTY>}]}

        """
        if self._data and self._is_list_index(self._data[0]):
            new_value = [EMPTY] * (self._data[0] + 1)
        else:
            new_value = {}
        sub_value = new_value
        for subpath, next_subpath in zip_longest(self._data[:-1], self._data[1:]):
            if self._is_list_index(next_subpath):
                sub_value[subpath] = [EMPTY] * (next_subpath + 1)
            else:
                sub_value[subpath] = {}
            sub_value = sub_value[subpath]

        # last path value holds the actual value
        if self._data:
            sub_value[self._data[-1]] = value

        return new_value

    def common(self, other: Sequence) -> 'FragmentPath':
        """Given another sequence representing a path, return the part of the sequence up to the point where they first differ."""
        common_path: List = []
        other_path: FragmentPath = type(self)(other)
        for subpath, subpath_other in zip(self._data, other_path):
            if subpath == subpath_other:
                common_path.append(subpath)
            else:
                break
        return type(self)(common_path)

    def _is_list_index(self, index) -> bool:
        """Check if index is a list index."""
        return isinstance(index, int)


class Fragment:
    """Data fragment for storing a value and metadata related to it."""

    value: Any
    source: str
    path: FragmentPath
    kind: FragmentKind

    def __init__(self, value: Any,
                 source: str = None,
                 path: Iterable = None,
                 kind: FragmentKind = None) -> None:
        """Initialize fragment."""
        if isinstance(value, Fragment):
            fragment = value
            value = fragment.value
            source = fragment.source
            path = fragment.path
            kind = fragment.kind

        if isinstance(path, str):
            path = path.split('.')

        self.value = value
        self.source = source if source is not None else ''
        self.path = FragmentPath(path) if path is not None else FragmentPath()
        self.kind = kind if kind is not None else FragmentKind.MERGE

    def __repr__(self):
        return '{}(value={}, source={}, path={}, kind={})'.format(
            type(self).__qualname__,
            repr(self.value),
            repr(self.source),
            repr(self.path),
            repr(self.kind)
        )

    def __eq__(self, other):
        return (
            type(self) == type(other) and
            self.value == other.value and
            self.source == other.source and
            self.path == other.path and
            self.kind == other.kind
        )

    def iter_leaves(self) -> Iterator['Fragment']:
        """Iterate over all leaves of a fragment.

        A leaf is obtained by walking through any nested dictionaries until a
        non-dictionary value is found.

        """
        items: Iterable[tuple]
        if isinstance(self.value, Mapping):
            items = self.value.items()
        elif isinstance(self.value, Sequence) and not isinstance(self.value, str):
            items = enumerate(self.value)
        else:
            # Can't obtain any items so just assume this is a leaf
            yield self
            return

        for k, v in items:
            yield from self.clone(value=v, path=list(self.path) + [k]).iter_leaves()

    def expand_value_with_path(self) -> Any:
        """Create expanded dictionary where the fragments path acts as nested keys."""
        return self.path.expand(self.value)

    def merge(self, other: 'Fragment') -> 'Fragment':
        """Merge with another fragment."""
        expanded_value = self.expand_value_with_path()
        other_expanded_value = other.expand_value_with_path()
        merged_value = merge_nested(expanded_value, other_expanded_value)

        new_path = self.path.common(other.path)
        new_value = get_nested(merged_value, new_path)
        new_source = ', '.join(str(s) for s in [self.source, other.source] if s)

        return self.clone(value=new_value, source=new_source, path=new_path)

    def difference(self, fragment: 'Fragment') -> 'Fragment':
        """Delete a fragments elements from the current fragment."""
        expanded_value = deepcopy(self.expand_value_with_path())

        for leaf in fragment.iter_leaves():
            if leaf.path:
                submap = get_nested(expanded_value, leaf.path[:-1])
                del submap[leaf.path[-1]]

        new_value = get_nested(expanded_value, self.path)

        return self.clone(value=new_value)

    def apply(self, fragment: 'Fragment'):
        """Apply a second fragment according to it's "kind"."""
        if fragment.kind == FragmentKind.MERGE:
            return self.merge(fragment)
        elif fragment.kind == FragmentKind.REMOVE:
            return self.difference(fragment)
        else:
            raise ValueError('Can\'t apply fragment with kind: {}'.format(fragment.kind))

    def clone(self, **kwargs):
        """Clone fragment but using ``kwargs`` as alternative constructor arguments."""
        defaults = {
            'value': self.value,
            'source': self.source,
            'path': self.path,
            'kind': self.kind,
        }
        updated_kwargs = {**defaults, **kwargs}
        return type(self)(**updated_kwargs)
