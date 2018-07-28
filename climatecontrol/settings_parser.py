"""Settings parser."""

from abc import ABC, abstractmethod
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
import json
import logging
import os
from pprint import pformat
from typing import List, Type, TypeVar, Tuple # noqa F401
from typing import (cast, Any, Callable, Set, Sequence,
                    Optional, Union, Mapping, Dict, Iterator, NamedTuple)
import warnings

try:
    import toml
except ImportError:
    toml = None  # type: ignore
try:
    import yaml
except ImportError:
    yaml = None  # type: ignore
try:
    import click
except ImportError:
    click = None  # type: ignore

from .logtools import DEFAULT_LOG_SETTINGS, logging_config

logger = logging.getLogger(__name__)
T = TypeVar('T')


class SettingsValidationError(ValueError):
    """Failed to validate settings."""


class SettingsLoadError(ValueError):
    """Settings file is neither path nor content."""


class ContentLoadError(SettingsLoadError):
    """Contents could not be loaded."""


class FileLoadError(SettingsLoadError):
    """Contents could not be loaded."""


class NoCompatibleLoaderFoundError(SettingsLoadError):
    """Settings could not be loaded do to format or file being incompatible."""


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
            fragment = self.preprocess_fragment(fragment)
            update_nested(settings_map, fragment)
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
        yield self._load_env_file()
        yield self._load_env()
        yield self._load_external()

    def preprocess_fragment(self, fragment: T) -> T:
        """Preprocess a settings fragment and return the new version."""
        return self._render_from_file_vars(fragment)

    def to_config(self, *, save_to: str = None, style: str = '.json') -> Optional[str]:
        """Generate a settings file from the current settings."""
        if save_to:
            style = os.path.splitext(save_to)[1]
        for loader in [TomlLoader, YamlLoader, JsonLoader]:
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
                                filepath, e.args[0])
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

    def _iter_load_files(self) -> Iterator[Dict[str, Any]]:
        for settings_file in self.settings_files:
            file_update = load_from_filepath_or_content(settings_file)
            yield file_update

    def _load_env_file(self) -> Dict[str, Any]:
        return self.env_parser.parse(include_file=True, include_vars=False)

    def _load_env(self) -> Dict[str, Any]:
        return self.env_parser.parse(include_file=False, include_vars=True)

    def _load_external(self) -> Dict[str, Any]:
        return self.external_data


EnvSetting = NamedTuple('EnvSetting', [('name', str), ('value', Mapping[str, Any])])


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
                 prefix: str = 'APP_SETTINGS',
                 split_char: str = '_',
                 implicit_depth: int = 0,
                 max_depth=None,
                 settings_file_suffix: str = 'SETTINGS_FILE',
                 exclude: Sequence[str] = ()) -> None:
        """Initialize object."""
        self.settings_file_suffix = str(settings_file_suffix)
        if max_depth is not None:
            # Use warnings module as logging probably isn't configured yet at this stage of the app.
            warnings.warn('`max_depth` is deprecated and will be removed '
                          'in next release. Please use `implicit_depth` instead.')
            self.implicit_depth = int(max_depth)
        else:
            self.implicit_depth = int(implicit_depth)
        self.split_char = split_char
        self.prefix = prefix
        self.exclude = exclude

    @property
    def exclude(self) -> Set[str]:
        """Return excluded environment variables."""
        exclude = self._exclude.union({self.settings_file_env_var})
        return set(s.lower() for s in exclude)

    @exclude.setter
    def exclude(self, exclude: Sequence = ()) -> None:
        """Set excluded environment variables."""
        if isinstance(exclude, str):
            exclude = (exclude,)
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

    def parse(self, include_vars=True, include_file: bool = True) -> Dict[str, Any]:
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
        settings_map = {}  # type: dict
        for env_var, settings in self._iter_parse(include_vars=include_vars, include_file=include_file):
            logger.info('Parsed setting from env var: %s.', env_var)
            update_nested(settings_map, settings)
        return settings_map

    def _build_env_var(self, *parts: str) -> str:
        return self.split_char.join(self._strip_split_char(p).upper() for p in parts)

    def _build_settings_update(self, keys: Sequence[str], value: Any) -> dict:
        """Build a settings update dictionary.

        Args:
            keys: Sequence of keys, each key representing a level in a nested dictionary
            value: Value that is assigned to the key at the deepest level.

        """
        update = {}  # type: dict
        u = update
        for key in keys[:-1]:
            u[key] = {}
            u = u[key]
        u[keys[-1]] = value
        return update

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
                        yield s
            elif section:
                yield section

    def _iter_parse(self, include_vars: bool = True, include_file: bool = True) -> Iterator[EnvSetting]:
        """Use in ``parse``.

        Iterate over valid environment variables and files defined by
        environment variables and yieldan envirnment settings tuple for each
        valid entry.

        See also:
            :meth:`parse`

        """
        if include_vars:
            for env_var in os.environ:
                nested_keys = list(self._iter_nested_keys(env_var))
                if not nested_keys:
                    continue
                value = self._get_env_var_value(env_var)
                update = self._build_settings_update(nested_keys, value)
                if update:
                    yield EnvSetting(env_var, update)
        if include_file:
            settings_file = os.environ.get(self.settings_file_env_var)
            if settings_file:
                yield EnvSetting(self.settings_file_env_var, load_from_filepath_or_content(settings_file))

    def _strip_split_char(self, s):
        if s.startswith(self.split_char):
            s = s[len(self.split_char):]
        elif s.endswith(self.split_char):
            s = s[:-len(self.split_char)]
        return s

    @staticmethod
    def _get_env_var_value(env_var: str) -> Any:
        """Parse an environment variable value using the toml parser."""
        v = os.environ[env_var]
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                pass
        return v


def load_from_filepath(filepath: str, allow_unknown_file_type=False):
    """Read settings file from a filepath.

    Returns:
        Data structure loaded/parsed from a compatible `FileLoader`. If no
        compatible file loaded can be found and `allow_unknown_file_type` is
        set, return the raw file contents (if `allow_unknown_file_type` is not
        set we raise an error on this case).

    Raises:
        SettingsLoadError

    """
    try:
        return load_from_filepath_or_content(filepath, _allow_content=False)
    except NoCompatibleLoaderFoundError:
        if not allow_unknown_file_type:
            raise
        # Load the raw contents from file and assume that they are to be
        # interpreted as a raw string.
        with open(filepath) as f:
            return f.read().strip()


def load_from_filepath_or_content(path_or_content: str, _allow_content=True) -> Dict[str, Any]:
    """Read settings file from a filepath or from a string representing the file contents.

    If ``path_or_content`` is a valid filename, load the file. If
    ``path_or_content`` represents a json, yaml or toml string instead (the
    contents of a json/toml/yaml file), parse the string directly.

    Note that json, yaml and toml files are read. If ``path_or_content`` is a
    string, we will try to guess what file type you meant. Note that this last
    feature is not perfect!

    Args:
        path_or_content: Path to file or file contents

    Raises:
        FileLoadError: when an error occurs during the loading of a file.
        ContentLoadError: when an error occurs during the loading of file contents.
        NoCompatibleLoaderFoundError: when no compatible loader was found for
            this filepath or content type.

    """
    file_data = {}  # type: Dict
    if not path_or_content:
        return file_data
    for loader in FileLoader.registered_loaders:
        if loader.is_path(path_or_content):
            file_data = loader.from_path(path_or_content)
            break
        if _allow_content and loader.is_content(path_or_content):
            file_data = loader.from_content(path_or_content)
            break
    else:
        raise NoCompatibleLoaderFoundError('Failed to load settings. No compatible loader: {}'.format(path_or_content))
    return file_data


def update_nested(d: Dict, u: Mapping) -> Dict:
    """Update nested mapping ``d`` with nested mapping ``u``."""
    for k, v in u.items():
        if isinstance(v, Mapping):
            r = update_nested(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


class FileLoader(ABC):
    """Abstract base class for file/file content loading."""

    valid_file_extensions = ()  # type: Tuple[str, ...]
    valid_content_start = ()  # type: Tuple
    registered_loaders = []  # type: List[FileLoader]

    @classmethod
    @abstractmethod
    def from_path(cls, path: str) -> Any:
        """Load serialized data from file at path."""

    @classmethod
    @abstractmethod
    def from_content(cls, content: str) -> Any:
        """Load serialized data from content."""

    @classmethod
    @abstractmethod
    def to_content(cls, data: Mapping) -> str:
        """Serialize data to string."""

    @classmethod
    def is_content(cls, path_or_content):
        """Check if argument is file content."""
        return any(path_or_content.lstrip().startswith(s) for s in cls.valid_content_start)

    @classmethod
    def is_path(cls, path_or_content: str):
        """Check if argument is a valid file path.

        If `only_existing` is set to ``True``, paths to files that don't exist
        will also return ``False``.
        """
        return (
            len(str(path_or_content).strip().splitlines()) == 1 and
            (os.path.splitext(path_or_content)[1] in cls.valid_file_extensions)
        )

    @classmethod
    def register(cls, class_to_register):
        """Register class as a valid file loader."""
        cls.registered_loaders.append(class_to_register)
        return class_to_register


@FileLoader.register
class JsonLoader(FileLoader):
    """FileLoader for .json files."""

    valid_file_extensions = ('.json',)
    valid_content_start = ('{',)

    @classmethod
    def from_content(cls, content: str) -> Any:
        """Load json from string."""
        return json.loads(content)

    @classmethod
    def from_path(cls, path: str):
        """Load json from file at path."""
        with open(path) as f:
            return json.load(f)

    @classmethod
    def to_content(cls, data: Mapping) -> str:
        """Serialize mapping to string."""
        return json.dumps(data, indent=4)


@FileLoader.register
class YamlLoader(FileLoader):
    """FileLoader for .yaml files."""

    valid_file_extensions = ('.yml', '.yaml')
    valid_content_start = ('---',)

    @classmethod
    def from_content(cls, content: str) -> Any:
        """Load data from yaml formatted string."""
        cls._check_yaml()
        return yaml.safe_load(content)

    @classmethod
    def from_path(cls, path: str) -> Any:
        """Load data from path containing a yaml file."""
        cls._check_yaml()
        with open(path) as f:
            return yaml.safe_load(f)

    @classmethod
    def to_content(cls, data: Mapping) -> str:
        """Serialize mapping to string."""
        cls._check_yaml()
        s = yaml.safe_dump(data, default_flow_style=False)
        s = '---\n' + s
        return s

    @staticmethod
    def _check_yaml():
        if yaml is None:
            raise ImportError('"pyyaml" package needs to be installed to parse yaml files.')


@FileLoader.register
class TomlLoader(FileLoader):
    """FileLoader for .toml files."""

    valid_file_extensions = ('.toml', '.ini', '.config', '.cfg')
    valid_content_start = ('[',)  # TODO: This only works if settings file has sections.

    @classmethod
    def from_content(cls, content: str) -> Any:
        """Load toml from string."""
        cls._check_toml()
        return toml.loads(content)

    @classmethod
    def from_path(cls, path: str):
        """Load toml from file at path."""
        cls._check_toml()
        with open(path) as f:
            return toml.load(f)

    @classmethod
    def to_content(cls, data: Mapping) -> str:
        """Serialize mapping to string."""
        cls._check_toml()
        s = toml.dumps(OrderedDict(sorted(data.items())))
        s = s.replace('\n[', '\n\n[')
        return s

    @staticmethod
    def _check_toml():
        if toml is None:
            raise ImportError('"toml" package needs to be installed to parse toml files.')
