[![Build Status](https://travis-ci.org/daviskirk/climatecontrol.svg?branch=master)](https://travis-ci.org/daviskirk/climatecontrol) [![Coverage Status](https://coveralls.io/repos/github/daviskirk/climatecontrol/badge.svg?branch=master)](https://coveralls.io/github/daviskirk/climatecontrol?branch=master)

# CLIMATECONTROL

Python library for loading app configurations from files and/or namespaced
environment variables.

## Install
```
pip install git+https://github.com/daviskirk/climatecontrol.git
```

## Usage

Set some environment variables in your shell
```sh
MY_APP_SECTION1_SUBSECTION1=test1
MY_APP_SECTION2_SUBSECTION2=test2
MY_APP_SECTION2_SUBSECTION3=test3
MY_APP_SECTION3=not_captured
```

Then use them in your python modules:

```python
from climatecontrol.settings_parser import Settings
settings_map = Settings(env_prefix='MY_APP', filters={'section1': 'subsection1', 'section2': None})
print(dict(settings_map))
```

The output should look something like this:

```
{'section1': {'subsection1': 'test1'}, 'section2': {'subsection2': 'test2', 'subsection3': 'test3'}}
```
