"""Environment variable parser."""

import logging
import os
import warnings
from typing import Iterable, Iterator, NamedTuple, Tuple

from . import file_loaders
from .fragment import Fragment
from .utils import parse_as_json_if_possible, int_if_digit

logger = logging.getLogger(__name__)

EnvSetting = NamedTuple('EnvSetting', [('name', str), ('value', Fragment)])


class EnvParser:
    r"""Environment variable parser.

    Args:
        prefix: Only environment variables which start with this string
            (case insensitive) are considered.
        split_char: Character to split variables at. Note that if prefix
            is given, the variable name must also be seperated from the base
            with this character.
        implicit_depth: Maximumum depth of implicitely nested environment
            variables to consider. If set, the first `implicit_depth`
            occurrences of a single `split_char` character will be considered
            nested settings boundaries. Note that if a file is given, the
            maximum depth does not apply as the definition is clear.
            **WARNING:** This feature is deprecated as of version 0.8 and will be
            removed in a future version.
        settings_file_suffix: Suffix to identify an environment variable as a
            settings file.

            >>> env_parser=EnvParser(prefix='A', split_char='_', setting_file_suffix='SF')
            >>> env_parser.settings_file_env_var
            'A_SF'

        exclude: Environment variables to exclude. Note that the settings file
            constructed from ``settings_file_suffix`` is excluded in any case.

    Attributes:
        settings_file_env_var: Name of the settings file environment variable.
            Is constructed automatically.

    Examples:
        >>> env_parser = EnvParser(prefix='THIS_EXAMPLE', implicit_depth=1)
        >>>
        >>> with os.open('settings.toml', 'w') as f:
        ...     f.write('[testgroup]\nother_var = 345')
        >>> os.environ['THIS_EXAMPLE_TESTGROUP_TESTVAR'] = 27
        >>> os.environ['THIS_EXAMPLE_SETTINGS_FILE'] = './settings.toml'
        >>>
        >>> result_dict = env_parser.parse()
        >>> result_dict
        {'testgroup': {'testvar': 27, 'othervar': 345}}

    """

    def __init__(self,
                 prefix: str = 'CLIMATECONTROL',
                 split_char: str = '_',
                 implicit_depth: int = 0,
                 settings_file_suffix: str = 'SETTINGS_FILE',
                 exclude: Iterable[str] = ()) -> None:
        """Initialize object."""
        self.settings_file_suffix = str(settings_file_suffix)
        self.implicit_depth = int(implicit_depth)
        if implicit_depth != 0:
            warnings.warn('Setting "implicit_depth" is deprecated and will be removed in a future version',
                          DeprecationWarning)
        self.split_char = split_char
        self.prefix = prefix
        self.exclude = exclude  # type: ignore

    @property
    def exclude(self) -> Tuple[str, ...]:
        """Return excluded environment variables."""
        exclude = self._exclude.union({self.settings_file_env_var})
        return tuple(set(s.lower() for s in exclude))

    @exclude.setter
    def exclude(self, exclude: Iterable[str] = ()) -> None:
        """Set excluded environment variables."""
        self._exclude = set(exclude)

    @property
    def prefix(self) -> str:
        """Return prefix used to filter used environment variables."""
        return self._build_env_var(self._prefix) + self.split_char

    @prefix.setter
    def prefix(self, value: str):
        """Set prefix used to filter used environment variables."""
        self._prefix = str(value)

    @property
    def settings_file_env_var(self) -> str:
        """Return environment variable used to indicate a path to a settings file."""
        return self._build_env_var(self.prefix, self.settings_file_suffix)

    @settings_file_env_var.setter
    def settings_file_env_var(self, value: str):
        """Set environment variable used to indicate a path to a settings file."""
        raise AttributeError('Can\'t set `settings_file_env_var` directly. Set `settings_file_suffix` instead.')

    @property
    def split_char(self) -> str:
        """Return character used to split sections."""
        return self._split_char

    @split_char.setter
    def split_char(self, char: str) -> None:
        """Set character used to split sections."""
        char = str(char)
        if len(char) != 1:
            raise ValueError('``split_char`` must be a single character')
        self._split_char = str(char)

    def iter_load(self, include_vars=True, include_file: bool = True) -> Iterator[Fragment]:
        """Convert environment variables to nested dict.

        Note that all string inputs are case insensitive and all resulting keys
        are lower case.

        Args:
            include_file: If set to ``True`` also parses the settings file if found.

        Returns:
            nested dictionary

        Examples:
            Use implicit_depth to ensure that split chars are used up to a certain depth.

            >>> os.environ['THIS_EXAMPLE_TESTGROUP_TESTVAR'] = 27
            >>> env_parser = EnvParser(prefix='THIS_EXAMPLE')
            >>> result_dict = env_parser.parse()
            >>> result_dict
            {'testgroup_testvar': 27}
            >>> env_parser = EnvParser(prefix='THIS_EXAMPLE', implicit_depth=1)
            >>> os.environ['THIS_EXAMPLE_TESTGROUP_TESTVAR'] = 27
            >>> result_dict = env_parser.parse()
            >>> result_dict
            {'testgroup': {'testvar': 27}}

        """
        if include_file:
            settings_file_str = os.getenv(self.settings_file_env_var, '')
            settings_files = [s.strip() for s in settings_file_str.split(',')]
            for settings_file in settings_files:
                for fragment in file_loaders.iter_load(settings_file):
                    fragment.source = 'ENV:' + str(self.settings_file_env_var) + ':' + fragment.source
                    yield fragment
        if include_vars:
            for env_var, env_var_value in os.environ.items():
                nested_keys = list(self._iter_nested_keys(env_var))
                if not nested_keys:
                    continue
                value = parse_as_json_if_possible(env_var_value)
                fragment = Fragment(value=value, path=nested_keys, source='ENV:' + env_var)
                yield fragment

    def _build_env_var(self, *parts: str) -> str:
        return self.split_char.join(self._strip_split_char(p).upper() for p in parts)

    def _iter_nested_keys(self, env_var: str) -> Iterator[str]:
        """Iterate over nested keys of an environment variable name.

        Yields:
            String representing each nested key.

        """
        env_var_low = env_var.lower()
        if env_var_low in self.exclude or not env_var_low.startswith(self.prefix.lower()):
            return
        body = env_var_low[len(self.prefix):]
        sections = body.split(self.split_char * 2)
        for i_section, section in enumerate(sections):
            if self.implicit_depth > 0 and i_section == 0:
                for s in section.split(self.split_char, self.implicit_depth):
                    if s:
                        yield int_if_digit(s)
            elif section:
                yield int_if_digit(section)

    def _strip_split_char(self, s):
        if s.startswith(self.split_char):
            s = s[len(self.split_char):]
        elif s.endswith(self.split_char):
            s = s[:-len(self.split_char)]
        return s
