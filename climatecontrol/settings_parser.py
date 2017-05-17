#!/usr/bin/env python

"""
Settings parser.
"""

import os
import toml
try:
    import click
except ImportError:
    click = None
from collections import OrderedDict
from functools import partial
from typing import List  # noqa F401
from typing import (cast, Any, Callable, Iterable, Set, Sequence,
                    Optional, Union, Mapping, Dict, Iterator, NamedTuple, Tuple)
from pprint import pformat
import logging
from copy import deepcopy
from .logtools import DEFAULT_LOG_SETTINGS, logging_config
logger = logging.getLogger(__name__)


class SettingsValidationError(ValueError):
    pass


class SettingsFileError(ValueError):
    pass


class Settings(Mapping):

    def __init__(self,
                 settings_files: Optional[Sequence[str]] = None,
                 filters: Optional[Union[str, Iterable, Mapping]] = None,
                 parser: Optional[Callable] = None,
                 parse_order: Optional[Sequence[str]] = None,
                 preparsers: Sequence = ('parse_from_file_vars',),
                 update_on_init: bool = True,
                 **env_parser_kwargs) -> None:
        """A Settings instance allows settings to be loaded from a settings file or
        environment variables.

        Attributes:
            settings_files: If set, a sequence of paths to settings files (toml
                format) from which all settings are loaded. The files are
                loaded one after another with variables set in later files
                overwriting values set in previous files.
            env_parser: `EnvParser` object handling the parsing of environment variables
            filters: Allows the settings to be filtered depending on the passed
                value. A string value will only use the settings section defined
                by the string. A ``dict`` or ``Mapping`` allows the settings to
                be limited to multiple sublevels.
            parser: If given, defines a custom function to further process the
                result of the settings. The function should take a single
                nested dictionary argument (the settings map) as an argument
                and output a nested dictionary.
            parse_order: Order in which options are parsed. If no
                ``parse_order`` argument is given upon initialization, the
                default order: ``("env", "env_file", "files", "external")`` is
                used.
            update_on_init: If set to `False` no parsing is performed upon
                initialization of the object. You will need to call update
                manually if you want load use any settings.

        Args:
            settings_files: See attribute
            filters: See attribute
            parser: See attribute
            parse_order: See attribute
            update_on_init: If set to ``True``, read all configurations upon initialization.
            **env_parser_kwargs: Arguments passed to ``EnvParser`` constructor.

        Example:
            >>> import os
            >>> os.environ['MY_APP_SECTION1_SUBSECTION1'] = 'test1'
            >>> os.environ['MY_APP_SECTION2_SUBSECTION2'] = 'test2'
            >>> os.environ['MY_APP_SECTION2_SUBSECTION3'] = 'test3'
            >>> settings_map = Settings(prefix='MY_APP')
            >>> dict(settings_map)
            {'section1': {'subsection1': 'test1'}, 'section2': {'subsection2': 'test2', 'subsection3': 'test3'}}

            Using filters we can conveniently promote a specific sections to the top level namespace

            >>> dict(Settings(prefix='MY_APP', filters='section1'))
            {'subsection1': 'test1'}

            Or gather multiple sections into the same namespace (sometimes dangerous if the subsections are not unique)

            >>> dict(Settings(prefix='MY_APP', filters=['section1', 'section2']))
            {'subsection1': 'test1', 'subsection2': 'test2', 'subsection3': 'test3'}

        See Also:
            EnvParser

        """
        self.env_parser = EnvParser(**(env_parser_kwargs or {}))
        self.parser = parser
        self.preparsers = preparsers
        self.filters = filters
        self.settings_files = settings_files
        self.external_data = {}  # type: Dict
        self._data = {}  # type: Dict
        self.parse_order = parse_order
        if update_on_init:
            self.update()

    def __repr__(self) -> str:
        return self.__class__.__qualname__ + '[\n{}\n]'.format(pformat(dict(**cast(Dict, self))))

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        yield from self._data

    @property
    def parse_order(self) -> Tuple[str, ...]:
        return self._parse_order

    @parse_order.setter
    def parse_order(self, parse_order: Sequence[str]) -> None:
        parse_options = self._parse_option_fcn_map.keys()
        if parse_order:
            if len(parse_order) != len(parse_options) or set(parse_order) != set(parse_options):
                raise ValueError('``parse_order`` must be sequence containing all strings {}. Got {} instead.'
                                 .format(list(parse_options), parse_order))
        else:
            parse_order = tuple(parse_options)
        self._parse_order = tuple(parse_order)

    @property
    def parser(self) -> Callable:
        return self._parse

    @parser.setter
    def parser(self, value: Optional[Callable]) -> None:
        if value and not callable(value):
            raise TypeError('If given, ``parser`` must be a callable')
        self._parse = value

    @property
    def preparsers(self) -> Tuple[Callable, ...]:
        return self._preparsers

    @preparsers.setter
    def preparsers(self, preparsers: Sequence) -> None:
        parsed_preparsers = []
        for preparser in preparsers:
            if isinstance(preparser, str):
                preparser = getattr(self, preparser)
            parsed_preparsers.append(preparser)
        self._preparsers = tuple(parsed_preparsers)

    @property
    def settings_files(self) -> Sequence:
        return self._settings_files

    @settings_files.setter
    def settings_files(self, files: Sequence) -> None:
        files = files or ()
        if isinstance(files, str):
            files = (files,)
        self._settings_files = list(files)

    @property
    def _parse_option_fcn_map(self) -> OrderedDict:
        return OrderedDict([
            ('env', partial(self.env_parser.parse, include_file=False)),
            ('env_file', partial(self.env_parser.parse, include_vars=False)),
            ('files', self._parse_files),
            ('external', lambda: self.external_data)
        ])

    def get_configuration_file(self, save_to=None):
        default_str = toml.dumps(OrderedDict(sorted(self._data.items())))
        default_str = default_str.replace('\n[', '\n\n[')
        if save_to:
            with open(save_to, 'w') as f:
                f.write(default_str)
        else:
            return default_str

    def update(self, d: Optional[Union[Mapping, Dict]] = None, clear_external: bool = False) -> None:
        """Updates object settings and reload files and environment variables.

        Args:
            d: Updates for settings. This is equivilant to `dict.update` except
                that the update is recursive for nested dictionaries.
            clear_external: If set to ``True`` clears all external data before applying ``d``.

        Example:
            >>> import os
            >>> os.environ['MY_APP_SECTION_VALUE'] = 'test'
            >>> settings = Settings(prefix='MY_APP')
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
        if clear_external:
            self.external_data = {}
        if d:
            update_nested(self.external_data, d)
        parse_option_fcn_map = self._parse_option_fcn_map
        for parse_option in self.parse_order:
            fcn = parse_option_fcn_map[parse_option]
            settings_map_updates = fcn()
            update_nested(settings_map, settings_map_updates)
        settings_map = self.subtree(settings_map)
        self._data = self.parse(settings_map)

    def parse(self, data) -> Dict:
        for preparser in self.preparsers:
            data = preparser(data)

        if self._parse:
            return self._parse(data)
        else:
            return data

    def setup_logging(self, logging_section='logging'):
        """Initialize logging. Uses the ``'logging'`` section from the global
        ``SETTINGS`` object if available. Otherwise uses sane defaults provided by
        the ``climatecontrol`` package

        """
        logging_settings = deepcopy(DEFAULT_LOG_SETTINGS)
        logging_settings_update = self.get(logging_section, {})
        if logging_settings_update:
            logging_settings.update(logging_settings_update)
        logging_config.dictConfig(logging_settings)

    def subtree(self, data: Dict) -> Dict:
        return subtree(data, self.filters, parent_hierarchy=['settings'])

    def click_settings_file_option(self, **kw) -> Callable:
        """See `cli_utils.click_settings_file_option`"""
        from . import cli_utils
        return cli_utils.click_settings_file_option(self, **kw)

    def _parse_files(self) -> Dict[str, Any]:
        file_settings_map = {}  # type: Dict[str, Any]
        for settings_file in self.settings_files:
            file_update = read_file(settings_file, raise_error=True)
            if file_update:
                update_nested(file_settings_map, file_update)
        return file_settings_map

    def parse_from_file_vars(self, data: Any, postfix_trigger='_from_file') -> Any:
        if not data:
            return data
        elif isinstance(data, Mapping):
            new_data = {k: v for k, v in data.items()}  # type: Any
            items = tuple(data.items())
        elif isinstance(data, Sequence) and not isinstance(data, str):
            new_data = [item for item in data]
            items = tuple(enumerate(data))
        else:
            return data
        for k, v in items:
            if isinstance(v, str) and isinstance(k, str) and k.lower().endswith(postfix_trigger):
                with open(v) as f:
                    v_from_file = f.read().rstrip()
                del new_data[k]
                new_data[k[:-len(postfix_trigger)]] = v_from_file
            elif isinstance(v, (Mapping, Sequence)):
                parsed_v = self.parse_from_file_vars(v)
                new_data[k] = parsed_v
        return new_data


EnvSetting = NamedTuple('EnvSetting', [('name', str), ('value', Mapping[str, Any])])


class EnvParser:
    """Environment variable parser

    Args:
        prefix: Only environment variables which start with this string
            (case insensitive) are considered.
        split_char: Character to split variables at. Note that if prefix
            is given, the variable name must also be seperated from the base
            with this character.
        max_depth: Maximumum depth of nested environment variables to consider.
            Note that if a file is given, the maximum depth does not apply as
            the definition is clear.

        settings_file_suffix: Suffix to identify an environment variable as a
            settings file.

            >>> env_parser=EnvParser(prefix='A', split_char='_', setting_file_suffix='SF')
            >>> env_parser.settings_file_env_var
            'A_SF'

        exclude: Environment variables to exclude. Note that the settings file
            constructed from ``settings_file_suffix`` is excluded in any case.

    Attributes:
        settings_file_env_var: Name of the settings file environment variable. Is constructed automatically.

    Examples:

        >>> env_parser = EnvParser(prefix='THIS_EXAMPLE')
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
    escape_placeholder = '$$$$'

    def __init__(self,
                 prefix: str = 'APP_SETTINGS',
                 split_char: str = '_',
                 max_depth: int = 1,
                 settings_file_suffix: str = 'SETTINGS_FILE',
                 exclude: Sequence[str] = ()) -> None:
        self.settings_file_suffix = str(settings_file_suffix)
        self.max_depth = int(max_depth)
        self.split_char = split_char
        self.prefix = prefix
        self.exclude = exclude

    @property
    def exclude(self) -> Set[str]:
        exclude = self._exclude.union({self.settings_file_env_var})
        return set(s.lower() for s in exclude)

    @exclude.setter
    def exclude(self, exclude: Sequence = ()) -> None:
        if isinstance(exclude, str):
            exclude = (exclude,)
        self._exclude = set(exclude)

    @property
    def prefix(self) -> str:
        return self._build_env_var(self._prefix) + self.split_char

    @prefix.setter
    def prefix(self, value: str):
        self._prefix = str(value)

    @property
    def settings_file_env_var(self) -> str:
        return self._build_env_var(self.prefix, self.settings_file_suffix)

    @settings_file_env_var.setter
    def settings_file_env_var(self, value: str):
        raise AttributeError('Can\'t set `settings_file_env_var` directly. Set `settings_file_suffix` instead.')

    @property
    def split_char(self) -> str:
        return self._split_char

    @split_char.setter
    def split_char(self, char: str) -> None:
        char = str(char)
        if len(char) != 1:
            raise ValueError('``split_char`` must be a single character')
        self._split_char = str(char)

    def parse(self, include_vars=True, include_file: bool = True) -> Dict[str, Any]:
        """Convert environment variables to nested dict. Note that all string inputs
        are case insensitive and all resulting keys are lower case.

        Args:
            include_file: If set to ``True`` also parses the settings file if found.

        Returns:
            nested dictionary

        Examples:
            >>> env_parser = EnvParser(prefix='THIS_EXAMPLE', max_depth=2, split_char='_')
            >>> os.environ['THIS_EXAMPLE_TESTGROUP_TESTVAR'] = 27
            >>> result_dict = env_parser.parse()
            >>> result_dict
            {'testgroup': {'testvar': 27}}

        """
        settings_map = {}  # type: dict
        for env_var, settings in self._iter_parse(include_vars=include_vars, include_file=include_file):
            logger.info('Parsed setting from env var: {}.'.format(env_var))
            update_nested(settings_map, settings)
        return settings_map

    def _build_env_var(self, *parts: str) -> str:
        return self.split_char.join(p.strip(self.split_char).upper() for p in parts)

    def _escape(self, s: str, *, inverse: bool = False) -> str:
        """Escape environment variables split char by parsing out double chars

        Examples:
            >>> 'bla_bla__this

        """
        # Choose something that can't be in an env var
        if inverse:
            args = [self.escape_placeholder, self.split_char]
        else:
            args = [self.split_char * 2, self.escape_placeholder]
        return s.replace(args[0], args[1])

    def _iter_parse(self, include_vars: bool = True, include_file: bool = True) -> Iterator[EnvSetting]:
        """Used in ``parse``"""
        if include_vars:
            for env_var in os.environ:
                env_var_low = env_var.lower()
                if env_var_low in self.exclude or not env_var_low.startswith(self.prefix.lower()):
                    continue
                escaped = self._escape(env_var_low)[len(self.prefix):]
                escaped_nested_keys = escaped.split(self.split_char, self.max_depth)
                nested_keys = [self._unescape(k) for k in escaped_nested_keys]
                if not nested_keys:
                    continue
                update = {}  # type: dict
                u = update
                for nk in nested_keys[:-1]:
                    u[nk] = {}
                    u = u[nk]
                value = self._get_env_var_value(env_var)
                u[nested_keys[-1]] = value
                if update:
                    yield EnvSetting(env_var, update)
        if include_file:
            settings_file = os.environ.get(self.settings_file_env_var)
            if settings_file:
                yield EnvSetting(self.settings_file_env_var, read_file(settings_file))

    def _unescape(self, s: str) -> str:
        """See ``escape`` with ``inverse`` set to ``True``."""
        return self._escape(s, inverse=True)

    @staticmethod
    def _get_env_var_value(env_var: str) -> Any:
        v = os.environ[env_var]
        try:
            return toml._load_value(v)[0]
        except (ValueError, TypeError, IndexError, toml.TomlDecodeError):
            return v


def read_file(path_or_content, raise_error=False) -> Dict[str, Any]:
    """Reads toml file. If ``path_or_content`` is a valid filename, load the file.
    If ``path_or_content`` represents a toml string instead (for example the
    contents of a toml file), parse the string directly.

    Args:
        path_or_content: Path to file or file contents

        raise_error: If set to ``True`` and ``path_or_content`` are neither a
            valid path nor valid toml content, raise a ``SettingsFileError``.

    Raises:
        SettingsFileError

    """
    file_data = {}  # type: Dict
    if path_or_content:
        if os.path.isfile(path_or_content):
            path = path_or_content
            with open(path) as f:
                file_data = toml.load(f)
            logger.debug('Loaded settings data from file {}'.format(path))
        elif path_or_content.lstrip().startswith('['):
            content = path_or_content
            file_data = toml.loads(content)
            logger.debug('Loaded settings from string found in settings file env var')
        elif raise_error:
            raise SettingsFileError('``path_or_content`` is neither path nor content!'
                                    '\nFailed to load:\n{}'.format(path_or_content))
        else:
            logger.debug('No settings file data loaded!')
    return file_data


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


def update_nested(d: Dict, u: Mapping) -> Dict:
    """Updates nested mapping ``d`` with nested mapping u"""
    for k, v in u.items():
        if isinstance(v, Mapping):
            r = update_nested(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d
