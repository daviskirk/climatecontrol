"""Climatecontrol extension for using pydantic schemas as source.

Supports both Pydantic v1 (>=1.7.4) and v2 (>=2.0).
"""

from typing import Generic, Mapping, Type, TypeVar

from pydantic import BaseModel

from climatecontrol.core import Climate as BaseClimate
from climatecontrol.core import SettingsItem as BaseSettingsItem
from climatecontrol.fragment import FragmentPath

T = TypeVar("T", bound=BaseModel)


class SettingsItem(BaseSettingsItem):
    @classmethod
    def _self_is_mutable(cls, value) -> bool:
        return super()._self_is_mutable(value) or isinstance(value, BaseModel)


class Climate(BaseClimate, Generic[T]):
    """Climate settings manager for dataclasses."""

    def __init__(self, *args, model: Type[T], **kwargs):
        """Initialize pydantic climate object.

        Uses a pydantic model as a schema to initialize settings and check types.

        Args:
            *args, **kwargs: See :class:`climateontrol.Climate`
            model: Additional argument specific to the model to use for the settings.

        Examples:

            >>> from climatecontrol.ext.pydantic import Climate
            >>>
            >>> class SettingsSubSchema(BaseModel):
            ...     d: int = 4
            ...
            >>> class SettingsSchema(BaseModel):
            ...     a: str = 'test'
            ...     b: bool = False
            ...     c: SettingsSubSchema = SettingsSubSchema()
            ...
            >>> climate = Climate(model=SettingsSchema)
            >>> # defaults are initialized automatically:
            >>> climate.settings.a
            'test'
            >>> climate.settings.c.d
            4
            >>> # Types are checked if given
            >>> climate.update({'c': {'d': 'boom!'}})
            Traceback (most recent call last):
               ...
            pydantic.ValidationError: 1 validation error for SettingsSchema
            c -> d
              Input should be a valid integer...

        Note:
            This extension supports both Pydantic v1 (>=1.7.4) and v2 (>=2.0).
            The error messages and formats may vary between versions.

        See Also:
            :module:`pydantic`: Used to initialize and check settings.

        """
        self.model = model
        super().__init__(*args, **kwargs)

    @property
    def settings(self) -> T:
        self.ensure_initialized()
        return SettingsItem(self._data, self, FragmentPath())

    def parse(self, data: Mapping) -> T:
        """Parse data into the provided dataclass."""
        data = super().parse(data)
        obj: T = self.model(**data)
        return obj
