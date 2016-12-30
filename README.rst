|Build Status| |Coverage Status|


CLIMATECONTROL
==============

CLIMATECONTROL controls your apps configuration environment. It is a Python
library for loading app configurations from files and/or namespaced environment
variables.


Install
-------

::

    pip install climatecontrol


Usage
-----

Set some environment variables in your shell

.. code:: sh

   export MY_APP_SECTION1_SUBSECTION1=test1
   export MY_APP_SECTION2_SUBSECTION2=test2
   export MY_APP_SECTION2_SUBSECTION3=test3

Then use them in your python modules:

.. code:: python

   from climatecontrol.settings_parser import Settings
   settings_map = Settings(prefix='MY_APP')
   print(dict(settings_map))

   {
       'section1': {
           'subsection1': 'test1'
       },
       'section2': {
           'subsection2': 'test2',
           'subsection3': 'test3'
       }
   }

In case you want to update your settings or your environment variables have
changed and you want to reload them, the `update` method will reload your
settings:

.. code:: python

   import os
   os.environ['MY_APP_SECTION2_NEW_ENV_VAR'] = 'new_env_data'
   settings_map.update()
   print(dict(settings_map))

   {
       'section1': {
           'subsection1': 'test1'
       },
       'section2': {
           'subsection2': 'test2',
           'subsection3': 'test3',
           'new_env_var': 'new_env_data'
       }
   }


Now you've noticed that you want more complex configurations and have settings
variables with underscores all over the place. For this situation you can
escape the section - splitting mechanism by using the splitting character twice
in your env variables:

.. code:: python

   settings_map = Settings(prefix='MY_APP', max_depth=3)
   print(dict(settings_map))

   {
       'section1': {
           'subsection1': 'test1'
       },
       'section2': {
           'subsection2': 'test2',
           'subsection3': 'test3',
           'new': {
               'env': {
                   'var': 'new_env_data'
               }
           }
       }
   }

   # That was ugly... we wanted something else
   del os.environ['MY_APP_SECTION2_NEW_ENV_VAR']

   # Notice the __ in the variable:
   os.environ['MY_APP_SECTION2_NEW_ENV__VAR'] = 'new_env_data'

   # Now let's look again
   settings_map.update()
   print(dict(settings_map))

   {
       'section1': {
           'subsection1': 'test1'
       },
       'section2': {
           'subsection2': 'test2',
           'subsection3': 'test3',
           'new': {
               'env_var': 'new_env_data'
           }
       }
   }



Settings file support
---------------------

If you don't want to use an environment variable for every single setting and
want to put your settings in a single file instead you can to this as well.
Settings files need to be in toml_ format right now.

.. code:: sh

   export MY_APP_SETTINGS_FILE=./my_settings_file.toml


The file could look like this:

.. code::

   [section1]
   subsection1 = "test1"

   [section2]
   subsection2 = "test2"
   subsection3 = "test3"


Command line support using click
--------------------------------

The click_ library is a great tool for creating command line applications. If
you don't want to have to use an environment to set your configuration file.
Write your command line application like this:

.. code:: python

   import click

   @click.command()
   @settings_map.click_settings_file_option()
   def cli():
      print(dict(settings_parser))

save it to a file like "cli.py" and then call it after installing click:

.. code:: sh

   pip install click
   python cli.py --settings ./my_settings_file.toml

whithout needing to set any env vars.


.. |Build Status| image:: https://travis-ci.org/daviskirk/climatecontrol.svg?branch=master
   :target: https://travis-ci.org/daviskirk/climatecontrol
.. |Coverage Status| image:: https://coveralls.io/repos/github/daviskirk/climatecontrol/badge.svg?branch=master
   :target: https://coveralls.io/github/daviskirk/climatecontrol?branch=master
.. _click: http://click.pocoo.org/
.. _toml: https://github.com/toml-lang/toml
