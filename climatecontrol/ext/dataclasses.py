"""Extension for using climatecontrol with dataclasses."""

from dataclasses import is_dataclass
from typing import Generic, Mapping, Type, TypeVar

import dacite

from climatecontrol.core import Climate as BaseClimate
from climatecontrol.core import SettingsItem as BaseSettingsItem
from climatecontrol.fragment import FragmentPath

T = TypeVar("T")


class SettingsItem(BaseSettingsItem):
    @classmethod
    def _self_is_mutable(cls, value) -> bool:
        return super()._self_is_mutable(value) or is_dataclass(value)


class Climate(BaseClimate, Generic[T]):
    """Climate settings manager for dataclasses."""

    _processors = tuple(list(BaseClimate._processors) + [])

    def __init__(self, *args, dataclass_cls: Type[T], **kwargs):
        """Initialize dataclass climate object.

        Uses a dataclass as a schema to initialize settings and check types.

        Args:
            *args, **kwargs: See :class:`climateontrol.Climate`
            dataclass_cls: Additional argument specific to the dataclass extension.  Given a class devorated by :func:`dataclasses.dataclass` the settings object will be initialized and checked according to the classes specifications and types.

        Examples:

            >>> from climatecontrol.ext.dataclasses import Climate
            >>> from dataclasses import dataclass, field
            >>>
            >>> @dataclass
            ... class SettingsSubSchema:
            ...     d: int = 4
            ...
            >>> @dataclass
            ... class SettingsSchema:
            ...     a: str = 'test'
            ...     b: bool = False
            ...     c: SettingsSubSchema = field(default_factory=SettingsSubSchema)
            ...
            >>> climate = Climate(dataclass_cls=SettingsSchema)
            >>> # defaults are initialized automatically:
            >>> climate.settings.a
            'test'
            >>> climate.settings.c.d
            4
            >>> # Types are checked if given
            >>> climate.update({'c': {'d': 'boom!'}})
            Traceback (most recent call last):
                ...
            dacite.exceptions.WrongTypeError: wrong value type for field "c.d" - should be "int" instead of value "boom!" of type "str"

        See Also:
            :module:`dacite`: Used to initialize and check dataclasses.

        """
        self.dataclass_cls = dataclass_cls
        super().__init__(*args, **kwargs)

    @property
    def settings(self) -> T:
        self.ensure_initialized()
        return SettingsItem(self._data, self, FragmentPath())

    def parse(self, data: Mapping) -> T:
        """Parse data into the provided dataclass."""
        data = super().parse(data)
        obj: T = dacite.from_dict(self.dataclass_cls, {k: v for k, v in data.items()})
        return obj
