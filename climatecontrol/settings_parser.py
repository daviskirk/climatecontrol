"""Settings parser."""

import json
import logging
import os
from contextlib import contextmanager
from copy import deepcopy
from pprint import pformat
from typing import List, Type, TypeVar, Tuple # noqa F401
from typing import (cast, Any, Callable, Sequence,
                    Optional, Union, Mapping, Dict, Iterator, NamedTuple)

try:
    import click
except ImportError:
    click = None  # type: ignore

from .env_parser import EnvParser
from .exceptions import SettingsValidationError  # noqa: F401  # Import here for backwards compatability.
from .file_loaders import FileLoader, load_from_filepath, load_from_filepath_or_content
from .logtools import DEFAULT_LOG_SETTINGS, logging_config
from .utils import iter_hierarchy, update_nested


logger = logging.getLogger(__name__)
T = TypeVar('T')


Fragment = NamedTuple('Fragment', [('data', Dict[str, Any]), ('source', str)])


class Settings(Mapping):
    """A Settings instance allows settings to be loaded from a settings file or environment variables.

    Attributes:
        settings_files: If set, a sequence of paths to settings files (toml
            format) from which all settings are loaded. The files are
            loaded one after another with variables set in later files
            overwriting values set in previous files.
        env_parser: `EnvParser` object handling the parsing of environment variables
        parser: If given, defines a custom function to further process the
            result of the settings. The function should take a single
            nested dictionary argument (the settings map) as an argument
            and output a nested dictionary.
        update_on_init: If set to `False` no parsing is performed upon
            initialization of the object. You will need to call update
            manually if you want load use any settings.

    Args:
        settings_files: See attribute
        parser: See attribute
        update_on_init: If set to ``True``, read all configurations upon initialization.
        **env_parser_kwargs: Arguments passed to :class:`EnvParser` constructor.

    Example:
        >>> import os
        >>> os.environ['MY_APP_VALUE0'] = 'test0'
        >>> os.environ['MY_APP_SECTION1_SUB1'] = 'test1'
        >>> os.environ['MY_APP_SECTION2_SUB2'] = 'test2'
        >>> os.environ['MY_APP_SECTION2_SUB3'] = 'test3'
        >>> settings_map = Settings(prefix='MY_APP', implicit_depth=1)
        >>> dict(settings_map)
        {'value0': 'test0', 'section1': {'subsection1': 'test1'}, 'section2': {'sub2': 'test2', 'sub3': 'test3'}}

    See Also:
        EnvParser

    """

    def __init__(self,
                 settings_files: Optional[Sequence[str]] = None,
                 parser: Optional[Callable] = None,
                 update_on_init: bool = True,
                 **env_parser_kwargs) -> None:
        """Initialize settings object."""
        self.env_parser = EnvParser(**(env_parser_kwargs or {}))
        self.parser = parser
        self.settings_files = settings_files
        self.external_data = {}  # type: Dict
        self._data = {}  # type: Mapping

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
    def parser(self) -> Optional[Callable]:
        """Return settings parser function."""
        return self._parse

    @parser.setter
    def parser(self, value: Optional[Callable]) -> None:
        """Set the settings parser function."""
        if value and not callable(value):
            raise TypeError('If given, ``parser`` must be a callable')
        self._parse = value

    @property
    def settings_files(self) -> Sequence:
        """Return current settings files."""
        return self._settings_files

    @settings_files.setter
    def settings_files(self, files: Sequence) -> None:
        """Set settings files to use when parsing settings."""
        files = files or ()
        if isinstance(files, str):
            files = (files,)
        self._settings_files = list(files)

    def update(self, d: Optional[Union[Mapping, Dict]] = None, clear_external: bool = False) -> None:
        """Update object settings and reload files and environment variables.

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
        for fragment in self.iter_source_loaders():
            fragment = Fragment(self.preprocess_fragment(fragment.data), fragment.source)
            self._log_assignments(fragment)
            update_nested(settings_map, fragment.data)
        self._data = self.parse(settings_map)

    def parse(self, data: Mapping) -> Mapping:
        """Parse data into settings.

        Args:
            data: Raw mapping to be parsed

        Returns:
            Parsed data that has run through all preparsers and the `Settings`.

        """
        if self._parse:
            return self._parse(data)
        else:
            return data

    def setup_logging(self, logging_section: str = 'logging') -> None:
        """Initialize logging.

        Uses the ``'logging'`` section from the global ``SETTINGS`` object if
        available. Otherwise uses sane defaults provided by the
        ``climatecontrol`` package.

        """
        logging_settings = deepcopy(DEFAULT_LOG_SETTINGS)
        logging_settings_update = self.get(logging_section, {})
        if logging_settings_update:
            logging_settings.update(logging_settings_update)
        logging_config.dictConfig(logging_settings)

    def click_settings_file_option(self, **kw) -> Callable:
        """See :func:`cli_utils.click_settings_file_option`."""
        from . import cli_utils
        return cli_utils.click_settings_file_option(self, **kw)

    def iter_source_loaders(self) -> Iterator:
        """Iterate over functions to load settings from various sources.

        Yields:
            Each yielded item represents an updates to the settings data.

        """
        yield from self._iter_load_files()
        yield self._load_env()
        yield self._load_external()

    def preprocess_fragment(self, fragment: T) -> T:
        """Preprocess a settings fragment and return the new version."""
        return self._render_from_file_vars(fragment)

    def to_config(self, *, save_to: str = None, style: str = '.json') -> Optional[str]:
        """Generate a settings file from the current settings."""
        if save_to:
            style = os.path.splitext(save_to)[1]
        for loader in FileLoader.registered_loaders:
            if style in loader.valid_file_extensions:
                s = loader.to_content(self._data)
                break
        else:
            raise ValueError('Not a valid style / file extension: {}'.format(style))

        if save_to:
            with open(save_to, 'w') as f:
                f.write(s)
            return None
        else:
            return s

    @contextmanager
    def temporary_changes(self):
        """Open a context where any changes to the settings are rolled back on context exit.

        This context manager can be used for testing or to temporarily change
        settings.

        Example:
            >>> from climatecontrol.settings_parser import Settings
            >>> settings = Settings()
            >>> settings.update({'a': 1})
            >>> with settings.temporary_changes():
            ...     settings.update({'a': 2})
            ...     assert settings['a'] == 2
            >>> assert settings['a'] == 1

        """
        archived_settings = deepcopy(self._data)
        archived_settings_files = deepcopy(self._settings_files)
        archived_external_data = deepcopy(self.external_data)
        yield self
        self._data = archived_settings
        self._settings_files = archived_settings_files
        self.external_data = archived_external_data

    def _render_from_file_vars(self, data: T, postfix_trigger='_from_file') -> T:
        """Read and replace settings values from content local files.

        Args:
            data: Given subset of settings data (or entire settings mapping)
            postfix_trigger: Optionally configurable string to trigger a local
                file value. If a key is found which ends with this string, the
                value is assumed to be a file path and the settings value will
                be set to the content of the file.

        Returns:
            An updated copy of `data` with keys and values replaced accordingly.

        """
        if not data:
            return data
        elif isinstance(data, Mapping):
            new_data = {k: v for k, v in data.items()}  # type: Any
            items = tuple(data.items())
        elif isinstance(data, Sequence) and not isinstance(data, str):
            new_data = [item for item in data]
            items = tuple(enumerate(data))
        else:
            return cast(T, data)
        for k, v in items:
            if isinstance(v, str) and isinstance(k, str) and k.lower().endswith(postfix_trigger):
                key_with_postfix = k
                filepath = v
                # Reassign value (v) using the contents of the file.
                try:
                    v = load_from_filepath(filepath, allow_unknown_file_type=True)
                except FileNotFoundError as e:
                    logger.info('Error while trying to load variable from file: %s. (%s) Skipping...',
                                filepath, e)
                else:
                    k = k[:-len(postfix_trigger)]  # Use the "actual" key from here on.
                    new_data[k] = v
                    logger.info('Settings key %s set to contents of file %s', k, v)
                finally:
                    del new_data[key_with_postfix]
            if isinstance(v, (Mapping, Sequence)) and not isinstance(v, str):
                parsed_v = self._render_from_file_vars(v)
                new_data[k] = parsed_v
        return new_data

    def _iter_load_files(self) -> Iterator[Fragment]:
        for settings_file in self.settings_files:
            file_update = load_from_filepath_or_content(settings_file)
            yield Fragment(data=file_update, source=str(settings_file))

    def _load_env(self) -> Fragment:
        return Fragment(self.env_parser.parse(),
                        'environment variables')

    def _load_external(self) -> Fragment:
        return Fragment(self.external_data, 'external')

    def _log_assignments(self, fragment: Fragment) -> None:
        messages = []
        for levels in iter_hierarchy(fragment.data):
            if levels:
                message = '.'.join(levels)
                messages.append(message)
        if messages:
            logger.debug('Assigned settings%s: %s',
                         ' from ' + str(fragment.source) if fragment.source else '',
                         json.dumps(messages))
