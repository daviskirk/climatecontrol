"""Fragment processors."""
import glob
import logging
import os
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence, Tuple, Type

from climatecontrol.constants import REMOVED
from climatecontrol.file_loaders import (
    FileLoader,
    NoCompatibleLoaderFoundError,
    iter_load,
    load_from_filepath,
)
from climatecontrol.fragment import Fragment, FragmentPath
from climatecontrol.utils import parse_as_json_if_possible

logger = logging.getLogger(__name__)


def find_suffix(fragment: Fragment, suffix: str) -> Iterator[Fragment]:
    value = fragment.value
    if isinstance(value, Mapping):
        items: Iterable[tuple] = value.items()
    elif isinstance(value, Sequence) and not isinstance(value, str):
        items = enumerate(value)
    else:
        return

    for k, v in items:
        new = fragment.clone(value=v, path=list(fragment.path) + [k])
        if isinstance(k, str) and k.endswith(suffix):
            yield new
        else:
            yield from find_suffix(new, suffix)


def replace_from_pattern(
    fragment: Fragment,
    postfix_trigger: str,
    transform_value: Callable[[Any, FragmentPath], Any],
    expected_exceptions: Tuple[Type[Exception], ...] = (),
):
    """Replace settings values using a given value transformation.

    Args:
        fragment: original fragment to search
        postfix_trigger: String at end of key that should trigger the transformation
        transform_value: Function to use to transform the value.  The function should take two arguments:
            * value: the value to transform
            * path: the fragment path at which the value was found.
        exected_exceptions: Tuple of exceptions to ignore if they are
            raised. In this case the original key and it's value that
            triggered the transformation is removed, and is not replaced
            with a new value.

    Yields:
        Additional fragments to patch the original fragment.

    """
    for leaf in find_suffix(fragment, postfix_trigger):
        path = leaf.path
        value = leaf.value

        if not path or value == REMOVED:
            continue

        key = path[-1]

        yield leaf.clone(value=REMOVED, path=path)

        try:
            # This allows "transform_value" to be a generator function as well.
            new_value = transform_value(value, path)
            if isinstance(new_value, Iterator):
                items: list = list(new_value)
            else:
                items = [new_value]
        except expected_exceptions:
            continue

        new_key = key[: -len(postfix_trigger)]
        new_path = list(path[:-1])
        if new_key:
            new_path += [new_key]

        for item in items:
            if isinstance(item, Fragment):
                kwargs = {}
                if item.source:
                    kwargs["source"] = leaf.source + f":{item.source}"
                yield leaf.clone(value=item.value, path=new_path, **kwargs)
            else:
                yield leaf.clone(value=item, path=new_path)


def replace_from_env_vars(
    fragment: Fragment, postfix_trigger: str = "_from_env"
) -> Iterator[Fragment]:
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

    class ExpectedTransformError(Exception):
        pass

    def transform_value(value, path):
        if not isinstance(value, str):
            raise ValueError(
                f"{postfix_trigger} replacement expects a string a a variable."
            )
        if "$" in value:
            env_var_value = os.path.expandvars(value)
        else:
            try:
                env_var_value = os.environ[value]
            except KeyError as e:
                logger.info(
                    "Error while trying to load environment variable: %s from %s. (%s) Skipping...",
                    value,
                    ".".join(str(p) for p in path),
                    e,
                )
                raise ExpectedTransformError()
        return parse_as_json_if_possible(env_var_value)

    yield from replace_from_pattern(
        fragment, postfix_trigger, transform_value, (ExpectedTransformError,)
    )


def replace_from_file_vars(
    fragment: Fragment, postfix_trigger: str = "_from_file"
) -> Iterator[Fragment]:
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

    def transform_value(value: Any, path: FragmentPath) -> Any:
        if isinstance(value, list):
            # if we get a list, process each item one after another.
            for item in value:
                yield from transform_value(item, path)
            return

        if not isinstance(value, str):
            raise ValueError("file path must be string")

        try:
            if glob.has_magic(value):
                yield from iter_load(value)
                return
            try:
                yield load_from_filepath(value)
                return
            except NoCompatibleLoaderFoundError:
                # just load as plain text file and interpret as string
                with open(value) as f:
                    yield f.read().strip()
                    return
        except FileNotFoundError as e:
            logger.info(
                "Error while trying to load variable from file: %s. (%s) Skipping...",
                value,
                ".".join(str(p) for p in path),
                e,
            )

    yield from replace_from_pattern(fragment, postfix_trigger, transform_value)


def replace_from_content_vars(fragment: Fragment) -> Iterator[Fragment]:
    """Read and replace settings values from content local files.

    Args:
        fragment: Fragment to process

    Yields:
        Additional fragments to patch the original fragment.

    """

    file_loader_map = {
        ext.strip("."): loader
        for loader in FileLoader.registered_loaders
        for ext in loader.valid_file_extensions
    }

    for format_name, loader in file_loader_map.items():
        postfix_trigger = f"_from_{format_name}_content"

        def transform_value(value, path: FragmentPath):
            try:
                return loader.from_content(value)
            except Exception:
                path_str = ".".join(str(p) for p in path)
                logger.info(
                    "Error while trying to load %s content at %s.",
                    format_name,
                    path_str,
                )
                raise

        yield from replace_from_pattern(
            fragment, postfix_trigger, transform_value, (Exception,)
        )
