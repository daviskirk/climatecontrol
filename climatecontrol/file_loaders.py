"""Module for loading various file formats."""

import glob
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple, Union

from .exceptions import NoCompatibleLoaderFoundError
from .fragment import Fragment

try:
    import toml
except ImportError:  # pragma: nocover
    toml = None  # type: ignore
try:
    import yaml
except ImportError:  # pragma: nocover
    yaml = None  # type: ignore


def iter_load(path: Union[str, Path]) -> Iterator[Fragment]:
    """Read settings file from a filepath or from a string representing the file contents.

    If ``path`` is a valid filename or glob expression, load the
    file (or all matching files).

    Note that json, yaml and toml files are read.

    Args:
        path: Path to file or file contents

    Raises:
        FileLoadError: when an error occurs during the loading of a file.
        NoCompatibleLoaderFoundError: when no compatible loader was found for
          this filepath or content type.

    """
    if not path:
        return
    expanded_path: str = os.path.expanduser(os.path.expandvars(path))
    if glob.has_magic(expanded_path):
        filepaths: List[str] = sorted(glob.glob(expanded_path))
    else:
        filepaths = [expanded_path]
    for filepath in filepaths:
        yield Fragment(value=load_from_filepath(filepath), source=filepath)


def load_from_filepath(filepath: str) -> Dict[str, Any]:
    """Read settings file from a filepath or from a string representing the file contents.

    Args:
        filepath: Path to file or file contents

    Raises:
        FileLoadError: when an error occurs during the loading of a file.
        ContentLoadError: when an error occurs during the loading of file contents.
        NoCompatibleLoaderFoundError: when no compatible loader was found for
            this filepath or content type.

    """
    file_data: dict = {}
    if not filepath:
        return file_data
    for loader in FileLoader.registered_loaders:
        if loader.is_path(filepath):
            file_data = loader.from_path(filepath)
            break
    else:
        raise NoCompatibleLoaderFoundError(
            "Failed to load settings from filepath. "
            "No compatible loader for file: {}".format(filepath)
        )
    return file_data


class FileLoader(ABC):
    """Abstract base class for file/file content loading."""

    format_name: str = ""
    valid_file_extensions: Tuple[str, ...] = ()
    registered_loaders: List["FileLoader"] = []

    @classmethod
    @abstractmethod
    def from_path(cls, path: str) -> Any:
        """Load serialized data from file at path."""

    @classmethod
    @abstractmethod
    def from_content(cls, content: str) -> Any:
        """Load serialized data from content."""

    @classmethod
    def is_path(cls, path_or_content: str):
        """Check if argument is a valid file path.

        If `only_existing` is set to ``True``, paths to files that don't exist
        will also return ``False``.
        """
        return len(str(path_or_content).strip().splitlines()) == 1 and (
            os.path.splitext(path_or_content)[1] in cls.valid_file_extensions
        )

    @classmethod
    def register(cls, class_to_register):
        """Register class as a valid file loader."""
        cls.registered_loaders.append(class_to_register)
        return class_to_register


@FileLoader.register
class JsonLoader(FileLoader):
    """FileLoader for .json files."""

    format_name = "json"
    valid_file_extensions = (".json",)

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
    def to_content(cls, data) -> str:
        """Serialize mapping to string."""
        return json.dumps(data, indent=4)


@FileLoader.register
class YamlLoader(FileLoader):
    """FileLoader for .yaml files."""

    format_name = "yaml"
    valid_file_extensions = (".yml", ".yaml")

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

    @staticmethod
    def _check_yaml():
        if yaml is None:
            raise ImportError(
                '"pyyaml" package needs to be installed to parse yaml files.'
            )


@FileLoader.register
class TomlLoader(FileLoader):
    """FileLoader for .toml files."""

    format_name = "toml"
    valid_file_extensions = (".toml", ".ini", ".config", ".conf", ".cfg")

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

    @staticmethod
    def _check_toml():
        if toml is None:
            raise ImportError(
                '"toml" package needs to be installed to parse toml files.'
            )
