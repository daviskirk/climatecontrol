|Build Status| |Coverage Status| |PyPi Status|


CLIMATECONTROL
==============

CLIMATECONTROL controls your apps configuration environment. It is a Python
library for loading app configurations from files and/or namespaced environment
variables.


Install
-------

::

    pip install climatecontrol


Note that versions 0.2.4 and below will probably not work with python 3.5.2 and
below. Default 3.5 branch should work fine though.


Usage
-----

Set some environment variables in your shell

.. code:: sh

   export MY_APP_VALUE1=test1
   export MY_APP_VALUE2=test2

Then use them in your python modules:

.. code:: python

   from climatecontrol.settings_parser import Settings
   settings_map = Settings(prefix='MY_APP')
   print(dict(settings_map))

   {
       'value1': 'test1',
       'value2': 'test2'
   }

In case you want to update your settings or your environment variables have
changed and you want to reload them, the `update` method will reload your
settings:

.. code:: python

   import os
   os.environ['MY_APP_VALUE3'] = 'new_env_data'
   settings_map.update()
   print(dict(settings_map))

   {
       'value1': 'test1',
       'value2': 'test2',
       'value3': 'new_env_data'
   }


Now you've noticed that you want more complex configurations and need nested
settings. For this situation we can delimit sections using a double underscore:

.. code:: sh

   export MY_APP_SECTION1__VALUE1=test1
   export MY_APP_SECTION2__VALUE2=test2
   export MY_APP_SECTION2__VALUE3=test3
   export MY_APP_SECTION2__SUB_SECTION__VALUE4=test4

.. code:: python

   settings_map = Settings(prefix='MY_APP')
   print(dict(settings_map))

   {
       'section1': {
           'value1': 'test1'
       },
       'section2': {
           'value2': 'test2',
           'value3': 'test3',
           'sub_section': {
               'value4': 'test4'
           }
       }
   }


Finally if you decide that your settings are simpler and you know that your
section names do not have underscores, you can use the ``implicit_depth``
option, which allows you to add a new section at every single underscore (up to
the depth you specify).

.. code:: sh

   export MY_APP_SECTION1_VALUE1=test1
   export MY_APP_SECTION2_VALUE2=test2
   export MY_APP_SECTION2_VALUE3=test3
   export MY_APP_SECTION2_SUBSECTION_VALUE4=test4

.. code:: python

   settings_map = Settings(prefix='MY_APP', implicit_depth=2)
   print(dict(settings_map))

   {
       'section1': {
           'value1': 'test1'
       },
       'section2': {
           'value2': 'test2',
           'value3': 'test3',
           'subsection': {
               'value4': 'test4'
           }
       }
   }


Settings file support
---------------------

If you don't want to use an environment variable for every single setting and
want to put your settings in a single file instead you can to this as well.
Settings files can be toml_ files (`.toml`), yaml files (`.yml`) or json files (`.json`).

.. code:: sh

   export MY_APP_SETTINGS_FILE=./my_settings_file.toml


The file could look like this:

.. code::

   [section1]
   subsection1 = "test1"

   [section2]
   subsection2 = "test2"
   subsection3 = "test3"


Setting variables whos values are saved in files
------------------------------------------------

Sometimes we don't want to save values in plain text in environment files or in
the settings file itself. Instead we have a file that contains the value of the
setting we want. A good example for this behaviour are docker _secrets that
store secrets in temporary files.

To read a variable from a file, simply add a `"_from_file"` to the variable
name and give it the path to the file that contains the variable as a value.

Using:

.. code::

   [section1]
   subsection1_from_file = /home/myuser/supersecret.txt

or

.. code:: sh

   export MY_APP_SECTION1_SUBSECTION1_FROM_FILE="/home/myuser/supersecret.txt"

will both write the content of the file at `"/home/myuser/supersecret.txt"`
into the variable `section1 -> sebsection1`.


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
.. |PyPi Status| image:: https://badge.fury.io/py/climatecontrol.svg
   :target: https://badge.fury.io/py/climatecontrol
.. _click: http://click.pocoo.org/
.. _toml: https://github.com/toml-lang/toml
.. _secrets: https://docs.docker.com/engine/swarm/secrets
