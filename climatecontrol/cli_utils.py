"""CLI utils for easy command line extras."""

import click

from climatecontrol import core


def click_settings_file_option(
    settings_obj: core.Climate, click_obj=click, option_name="settings", **kw
):
    """Build a `click` option decorator.

    Args:
        settings_obj: settings object to load configuration into.
        click_obj: if a command

    Example:
       Given a command line script `cli.py`:

        .. code-block:: python

           import click
           from climatecontrol import core, cli_utils

           settings_map = settings_parser.Climate(env_prefix='TEST_STUFF')

           @click.command()
           @cli_utils.click_settings_file_option(settings_map)
           def tmp_cli():
               pass

        And running the script:

        .. code-block:: bash

           python cli.py --settings 'my_settings_file.yaml'

        will load settings from `my_settings_file.yaml` into the `settings_map`
        object which can then be used in the script.

    """

    def validate(ctx, param, value):
        if value:
            settings_obj.settings_files = value
            settings_obj.update()

    option_kwargs = dict(
        help="Settings file path for loading settings from file.",
        callback=validate,
        type=click_obj.Path(exists=True, dir_okay=False, resolve_path=True),
        expose_value=False,
        is_eager=True,
        multiple=True,
    )
    option_kwargs.update(kw)
    option = click_obj.option(
        "--{}".format(option_name), "-{}".format(option_name[0]), **option_kwargs
    )
    return option
