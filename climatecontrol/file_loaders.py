"""Module for loading various file formats."""

import json
import os
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Tuple, List  # noqa: F401
from typing import Any, Dict, Mapping

from .exceptions import NoCompatibleLoaderFoundError

try:
    import toml
except ImportError:
    toml = None  # type: ignore
try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


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
