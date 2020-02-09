"""Fragment processors."""
import logging
import os
from typing import Any, Callable, Iterator, Tuple, Type

from climatecontrol.constants import REMOVED
from climatecontrol.file_loaders import (
    FileLoader,
    NoCompatibleLoaderFoundError,
    load_from_filepath,
)
from climatecontrol.fragment import Fragment, FragmentPath
from climatecontrol.utils import parse_as_json_if_possible

logger = logging.getLogger(__name__)


def replace_from_pattern(
    fragment: Fragment,
    postfix_trigger: str,
    transform_value: Callable[[Any, FragmentPath], Any],
    expected_exceptions: Tuple[Type[Exception], ...],
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
    for leaf in fragment.iter_leaves():
        if not leaf.path or leaf.value == REMOVED:
            continue

        key, value = leaf.path[-1], leaf.value

        if (
            not isinstance(value, str)
            or not isinstance(key, str)
            or not key.lower().endswith(postfix_trigger)
        ):
            continue

        yield leaf.clone(value=REMOVED)

        try:
            new_value = transform_value(value, leaf.path)
        except expected_exceptions:
            pass
        else:
            new_key = key[: -len(postfix_trigger)]
            yield leaf.clone(value=new_value, path=list(leaf.path[:-1]) + [new_key])


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

    class ExpectedTransformError(Exception):
        pass

    def transform_value(value: Any, path: FragmentPath) -> Any:
        try:
            try:
                return load_from_filepath(value)
            except NoCompatibleLoaderFoundError:
                # just load as plain text file and interpret as string
                with open(value) as f:
                    return f.read().strip()
        except FileNotFoundError as e:
            logger.info(
                "Error while trying to load variable from file: %s. (%s) Skipping...",
                value,
                ".".join(str(p) for p in path),
                e,
            )
            raise ExpectedTransformError()

    yield from replace_from_pattern(
        fragment, postfix_trigger, transform_value, (ExpectedTransformError,)
    )


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
