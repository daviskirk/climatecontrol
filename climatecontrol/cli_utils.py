#!/usr/bin/env python

"""
CLI utils for easy command line extras.
"""

import click
from . import settings_parser


def click_settings_file_option(settings_obj: settings_parser.Settings,
                               click_obj=click, option_name='settings'):
    """Convenience function for building a `click` option decorator

    Args:
        settings_obj: settings object to load configuration into.
        click_obj: if a command

    Example:
       Given a command line script `cli.py`:

        .. code-block:: python

           import click
           from climatecontrol import settings_parser, cli_utils

           settings_map = settings_parser.Settings(env_prefix='TEST_STUFF')

           @click.command()
           @cli_utils.click_settings_file_option(settings_map)
           def tmp_cli():
               pass

        And running the script:

        .. code-block:: bash

           python cli.py --settings 'my_settings_file.toml'

        will load settings from `my_settings_file.toml` into the `settings_map`
        object which can then be used in the script.

    """
    def validate(ctx, param, value):
        if value:
            settings_obj.settings_files = value
            settings_obj.update()

    option = click_obj.option(
        '--{}'.format(option_name),
        help='Settings file path for loading settings from toml file.',
        callback=validate,
        type=click.Path(exists=True, dir_okay=False, resolve_path=True),
        expose_value=False,
        is_eager=True,
        multiple=True
    )

    return option
