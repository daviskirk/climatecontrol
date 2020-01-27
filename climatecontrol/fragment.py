"""Module for defining settings fragments."""

from contextlib import suppress
from itertools import zip_longest
from typing import (
    Any,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    Type,
    TypeVar,
    Union,
)

from .utils import EMPTY, get_nested, merge_nested

T = TypeVar("T")
FV = TypeVar("FV")
FP = TypeVar("FP", bound="FragmentPath")
F = TypeVar("F", bound="Fragment")


class FragmentPath(Sequence):
    """Path indicating nested levels of a fragment value."""

    def __init__(self, iterable: Iterable = ()) -> None:
        """Assign initial iterable data."""
        self._data: list = list(iterable)

    @classmethod
    def from_spec(cls: Type[FP], spec: Union[str, int, Sequence]) -> FP:
        """Construct fragment path from complex spec.

        Examples:
            >>> FragmentPath.from_spec('a.b.0.c')
            FragmentPath(['a', 'b', 0, 'c'])
            >>> FragmentPath([1])
            FragmentPath([1])
            >>> FragmentPath(['a', 'b'])
            FragmentPath(['a', 'b'])

        """
        return cls(cls._iter_spec(spec))

    @staticmethod
    def _iter_spec(spec: Any) -> Iterator:
        try:
            spec_iter = spec.split(".")
        except AttributeError:
            try:
                spec_iter = iter(spec)
            except TypeError:
                yield spec
                return

        for item in spec_iter:
            with suppress(AttributeError):
                if item.isdigit():
                    item = int(item)
            yield item

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator:
        yield from self._data

    def __getitem__(self, index) -> Any:
        return self._data[index]

    def __repr__(self) -> str:
        return "{}({})".format(type(self).__qualname__, repr(self._data))

    def __str__(self) -> str:
        return f"{type(self).__qualname__}({self._data})"

    def __eq__(self, other) -> bool:
        return type(self) == type(other) and self._data == other._data

    def expand(self, value: Any = None) -> Any:
        """Expand path to object.

        Depending on each entry of the path a dictionary or list is created.
        Entries that are not defined are will with the :data:`EMPTY` object.

        Example:
            >>> FragmentPath(['a', 1, 'b']).expand()
            {'a': [<EMPTY>, {'b': None}]}

        """
        if not self._data:
            return value
        if self._data and self._is_list_index(self._data[0]):
            new_value: Union[dict, list] = [EMPTY] * (self._data[0] + 1)
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
        sub_value[self._data[-1]] = value

        return new_value

    def common(self: FP, other: Sequence) -> FP:
        """Given a second path, return the part of the sequence up to the point where they first differ."""
        common_path = []
        other_path: FragmentPath = type(self)(other)
        for subpath, subpath_other in zip(self._data, other_path):
            if subpath == subpath_other:
                common_path.append(subpath)
            else:
                break
        return type(self)(common_path)

    @classmethod
    def _is_list_index(cls, index) -> bool:
        """Check if index is a list index."""
        return isinstance(index, int)


class Fragment(Generic[FV]):
    """Data fragment for storing a value and metadata related to it."""

    path: FragmentPath

    def __init__(self, value: FV, source: str = "", path: Sequence = ()) -> None:
        """Initialize fragment."""
        self.value = value
        self.source = source
        self.path = FragmentPath(path)

    def __repr__(self) -> str:
        return "{}(value={}, source={}, path={})".format(
            type(self).__qualname__,
            repr(self.value),
            repr(self.source),
            repr(self.path),
        )

    def __eq__(self, other) -> bool:
        return (
            type(self) == type(other)
            and self.value == other.value
            and self.source == other.source
            and self.path == other.path
        )

    def iter_leaves(self: F) -> Iterator[F]:
        """Iterate over all leaves of a fragment.

        A leaf is obtained by walking through any nested dictionaries until a
        non-dictionary value is found.

        """
        if isinstance(self.value, Mapping):
            items: Iterable[tuple] = self.value.items()
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

    def merge(self: F, other: "Fragment") -> F:
        """Merge with another fragment."""
        expanded_value = self.expand_value_with_path()
        other_expanded_value = other.expand_value_with_path()
        merged_value = merge_nested(expanded_value, other_expanded_value)

        new_path = self.path.common(other.path)
        new_value = get_nested(merged_value, new_path)
        new_source = ", ".join(str(s) for s in [self.source, other.source] if s)

        return self.clone(value=new_value, source=new_source, path=new_path)

    def clone(self: F, **kwargs) -> F:
        """Clone fragment but using ``kwargs`` as alternative constructor arguments."""
        defaults = {"value": self.value, "source": self.source, "path": self.path}
        updated_kwargs = {**defaults, **kwargs}
        return type(self)(**updated_kwargs)
