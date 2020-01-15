"""Settings parser."""

from enum import Enum
import itertools
import logging
import warnings
import os
from contextlib import contextmanager
from copy import deepcopy
from pprint import pformat
from typing import (  # noqa: F401
    Any, Callable, Dict, Iterable, Iterator, List,
    Mapping, MutableMapping, MutableSequence, Optional,
    Sequence, TypeVar, Union, cast
)

try:
    import click
except ImportError:
    click = None  # type: ignore

from .env_parser import EnvParser
from .exceptions import SettingsValidationError  # noqa: F401  # Import here for backwards compatability.
from .file_loaders import (
    FileLoader, NoCompatibleLoaderFoundError, iter_load, load_from_filepath
)
from .fragment import Fragment
from .logtools import DEFAULT_LOG_SETTINGS, logging_config
from .utils import merge_nested, parse_as_json_if_possible


logger = logging.getLogger(__name__)
T = TypeVar('T')


class Settings(Mapping):
    """A Settings instance allows settings to be loaded from a settings file or environment variables.

    Attributes:
        settings_files: If set, a sequence of paths to settings files (json, yaml or toml
            format) from which all settings are loaded. The files are
            loaded one after another with variables set in later files
            overwriting values set in previous files.
        env_parser: `EnvParser` object handling the parsing of environment variables
        parser: If given, defines a custom function to further process the
            result of the settings. The function should take a single
            nested dictionary argument (the settings map) as an argument
            and output a nested dictionary.
        update_on_init: (Deprecated) If set to `False` no parsing is performed upon
            initialization of the object. You will need to call update
            manually if you want load use any settings.

    Args:
        settings_files: See attribute
        parser: See attribute
        update_on_init: (Deprecated) If set to ``True``, read all configurations upon initialization.
        **env_parser_kwargs: Arguments passed to :class:`EnvParser` constructor.

    Example:
        >>> import os
        >>> os.environ['MY_APP_VALUE0'] = 'test0'
        >>> os.environ['MY_APP_SECTION1_SUB1'] = 'test1'
        >>> os.environ['MY_APP_SECTION2_SUB2'] = 'test2'
        >>> os.environ['MY_APP_SECTION2_SUB3'] = 'test3'
        >>> settings_manager = SettingsManager(prefix='MY_APP')
        >>> dict(settings_manager)
        {'value0': 'test0', 'section1': {'subsection1': 'test1'}, 'section2': {'sub2': 'test2', 'sub3': 'test3'}}

    See Also:
        EnvParser

    """

    def __init__(self,
                 settings_files: Sequence[str] = (),
                 parser: Optional[Callable[[Mapping], Mapping]] = None,
                 update_on_init: Optional[bool] = None,
                 **env_parser_kwargs) -> None:
        """Initialize settings object."""
        self.env_parser = EnvParser(**(env_parser_kwargs or {}))
        self.parser = parser
        self.settings_files = settings_files
        self.update_data = {}  # type: dict
        self.fragments = []  # type: List[Fragment]
        self._data = {}  # type: Mapping
        self._initialized = False  # type: bool

        if update_on_init is not None:
            warnings.warn('setting update_on_init is deprecated', DeprecationWarning)
        if update_on_init:
            self.update()

    def __repr__(self) -> str:
        return self.__class__.__qualname__ + '[\n{}\n]'.format(pformat(dict(**cast(Dict, self))))

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, key: str) -> Any:
        if not self._initialized:
            self.update()
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        if not self._initialized:
            self.update()
        yield from self._data

    @property
    def parser(self) -> Optional[Callable[[Mapping], Mapping]]:
        """Return settings parser function."""
        return self._parse

    @parser.setter
    def parser(self, value: Optional[Callable[[Mapping], Mapping]]) -> None:
        """Set the settings parser function."""
        if value and not callable(value):
            raise TypeError('If given, ``parser`` must be a callable')
        self._parse = value

    @property
    def settings_files(self) -> Sequence:
        """Return current settings files."""
        return self._settings_files

    @settings_files.setter
    def settings_files(self, files: Union[str, Iterable[str]]) -> None:
        """Set settings files to use when parsing settings."""
        files = files or ()
        if isinstance(files, str):
            files = (files,)
        self._settings_files = list(files)

    @property
    def update_log(self) -> str:
        """Log of all each loaded settings variable."""
        def iter_fragment_lines(fragment: Fragment) -> Iterator[str]:
            for leaf in fragment.iter_leaves():
                action = 'removed' if leaf.value == REMOVED else 'loaded'
                yield action + ' ' + '.'.join(str(p) for p in leaf.path) + ' from ' + str(leaf.source)

        lines = itertools.chain.from_iterable(
            iter_fragment_lines(fragment) for fragment in self.fragments
        )
        result = '\n'.join(lines)
        return result

    def update(self, d: Optional[Mapping] = None, clear: bool = False) -> None:
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
        # External data is any data that was explicitely assigned through a
        # call to :meth:`update`.
        update_data = {} if clear else self.update_data
        if d:
            update_data = merge_nested(update_data, d)

        # Compile a list of fragments
        fragments = []

        for fragment in itertools.chain(
                self._iter_load_files(),
                self.env_parser.iter_load(),
                [Fragment(value=update_data, source='external')]
        ):
            fragments.append(fragment)
            fragments.extend(self.process_fragment(fragment))

        # Combine the fragments into one final fragment
        combined_fragment = None  # type: Optional[Fragment]
        for fragment in fragments:
            if combined_fragment is None:
                combined_fragment = fragment
            else:
                combined_fragment = combined_fragment.merge(fragment)

        # Obtain settings map
        if combined_fragment is None:
            settings_map = {}  # type: dict
        else:
            settings_map = combined_fragment.expand_value_with_path()
            clean_removed_items(settings_map)

        self._data = self.parse(settings_map)

        # If parsing was successfull, update external data and fragments.
        self.update_data = update_data
        self.fragments = fragments
        self._initialized = True

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
        logging_settings = DEFAULT_LOG_SETTINGS
        logging_settings_update = self.get(logging_section)
        if logging_settings_update:
            logging_settings = merge_nested(logging_settings, logging_settings_update)
        logging_config.dictConfig(logging_settings)

    def click_settings_file_option(self, **kw) -> Callable[..., Any]:
        """See :func:`cli_utils.click_settings_file_option`."""
        from . import cli_utils
        return cli_utils.click_settings_file_option(self, **kw)

    def process_fragment(self, fragment: Fragment) -> Iterator[Fragment]:
        """Preprocess a settings fragment and return the new version."""
        processors = [
            replace_from_file_vars, replace_from_env_vars
        ]  # type: List[Callable[[Fragment], Iterator[Fragment]]]
        for process in processors:
            for new_fragment in process(fragment):
                yield new_fragment
                yield from self.process_fragment(new_fragment)

    def to_config(self, *, save_to: str = None, style: str = '.json') -> Optional[str]:
        """Generate a settings file from the current settings."""
        if save_to:
            style = os.path.splitext(save_to)[1]
        for loader in FileLoader.registered_loaders:
            if style in loader.valid_file_extensions:
                s = loader.to_content(dict(self))
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
        archived_settings_files = deepcopy(self.settings_files)
        archived_update_data = deepcopy(self.update_data)
        yield self
        self._data = archived_settings
        self.settings_files = archived_settings_files
        self.update_data = archived_update_data

    def _iter_load_files(self) -> Iterator[Fragment]:
        for entry in self.settings_files:
            yield from iter_load(entry)


def replace_from_env_vars(fragment: Fragment, postfix_trigger: str = '_from_env') -> Iterator[Fragment]:
    """Read and replace settings values from environment variables.

    Args:
        fragment: Fragment to process
        postfix_trigger: Optionally configurable string to trigger a
            replacement with an environment variable. If a key is found which
            ends with this string, the value is assumed to be the name of an
            environemtn variable and the settings value will be set to the
            contents of that variable.

    Yields:
        Additional fragments to patch the original fragment.

    """
    for leaf in fragment.iter_leaves():
        if not leaf.path or leaf.value == REMOVED:
            continue
        key, value = leaf.path[-1], leaf.value
        if isinstance(value, str) and isinstance(key, str) and key.lower().endswith(postfix_trigger):
            env_var = value
            yield leaf.clone(value=REMOVED)
            try:
                env_var_value = os.environ[env_var]
            except KeyError as e:
                logger.info('Error while trying to load environment variable: %s. (%s) Skipping...',
                            env_var, e)
            else:
                new_key = key[:-len(postfix_trigger)]
                new_value = parse_as_json_if_possible(env_var_value)
                yield leaf.clone(value=new_value, path=list(leaf.path[:-1]) + [new_key])


def replace_from_file_vars(fragment: Fragment, postfix_trigger: str = '_from_file') -> Iterator[Fragment]:
    """Read and replace settings values from content local files.

    Args:
        fragment: Fragment to process
        postfix_trigger: Optionally configurable string to trigger a local
            file value. If a key is found which ends with this string, the
            value is assumed to be a file path and the settings value will
            be set to the content of the file.

    Yields:
        Additional fragments to patch the original fragment.

    """
    for leaf in fragment.iter_leaves():
        if not leaf.path or leaf.value == REMOVED:
            continue
        key, value = leaf.path[-1], leaf.value
        if isinstance(value, str) and isinstance(key, str) and key.lower().endswith(postfix_trigger):
            filepath = value
            yield leaf.clone(value=REMOVED)
            try:
                try:
                    new_value = load_from_filepath(filepath)  # type: Any
                except NoCompatibleLoaderFoundError:
                    # just load as plain text file and interpret as string
                    with open(filepath) as f:
                        new_value = f.read().strip()
            except FileNotFoundError as e:
                logger.info('Error while trying to load variable from file: %s. (%s) Skipping...',
                            filepath, e)
            else:
                new_key = key[:-len(postfix_trigger)]
                yield leaf.clone(value=new_value, path=list(leaf.path[:-1]) + [new_key])


def clean_removed_items(obj):
    """Remove all keys that contain a removed key indicated by a :data:``REMOVED`` object."""
    if isinstance(obj, MutableMapping):
        items = obj.items()  # type: Any
    elif isinstance(obj, MutableSequence):
        items = enumerate(obj)
    else:
        return

    keys_to_remove = []
    for key, value in items:
        if value == REMOVED:
            keys_to_remove.append(key)
        else:
            clean_removed_items(value)

    for key in keys_to_remove:
        del obj[key]


class _Removed(Enum):
    """Object representing an empty item."""

    REMOVED = None

    def __repr__(self):
        return '<REMOVED>'  # pragma: nocover


REMOVED = _Removed.REMOVED
