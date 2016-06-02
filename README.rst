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

    MY_APP_SECTION1_SUBSECTION1=test1
    MY_APP_SECTION2_SUBSECTION2=test2
    MY_APP_SECTION2_SUBSECTION3=test3

Then use them in your python modules:

>>> from climatecontrol.settings_parser import Settings
>>> settings_map = Settings(env_prefix='MY_APP')
>>> dict(settings_map)
{'section1': {'subsection1': 'test1'}, 'section2': {'subsection2': 'test2', 'subsection3': 'test3'}}
>>>

In case you want to update your settings or your environment variables have
changed and you want to reload them, the `update` method will reload your
settings:

>>> import os
>>> os.environ['MY_APP_SECTION2_NEW_ENV_VAR'] = 'new_env_data'
>>> settings_map.update()
{'section2': {'subsection3': 'test3', 'subsection2': 'test2', 'new_env_var': 'new_env_data'}, 'section1': {'subsection1': 'test1'}}
>>>


.. |Build Status| image:: https://travis-ci.org/daviskirk/climatecontrol.svg?branch=master
   :target: https://travis-ci.org/daviskirk/climatecontrol
.. |Coverage Status| image:: https://coveralls.io/repos/github/daviskirk/climatecontrol/badge.svg?branch=master
   :target: https://coveralls.io/github/daviskirk/climatecontrol?branch=master
