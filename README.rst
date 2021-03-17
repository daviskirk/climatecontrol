|Build Status| |Coverage Status| |PyPi version| |PyPI license| |PyPI pyversions| |Conda version|
|Code Style Black|


.. image:: https://raw.githubusercontent.com/daviskirk/climatecontrol/logo/climatecontrol-text.svg?sanitize=true


CLIMATECONTROL controls your applications settings and configuration
environment. It is a Python library for loading app configurations from files
and/or namespaced environment variables.

Features
========

* Separation of settings and code
* Loading from files (`.yaml`, `.json`, `.toml`)
* Loading multiple files using glob syntax
* Loading from environment variables, including loading of nested values
* Freely reference nested configurations via files or environment variables
* CLI integration
* Validation using the Validation library of your choice
* Logging configuration integration
* Testing integration


Install
=======

::

    pip install climatecontrol



Usage
=====

Set some environment variables in your shell

.. code:: sh

   export CLIMATECONTROL_VALUE1=test1
   export CLIMATECONTROL_VALUE2=test2

Then use them in your python modules:

.. code:: python

   from climatecontrol import climate
   print(climate.settings)

   {
       'value1': 'test1',
       'value2': 'test2'
   }

In case you want to update your settings or your environment variables have
changed and you want to reload them, the `update` method will reload your
settings:

.. code:: python

   import os
   os.environ['CLIMATECONTROL_VALUE3'] = 'new_env_data'
   climate.reload()
   print(climate.settings)

   {
       'value1': 'test1',
       'value2': 'test2',
       'value3': 'new_env_data'
   }


Now you've noticed that you want more complex configurations and need nested
settings. For this situation we can delimit sections using a double underscore:

.. code:: sh

   export CLIMATECONTROL_SECTION1__VALUE1=test1
   export CLIMATECONTROL_SECTION2__VALUE2=test2
   export CLIMATECONTROL_SECTION2__VALUE3=test3
   export CLIMATECONTROL_SECTION2__SUB_SECTION__VALUE4=test4

.. code:: python

   from climatecontrol import climate
   print(climate.settings)

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


Settings file support
---------------------

If you don't want to use an environment variable for every single setting and
want to put your settings in a single file instead you can to this as well.
Settings files can be yaml files (`.yml`/ `.yaml`), json files (`.json`) or toml_ files (`.toml`).

.. code-block:: sh

   export CLIMATECONTROL_SETTINGS_FILE=./my_settings_file.yml


The file could look like this:

.. code-block:: yaml

   # ./climatecontrol_settings.yaml
   section1:
     subsection1 = test1

   section2:
     subsection2: test2
     subsection3: test3


or in toml form:

.. code-block:: sh

   # ./climatecontrol_settings.toml
   [section1]
   subsection1 = "test1"

   [section2]
   subsection2 = "test2"
   subsection3 = "test3"


In the following documentation examples, yaml files will be used, but any
examples will work using the other file syntaxes as well.

See the `climatecontrol.core.Climate.inferred_settings_files` docstring
for further examples of how settings files are loaded and how they can be named.
Also note that you can set your own settings files explicitely either by
settings an environment variable:

.. code-block:: sh

   export CLIMATECONTROL_SETTINGS_FILE="mysettings.yaml, mysettings.toml, override.yml"

or by adding them in code:

.. code-block:: python

   climate.settings_files.extend(["mysettings.yaml", "mysettings.toml", "override.yml"]


Advanced Features
-----------------

Setting variables from values saved in files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes we don't want to save values in plain text in environment files or in
the settings file itself. Instead we have a file that contains the value of the
setting we want. A good example for this behaviour are docker secrets_ that
store secrets in temporary files.

To read a variable from a file, simply add a `"_from_file"` to the variable
name and give it the path to the file that contains the variable as a value.

Using a settings file with the contents (in this case yaml):

.. code-block:: yaml

   section1:
     subsection1_from_file: /home/myuser/supersecret.txt

or using an environment variable:

.. code-block:: sh

   export CLIMATECONTROL_SECTION1_SUBSECTION1_FROM_FILE="/home/myuser/supersecret.txt"

will both write the content of the file at `"/home/myuser/supersecret.txt"`
into the variable `section1 -> subsection1`.


Setting variables from values saved in specific environment variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Similarly, to read a value from an environment variable, add a `"_from_env"` to
the variable name. For example if we wanted to obtain a value from the variable
`SPECIFIC_ENV_VAR`:

.. code-block:: sh

   export SPECIFIC_ENV_VAR="some value"

Using a settings file with the contents (in this case yaml):

.. code-block:: yaml

   section1:
     subsection1_from_env: SPECIFIC_ENV_VAR

or using an environment variable:

.. code-block:: sh

   export CLIMATECONTROL_SECTION1_SUBSECTION1_FROM_FILE="/home/myuser/supersecret.txt"

will both write "some value" into the variable `section1 -> subsection1`.

Settings variables from serialized content
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: yaml

   section1_from_json_content: '{"subsection1": "test", "subsection2": 2}'
   section2_from_toml_content: 'subsection1 = "test"\nsubsection2 = 2\n'
   section3_from_yaml_content: 'subsection1: test\nsubsection2: 2\n'


The equivilant environment variables are also handled correctly:

.. code-block:: sh

   CLIMATECONTROL_SECTION1_FROM_JSON_CONTENT='{"subsection1": "test", "subsection2": 2}'
   CLIMATECONTROL_SECTION2_FROM_TOML_CONTENT='subsection1 = "test"\nsubsection2 = 2\n'
   CLIMATECONTROL_SECTION3_FROM_YAML_CONTENT='subsection1: test\nsubsection2: 2\n'


Nested settings files
^^^^^^^^^^^^^^^^^^^^^

In addition, file variables can also target other settings files directly. To
do this, just make sure the target file is has an extension supported by
climate control. A simple example is illustrated here. Given a settings file:

.. code-block:: yaml

   value1: "spam"
   section1_from_file: /home/myuser/nestedfile.yaml


where the content of `/home/myuser/nestedfile.yaml` is:

.. code-block:: yaml

   value2: "cheese"
   subsection:
     value3: "parrot"

which would result in a settings structure:

.. code-block:: python

   {
       "value1": "spam",
       "section1": {
           "value2": "cheese",
           "subsection": {
               "value3": "parrot"
           }
       }
   }

You can also expand the settings at the root of the document by using only
"_from_file" as the key:

.. code-block:: yaml

   value1: "spam"
   _from_file: /home/myuser/nestedfile.yaml

.. code-block:: python

   {
       "value1": "spam",
       "value2": "cheese",
       "subsection": {
           "value3": "parrot"
       }
   }


Extensions
----------

While the default `climate` object is great for most uses, perhaps you already
have a settings object style that you like or use a specific library for
validation.  In these cases, CLIMATECONTROL can be extended to use these
libraries.

Dataclasses
^^^^^^^^^^^

>>> from climatecontrol.ext.dataclasses import Climate
>>> from dataclasses import dataclass, field
>>>
>>> @dataclass
... class SettingsSubSchema:
...     d: int = 4
...
>>> @dataclass
... class SettingsSchema:
...     a: str = 'test'
...     b: bool = False
...     c: SettingsSubSchema = field(default_factory=SettingsSubSchema)
...
>>> climate = Climate(dataclass_cls=SettingsSchema)
>>> # defaults are initialized automatically:
>>> climate.settings.a
'test'
>>> climate.settings.c.d
4
>>> # Types are checked if given
>>> climate.update({'c': {'d': 'boom!'}})
Traceback (most recent call last):
    ...
dacite.exceptions.WrongTypeError: wrong type for field "c.d" - should be "int" instead of "str"


Pydantic
^^^^^^^^

Pydantic is a great data validation library:
https://github.com/samuelcolvin/pydantic and climatecontrol also provides a
simple extension to use pydantic models directly (typing functionality mentioned
above works here as well).

>>> from climatecontrol.ext.pydantic import Climate
>>>
>>> class SettingsSubSchema(BaseModel):
...     d: int = 4
...
>>> class SettingsSchema(BaseModel):
...     a: str = 'test'
...     b: bool = False
...     c: SettingsSubSchema = SettingsSubSchema()
...
>>> climate = Climate(model=SettingsSchema)
>>> # defaults are initialized automatically:
>>> climate.settings.a
'test'
>>> climate.settings.c.d
4
>>> # Types are checked if given
>>> climate.update({'c': {'d': 'boom!'}})
Traceback (most recent call last):
    ...
pydantic.error_wrappers.ValidationError: 1 validation error for SettingsSchema
c -> d
    value is not a valid integer (type=type_error.integer)


Integrations
------------

Command line support using click
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The click_ library is a great tool for creating command line applications. If
you don't want to have to use an environment to set your configuration file.
Write your command line application like this:

.. code-block:: python

   import click

   @click.command()
   @climate.click_settings_file_option()
   def cli():
      print(climate.settings)

save it to a file like "cli.py" and then call it after installing click:

.. code-block:: sh

   pip install click
   python cli.py --settings ./my_settings_file.toml

whithout needing to set any env vars.

Multiple files are supported. They will be automatically recursively merged
with the last file overriting any overlapping keys of the first file.

.. code-block:: sh

   pip install click
   python cli.py --settings ./my_settings_file.toml  --settings ./my_settings_file.yaml


Logging
^^^^^^^

If you have a "logging" section in your settings files, you can configure
python standard library logging using that section directly:

.. code:: yaml

   logging:
     formatters:
       default:
         format': "%(levelname)s > %(message)s"
     root:
       level: DEBUG


.. code:: python

   import logging
   from climatecontrol import climate

   climate.setup_logging()
   logging.debug('test')
   # outputs: DEBUG > test


Testing
-------

When testing your application, different behaviours often depend on settings
taking on different values. Assuming that you are using a single `Settings`
object accross multiple functions or modules, handling these settings changes
in tests can be tricky.

The settings object provides a simple method for modifying your settings object
temporarily:

.. code-block:: python

   climate.update({'a': 1})
   # Enter a temporary changes context block:
   with climate.temporary_changes():
       climate.update({'a': 1})
       # Inside the context, the settings can be modified and used as you choose
       print(climate['a'])  # outputs: 2
   # After the context exits the settings map
   print(climate['a'])  # outputs: 1


Contributing
============

See: `CONTRIBUTING.md <./CONTRIBUTING.md>`__


.. |Build Status| image:: https://img.shields.io/github/workflow/status/daviskirk/climatecontrol/ci?style=flat-square
   :target: https://github.com/daviskirk/climatecontrol
.. |Coverage Status| image:: https://img.shields.io/codecov/c/github/daviskirk/climatecontrol/master?style=flat-square
   :target: https://codecov.io/gh/daviskirk/climatecontrol
.. |PyPI version| image:: https://img.shields.io/pypi/v/climatecontrol?style=flat-square
   :target: https://pypi.python.org/pypi/climatecontrol/
.. |PyPI license| image:: https://img.shields.io/pypi/l/climatecontrol?style=flat-square
   :target: https://pypi.python.org/pypi/climatecontrol/
.. |PyPI pyversions| image:: https://img.shields.io/pypi/pyversions/climatecontrol?style=flat-square
   :target: https://pypi.python.org/pypi/climatecontrol/
.. |Conda version| image:: https://img.shields.io/conda/vn/conda-forge/climatecontrol?style=flat-square
   :target: https://anaconda.org/conda-forge/climatecontrol
.. |Code Style Black| image:: https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square
   :target: https://github.com/psf/black
.. _click: http://click.pocoo.org/
.. _toml: https://github.com/toml-lang/toml
.. _secrets: https://docs.docker.com/engine/swarm/secrets
