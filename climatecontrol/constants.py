"""Constants used in other modules."""


from enum import Enum


class _Removed(Enum):
    """Object representing an empty item."""

    REMOVED = None

    def __repr__(self):
        return "<REMOVED>"  # pragma: nocover


REMOVED = _Removed.REMOVED


class _Empty(Enum):
    """Object representing an empty item."""

    EMPTY = None

    def __repr__(self):
        return "<EMPTY>"  # pragma: nocover


EMPTY = _Empty.EMPTY
