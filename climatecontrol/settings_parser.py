#!/usr/bin/env python

"""
Settings parser.
"""

import os
import toml
from collections.abc import Mapping as MappingABC
from typing import Optional, Iterable, List, Union, Any, Callable, Mapping, Dict
from . import logtools
import logging
from copy import deepcopy
logger = logging.getLogger(__name__)


class SettingsValidationError(ValueError):
    pass


class SettingsFileError(ValueError):
    pass


class Settings(MappingABC):

    @logtools.log_exception(logger)
    def __init__(self,
                 settings_file: Optional[str] = None,
                 env_prefix: str = 'APP_SETTINGS',
                 settings_file_env_suffix: str = 'SETTINGS_FILE',
                 filters: Optional[Union[str, Iterable, Mapping]] = None,
                 parser: Optional[Callable] = None) -> None:
        """A Settings instance allows settings to be loaded from a settings file or
        environment variables.

        args:
            settings_file: If set, is used as a path to a settings file (toml
                format) from which all settings are loaded
            env_prefix: Environment variables which start with this prefix will
                be parsed as settings.
            settings_file_env_suffix: The combination out of this suffix and
                `env_prefix` define the environment variable which (if set)
                will be used as a path to a settings file. Note that the
                explicit ``settings_file`` argument overrides the file set in
                the environment variable.
            filters: Allows the settings to be filtered depending on the passed
                value. A string value will only use the settings section defined
                by the string. A ``dict`` or ``Mapping`` allows the settings to
                be limited to multiple sublevels.
            parser: If given, defines a custom function to further process the
                result of the settings. The function should take a single
                nested dictionary argument (the settings map) as an argument
                and output a nested dictionary.

        examples:
            >>> import os
            >>> os.environ['MY_APP_SECTION1_SUBSECTION1'] = 'test1'
            >>> os.environ['MY_APP_SECTION2_SUBSECTION2'] = 'test2'
            >>> os.environ['MY_APP_SECTION2_SUBSECTION3'] = 'test3'
            >>> settings_map = Settings(env_prefix='MY_APP')
            >>> dict(settings_map)
            {'section1': {'subsection1': 'test1'}, 'section2': {'subsection2': 'test2', 'subsection3': 'test3'}}

            Using filters we can conveniently promote a specific sections to the top level namespace

            >>> dict(Settings(env_prefix='MY_APP', filters='section1'))
            {'subsection1': 'test1'}

            Or gather multiple sections into the same namespace (sometimes dangerous if the subsections are not unique)

            >>> dict(Settings(env_prefix='MY_APP', filters=['section1', 'section2']))
            {'subsection1': 'test1', 'subsection2': 'test2', 'subsection3': 'test3'}

        """
        if parser and not callable(parser):
            raise TypeError('If given, ``parser`` must be a callable')
        self._parse = parser
        self.filters = filters
        self.env_prefix = env_prefix
        self.settings_file_env_suffix = settings_file_env_suffix
        self.settings_file = settings_file
        self.external_data = {}  # type: Dict
        self.update()

    @property
    def env_prefix(self) -> str:
        return self._env_prefix

    @env_prefix.setter
    def env_prefix(self, value: str):
        self._env_prefix = build_env_var(value)

    @property
    def settings_file_env_suffix(self) -> str:
        return self._settings_file_env_suffix

    @settings_file_env_suffix.setter
    def settings_file_env_suffix(self, value: str):
        self._settings_file_env_suffix = value
        self._settings_file_env_var = build_env_var(self.env_prefix, value)

    @property
    def settings_file_env_var(self) -> str:
        return self._settings_file_env_var

    @settings_file_env_var.setter
    def settings_file_env_var(self, value: str):
        raise AttributeError('Can\'t set `settings_file_env_var` directly. Set `settings_file_env_suffix` instead.')

    @property
    def settings_file(self):
        return self._settings_file

    @settings_file.setter
    def settings_file(self, value: str):
        self._settings_file = value or os.environ.get(self.settings_file_env_var)

    @property
    def parser(self):
        return self._parse

    @parser.setter
    def parser(self, value: Optional[Callable]):
        if value and not callable(value):
            raise TypeError('If given, ``parser`` must be a callable')
        self._parse = value

    def update(self, d: Optional[Union[Mapping, Dict]] = None) -> None:
        """Updates object settings and reload files and environment variables.

        Args:
            d: Updates for settings. This is equivilant to `dict.update` except
                that the update is recursive for nested dictionaries.

        Example:
            >>> import os
            >>> os.environ['MY_APP_SECTION_VALUE'] = 'test'
            >>> settings = Settings(env_prefix='MY_APP')
            >>> dict(settings)
            {'section': {'value': 'test'}}
            >>>
            >>> # now update the settings
            >>> os.environ['MY_APP_SECTION2_NEW_ENV_VALUE'] = 'new_env_data'
            >>> settings.update({'section': {'new_value': 'new'}})
            >>> dict(settings)
            {'section': {'value': 'test', 'new_value': 'new'}, 'section2': {'new_env_value': 'new_env_data'}}

        """
        settings_map = {}  # type: Dict
        update_nested(settings_map, self.parse_env_vars())
        update_nested(settings_map, self.read_file())
        if d:
            update_nested(self.external_data, d)
            update_nested(settings_map, self.external_data)
        settings_map = self.subtree(settings_map)
        self._data = self.parse(settings_map)

    def parse(self, data):
        if self._parse:
            return self._parse(data)
        else:
            return data

    def __repr__(self):
        return self.__class__.__name__ + '({!r}, {!r}, {!r}, {!r}, {!r})'.format(
            self.settings_file,
            self.env_prefix,
            self.settings_file_env_suffix,
            self.filters,
            self._parse)

    def __len__(self):
        return len(self._data)

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        for k in self._data:
            yield k

    def _read_file(self) -> Mapping:
        if self.settings_file:
            if os.path.isfile(self.settings_file):
                with open(self.settings_file) as f:
                    return toml.load(f)
            elif self.settings_file.lstrip().startswith('['):
                return toml.loads(self.settings_file)
        else:
            return {}

    def read_file(self) -> Mapping:
        return self._read_file()

    def parse_env_vars(self) -> Mapping:
        return parse_env_vars(self.env_prefix, exclude=(self.settings_file_env_var,))

    def subtree(self, data: Dict) -> Dict:
        return subtree(data, self.filters, parent_hierarchy=['settings'])


def build_env_var(*parts: str, split_char='_') -> str:
    return '_'.join(p.strip(split_char).upper() for p in parts)


def parse_env_vars(env_prefix: Optional[str] = None,
                   max_depth: int = 1,
                   split_char: str = '_',
                   exclude: Iterable[str] = ()) -> Mapping:
    """Convert environment variables to nested dict. Note that all string inputs
    are case insensitive and all resulting keys are lower case.

    args:
        env_prefix: Only environment variables which start with this string
            (case insensitive) are considered.
        max_depth: Maximumum depth of nested variables to consider.
        split_char: Character to split variables at. Note that if env_prefix
            is given, the variable name must also be seperated from the base
            with this character.

    returns:
        nested dictionary

    examples:
        >>> os.environ['THIS_EXAMPLE_TESTGROUP_TESTVAR'] = 27
        >>> result_dict = parse_environment_vars(env_prefix='THIS_EXAMPLE', max_depth=2, split_char='_')
        >>> result_dict
        {'testgroup': {'testvar': 27}}

    """
    exclude_set = set(s.lower() for s in exclude)
    settings_map = {}  # type: dict
    if len(split_char) != 1:
        raise ValueError('``split_char`` must be a single character')
    split_char = split_char.lower()
    env_prefix = env_prefix.lower().rstrip(split_char) + split_char
    if len(env_prefix) <= 1:
        return settings_map
    for env_var in os.environ:
        env_var_lower = env_var.lower()
        if env_var_lower in exclude_set or not env_var_lower.startswith(env_prefix):
            continue
        nested_keys = env_var_lower[len(env_prefix):].split(split_char, max_depth)
        if not nested_keys:
            continue
        update = {}  # type: dict
        u = update
        for nk in nested_keys[:-1]:
            u[nk] = {}
            u = u[nk]
        u[nested_keys[-1]] = get_env_var_value(env_var)
        logger.info('Getting settings from env var: {}'.format(env_var))
        update_nested(settings_map, update)
    return settings_map


def get_env_var_value(env_var: str) -> Any:
    v = os.environ[env_var]
    try:
        return toml.load_value(v)[0]
    except (ValueError, TypeError, IndexError):
        return v


def update_nested(d: Dict, u: Mapping) -> Dict:
    """Updates nested mapping ``d`` with nested mapping u"""
    for k, v in u.items():
        if isinstance(v, Mapping):
            r = update_nested(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def subtree(data: Union[Dict, Mapping],
            filters: Optional[Union[str, Mapping, Iterable]] = None,
            parent_hierarchy: Iterable = ()) -> Any:
    if not parent_hierarchy:
        parent_hierarchy = []
    else:
        parent_hierarchy = list(parent_hierarchy)
    if not filters or filters == '*':
        return data
    if isinstance(filters, str):
        key = filters
        try:
            return deepcopy(data[key])
        except KeyError:
            parent_str = '.'.join(parent_hierarchy)
            logger.warning('Section {}.{} not found in data'.format(parent_str, key))
            return {}
    elif isinstance(filters, Mapping):
        new_data = {}  # type: Dict
        parent_hierarchy = parent_hierarchy + []
        for k, v in filters.items():
            subdata_root = subtree(data, k)
            subdata = subtree(subdata_root, v, parent_hierarchy=parent_hierarchy + [k])
            new_data.update(subdata)
        return new_data
    elif isinstance(filters, Iterable):
        new_data = {}
        parent_hierarchy = parent_hierarchy + []
        for f in filters:
            new_data.update(subtree(data, f, parent_hierarchy=parent_hierarchy))
        return new_data
    else:
        raise TypeError('filters must be strings or iterables')
