|Build Status| |Coverage Status|


CLIMATECONTROL
==============

Python library for loading app configurations from files and/or
namespaced environment variables.


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
    MY_APP_SECTION3=not_captured

Then use them in your python modules:

.. code:: python

    from climatecontrol.settings_parser import Settings
    settings_map = Settings(env_prefix='MY_APP', filters={'section1': 'subsection1', 'section2': None})
    print(dict(settings_map))

The output should look something like this:

::

    {'section1': {'subsection1': 'test1'}, 'section2': {'subsection2': 'test2', 'subsection3': 'test3'}}


.. |Build Status| image:: https://travis-ci.org/daviskirk/climatecontrol.svg?branch=master
   :target: https://travis-ci.org/daviskirk/climatecontrol
.. |Coverage Status| image:: https://coveralls.io/repos/github/daviskirk/climatecontrol/badge.svg?branch=master
   :target: https://coveralls.io/github/daviskirk/climatecontrol?branch=master
