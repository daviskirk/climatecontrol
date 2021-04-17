"""Climate parser."""
import logging
from contextlib import contextmanager
from copy import deepcopy
from itertools import chain
from pathlib import Path
from pprint import pformat
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

import wrapt

from climatecontrol.constants import REMOVED
from climatecontrol.env_parser import EnvParser
from climatecontrol.file_loaders import FileLoader, iter_load
from climatecontrol.fragment import Fragment, FragmentPath
from climatecontrol.logtools import DEFAULT_LOG_SETTINGS, logging_config
from climatecontrol.processors import (
    replace_from_content_vars,
    replace_from_env_vars,
    replace_from_file_vars,
)
from climatecontrol.utils import merge_nested

try:
    import click
except ImportError:
    click = None  # type: ignore


logger = logging.getLogger(__name__)
T = TypeVar("T", bound=wrapt.ObjectProxy)


class ObjectProxy(wrapt.ObjectProxy):
    """Simple object proxy with added representation of wrapped object."""

    def __repr__(self) -> str:
        return repr(self.__wrapped__)


class SettingsItem(ObjectProxy):
    """Object proxy for representing a nested settings item.

    An object proxy acts like the underlying but adds functionality on top.
    In this case the SettingsItem object ensures immutability of the object as
    changing a settings object can have unexpected behaviour as the underlying
    :class:`Climate` data is not changed and updates the same way.

    The settings item object ensures that any "nested" objects are also
    represented as :class:`SettingsItem` object.

    Examples:

        >>> climate = Climate()
        >>> s = SettingsItem({'a': 5, 'b': {'c': 6}}, climate, FragmentPath([]))
        >>> s
        {'a': 5, 'b': {'c': 6}}
        >>> s.a
        5
        >>> s.b
        {'c': 6}
        >>> type(s.b)
        <class 'climatecontrol.core.SettingsItem'>

    """

    def __init__(self, wrapped, climate: "Climate", path: FragmentPath) -> None:
        super().__init__(wrapped)
        self._self_climate = climate
        self._self_path = path

    def __repr__(self) -> str:
        self._self_climate.ensure_initialized()
        return super().__repr__()

    def __getattr__(self, key):
        self._self_climate.ensure_initialized()
        try:
            result = getattr(self.__wrapped__, key)
        except AttributeError as e:
            try:
                result = self.__wrapped__[key]
            except (TypeError, KeyError):
                raise e
        if self._self_is_mutable(result):
            return type(self)(
                result,
                self._self_climate,
                type(self._self_path)(list(self._self_path) + [key]),
            )
        return result

    def __deepcopy__(self: T, memo: dict) -> T:
        return type(self)(
            deepcopy(self.__wrapped__, memo), self._self_climate, self._self_path
        )

    def __setattr__(self, key: str, value) -> None:
        is_proxy_key = hasattr(key, "startswith") and key.startswith("_self_")
        if not is_proxy_key:
            raise TypeError(f"{type(self)} does not support attribute assignment")
        super().__setattr__(key, value)

    def __delattr__(self, key: str) -> None:
        is_proxy_key = hasattr(key, "startswith") and key.startswith("_self_")
        if not is_proxy_key:
            raise TypeError(f"{type(self)} does not support attribute deletion")
        super().__delattr__(key)

    def __getitem__(self, key):
        self._self_climate.ensure_initialized()
        result = self.__wrapped__.__getitem__(key)
        if self._self_is_mutable(result):
            return type(self)(
                result,
                self._self_climate,
                type(self._self_path)(list(self._self_path) + [key]),
            )
        return result

    def __setitem__(self, key, value) -> None:
        raise TypeError(f"{type(self)} does not support item assignment")

    def __delitem__(self, key) -> None:
        raise TypeError(f"{type(self)} does not support item deletion")

    @classmethod
    def _self_is_mutable(cls, value: Any) -> bool:
        return isinstance(value, (MutableMapping, MutableSequence))


class Climate:
    """A Climate instance allows settings to be loaded from a settings file or environment variables.

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

    Args:
        settings_files: See attribute
        parser: See attribute
        **env_parser_kwargs: Arguments passed to :class:`EnvParser` constructor.

    Example:
        >>> import os
        >>> os.environ['MY_APP_VALUE0'] = 'test0'
        >>> os.environ['MY_APP_SECTION1__SUB1'] = 'test1'
        >>> os.environ['MY_APP_SECTION2__SUB2'] = 'test2'
        >>> os.environ['MY_APP_SECTION2__SUB3'] = 'test3'
        >>> climate = Climate(prefix='MY_APP')
        >>> dict(climate.settings)
        {'value0': 'test0', 'section1': {'sub1': 'test1'}, 'section2': {'sub2': 'test2', 'sub3': 'test3'}}

    See Also:
        EnvParser

    """

    settings_files: List[Union[str, Path]]
    _combined_fragment: Fragment
    _updates: List
    _fragments: List[Fragment]
    _data: Any
    _initialized: bool
    _processors: Tuple[Callable[[Fragment], Iterator[Fragment]], ...] = (
        replace_from_file_vars,
        replace_from_env_vars,
        replace_from_content_vars,
    )

    def __init__(
        self,
        settings_files: Union[str, Path, Sequence[Union[str, Path]]] = (),
        parser: Optional[Callable[[Mapping], Mapping]] = None,
        **env_parser_kwargs: Any,
    ) -> None:
        """Initialize settings object."""
        self.env_parser = EnvParser(**(env_parser_kwargs or {}))
        self.parser = parser
        if isinstance(settings_files, (str, Path)):
            self.settings_files = [settings_files]
        else:
            self.settings_files = list(settings_files)
        self._updates = []
        self._fragments = []
        self._initialized = False
        # We use an object proxy here so that the referene to the object is always the same.
        # Note that instead of assigning _data directly, we reinitialize it using self._set_data(new_obj).
        self._data = ObjectProxy(None)
        self._combined_fragment = Fragment(None)

    def __repr__(self) -> str:
        return self.__class__.__qualname__ + "[\n{}\n]".format(pformat(self._data))

    @property
    def parser(self) -> Optional[Callable[[Mapping], Mapping]]:
        """Return settings parser function."""
        return self._parse

    @parser.setter
    def parser(self, value: Optional[Callable[[Mapping], Mapping]]) -> None:
        """Set the settings parser function."""
        self._parse = value

    @property
    def settings(self) -> Any:
        """Return a settings item proxy for easy access to settings hierarchy."""
        self.ensure_initialized()
        return SettingsItem(self._data, self, FragmentPath())

    @property
    def inferred_settings_files(self) -> List[Path]:
        """Infer settings files from current directory and parent directories.

        1. Search upward until a repository root is found (symbolized by a get repository)
        2. Along the directories starting with the project root up until the current directory search for the following files:
          * Files matching the pattern: `*<prefix>*settings*<loadable filetype>`
          * Files matching the pattern above but within subdirectories named `*<prefix>*settings*`
          * Files matching the pattern above in any recursive subdirectories of the subdirectory mentioned above

        Note that the prefix is lower cased even if it is given as upper or mixed case.

        Given a filestructure:

        ::


           |-- myuser/
           |-- unused_climatecontrol_settings.yaml
           |-- myrepo/
               |-- .git/
               |-- base-climatecontrol-settings.json
               |-- climatecontrol_settings/
                   |-- 01.toml
                   |-- 02.yml
                   |-- 0/
                       |-- settings.yml
                   |-- 1/
                       |-- settings.json
               |-- myproject/
                   |-- climatecontrol.general.settings.yaml
                   |-- mysubproject/
                       |-- .climatecontrol.settings.yaml

        and assuming the current working directory is `myuser/myproject/mysubproject`, the inferred settings files would be:

        ::
            myuser/myrepo/base-climatecontrol-settings.json
            myuser/myrepo/climatecontrol_settings/01.toml
            myuser/myrepo/climatecontrol_settings/02.yml
            myuser/myrepo/climatecontrol_settings/0/settings.yml
            myuser/myrepo/climatecontrol_settings/1/settings.json
            myuser/myproject/climatecontrol.general.settings.yaml
            myuser/mysubproject/.climatecontrol.settings.yaml

        """
        prefix = self.env_parser.prefix.strip(self.env_parser.split_char).lower()
        base_pattern = f"*{prefix}*settings"
        extensions = [
            ext
            for loader in FileLoader.registered_loaders
            for ext in loader.valid_file_extensions
        ]

        def find_settings_files(path: Path, glob_pattern: str, recursive=False):
            glob = path.rglob if recursive else path.glob
            filepaths = []
            for ext in extensions:
                for filepath in glob(f"{glob_pattern}{ext}"):
                    if filepath.is_file():
                        filepaths.append(filepath)
            return sorted(filepaths)

        # Find all directories between current directory and project root
        search_directories: List[Path] = []
        project_root_candidates = [
            ".git",
            ".hg",
            "setup.py",
            "requirements.txt",
            "environment.yml",
            "environment.yaml",
            "pyproject.toml",
        ]
        current_path: Path = Path(".")
        while True:
            search_directories.append(current_path)
            new_current_path = current_path / ".."
            if (
                any(
                    (current_path / candidate).exists()
                    for candidate in project_root_candidates
                )
                or not new_current_path.is_dir()
                or new_current_path.resolve() == current_path.resolve()
            ):
                break
            current_path = new_current_path

        # Iterate over all directories and find files
        filepaths: List[Path] = []
        for directory in reversed(search_directories):
            filepaths.extend(find_settings_files(directory, base_pattern))
            for sub_dir in directory.glob(base_pattern):
                if not sub_dir.is_dir():
                    continue
                # Use all files with valid file extensions if already in settings directory.
                filepaths.extend(find_settings_files(sub_dir, "*", recursive=True))

        return filepaths

    @property
    def update_log(self) -> str:
        """Log of all each loaded settings variable."""

        def iter_fragment_lines(fragment: Fragment) -> Iterator[str]:
            for leaf in fragment.iter_leaves():
                action = "removed" if leaf.value == REMOVED else "loaded"
                yield action + " " + ".".join(
                    str(p) for p in leaf.path
                ) + " from " + str(leaf.source)

        lines = chain.from_iterable(
            iter_fragment_lines(fragment) for fragment in self._fragments
        )
        result = "\n".join(lines)
        return result

    def clear(self) -> None:
        """Remove all data and reset to initial state."""
        self._updates.clear()
        self._fragments.clear()
        self._initialized = False  # next access should reload all fragments

    def ensure_initialized(self):
        """Ensure that object is initialized and reload if it is not."""
        if not self._initialized:
            self.reload()

    def reload(self) -> None:
        """Reload data from all sources.

        Updates that were applied manually (through code) are not discarded. Use
        :method:`clear` for that.
        """
        parsed, combined, fragments = self._stateless_reload(self._updates)
        self._set_state(parsed, combined, fragments, self._updates)

    def update(
        self, update_data: Mapping = None, path: Union[str, int, Sequence] = None
    ) -> None:
        """Update settings using a patch dictionary.

        Args:
            update_data: Updates for settings. This is equivilant to `dict.update` except
                that the update is recursive for nested dictionaries.

        Example:
            >>> import os
            >>> os.environ['CLIMATECONTROL_VALUE'] = 'test'
            >>> climate = Climate()
            >>> dict(climate.settings)
            {'value': 'test'}
            >>>
            >>> # now update the settings
            >>> climate.update({'new_value': 'new'})
            >>> climate.settings.value
            'test'
            >>> climate.settings.new_value
            'new'

            Alternatively a path can be specified that will be expanded:

            >>> climate.update('test', 'level_1.level_2.0.inlist')
            >>> climate.settings.level_1.level_2[0].inlist
            'test'


        """
        if path is not None:
            update_data = FragmentPath.from_spec(path).expand(update_data)
        if not self._initialized:
            new_updates = (
                self._updates + [update_data] if update_data else self._updates
            )
            parsed, combined, fragments = self._stateless_reload(new_updates)
            self._set_state(parsed, combined, fragments, new_updates)
            return
        if not update_data:
            return
        # we can start directly from the previously consolidated fragment
        base_fragments: List[Fragment] = [self._combined_fragment]
        new_updates = [update_data]
        update_fragments = list(self._iter_update_fragments(new_updates))
        combined = self._combine_fragments(chain(base_fragments, update_fragments))
        expanded = combined.expand_value_with_path()
        clean_removed_items(expanded)
        parsed = self.parse(expanded)

        fragments = self._fragments + update_fragments
        updates = self._updates + new_updates

        self._set_state(parsed, combined, fragments, updates)

    def parse(self, data: Any) -> Any:
        """Parse data into settings.

        Args:
            data: Raw mapping to be parsed

        Returns:
            Parsed data that has run through all preparsers and the `Climate`.

        """
        if self._parse:
            return self._parse(data)
        else:
            return data

    def setup_logging(self, logging_section: str = "logging") -> None:
        """Initialize logging.

        Uses the ``'logging'`` section from the global ``SETTINGS`` object if
        available. Otherwise uses sane defaults provided by the
        ``climatecontrol`` package.

        """
        logging_settings = DEFAULT_LOG_SETTINGS
        try:
            logging_settings_update = getattr(self.settings, logging_section)
        except (KeyError, TypeError, AttributeError):
            logging_settings_update = None
        if logging_settings_update:
            logging_settings = merge_nested(logging_settings, logging_settings_update)
        logging_config.dictConfig(logging_settings)

    def click_settings_file_option(self, **kw) -> Callable[..., Any]:
        """See :func:`cli_utils.click_settings_file_option`."""
        from climatecontrol import cli_utils

        return cli_utils.click_settings_file_option(self, **kw)

    @contextmanager
    def temporary_changes(self):
        """Open a context where any changes to the settings are rolled back on context exit.

        This context manager can be used for testing or to temporarily change
        settings.

        Example:
            >>> from climatecontrol.core import Climate
            >>> climate = Climate()
            >>> climate.update({'a': 1})
            >>> with climate.temporary_changes():
            ...     climate.update({'a': 2})
            ...     assert climate.settings['a'] == 2
            >>> assert climate.settings['a'] == 1

        """
        archived_data = deepcopy(self._data.__wrapped__)
        archived_settings = {
            k: deepcopy(getattr(self, k))
            for k in [
                "settings_files",
                "_updates",
                "_fragments",
                "_combined_fragment",
            ]
        }
        yield self

        # reinstate all saved data after context block is finished
        self._set_data(archived_data)
        for k, v in archived_settings.items():
            setattr(self, k, v)

    def _set_state(
        self, parsed: Any, combined: Fragment, fragments: List[Fragment], updates: list
    ):
        """Set all relevant state fields related to loading of settings on object."""
        self._fragments = fragments
        self._combined_fragment = combined
        self._set_data(parsed)
        self._updates = updates
        self._initialized = True

    def _set_data(self, value: Any) -> None:
        self._data.__init__(value)

    def _stateless_reload(self, updates: list) -> Tuple[List[Fragment], Fragment, Any]:
        """Calculate result of reload but do not use any object state.

        Obtain updates from input instead of from :attrib:`_updates` and return
        the results as output instead of storing them in state.

        Args:
            updates: List of updates.
        Returns:

            Tuple conisting of a list of: The parsed result object, the combined
            final fragment, the list of fragments that were used to reach this
            result.
        """
        base_fragments = self._iter_base_fragments()
        update_fragments = self._iter_update_fragments(updates)
        fragments = list(chain(base_fragments, update_fragments))
        combined = self._combine_fragments(fragments)
        expanded = combined.expand_value_with_path()
        clean_removed_items(expanded)
        parsed = self.parse(expanded)
        return parsed, combined, fragments

    def _process_fragment(self, fragment: Fragment) -> Iterator[Fragment]:
        """Preprocess a settings fragment and return the new version."""
        for process in self._processors:
            for new_fragment in process(fragment):
                yield new_fragment
                # recursively process new fragments as well
                yield from self._process_fragment(new_fragment)

    def _iter_process_fragments(
        self, fragments: Iterable[Fragment]
    ) -> Iterator[Fragment]:
        for fragment in fragments:
            yield fragment
            yield from self._process_fragment(fragment)

    def _iter_update_fragments(self, updates: Sequence[Mapping] = ()):
        fragments = (
            Fragment(value=update_data, source="external")
            for update_data in updates
            if update_data
        )
        yield from self._iter_process_fragments(fragments)

    def _iter_base_fragments(self) -> Iterator[Fragment]:
        """Iterate through all relevant fragments."""
        fragments = chain(self._iter_load_files(), self.env_parser.iter_load())
        yield from self._iter_process_fragments(fragments)

    def _combine_fragments(self, fragments: Iterable[Fragment]) -> Fragment:
        """Combine the fragments into one final fragment."""
        combined_fragment: Optional[Fragment] = None
        for fragment in fragments:
            if combined_fragment is None:
                combined_fragment = fragment
            else:
                combined_fragment = combined_fragment.merge(fragment)

        if not combined_fragment:
            combined_fragment = Fragment({})
        return combined_fragment

    def _iter_load_files(self) -> Iterator[Fragment]:
        for inferred_entry in self.inferred_settings_files:
            yield from iter_load(inferred_entry)

        for entry in self.settings_files:
            yield from iter_load(entry)


def clean_removed_items(obj):
    """Remove all keys that contain a removed key indicated by a :data:``REMOVED`` object."""
    items: Iterable[Tuple[Any, Any]]
    if isinstance(obj, MutableMapping):
        items = obj.items()
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
