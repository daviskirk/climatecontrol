#!/usr/bin/env python

"""Setup climatecontrol."""

import os
from setuptools import setup

requirements = [
    'typing'
]

test_requirements = [
    'click',
    'pytest-mock',
    'pytest-cov>=2.5.1',
    'pytest>=3.2.1',
    'toml>=0.9.2',
    'pyyaml'
]

rootdir = os.path.abspath(os.path.dirname(__file__))


def read(fname):
    """Read a file from path.

    Utility function to read the README file. Used for the long_description.
    It's nice, because now 1) we have a top level README file and 2) it's
    easier to type in the README file than to put a raw string in below ...

    """
    return open(os.path.join(rootdir, fname)).read()


setup(
    name='climatecontrol',
    use_scm_version=True,
    description='Python library for loading app configurations from files and/or namespaced environment variables',
    long_description=read('README.rst'),
    author='Davis Kirkendall',
    author_email='davis.e.kirkendall@gmail.com',
    url='https://github.com/daviskirk/climatecontrol',
    packages=[
        'climatecontrol',
    ],
    package_dir={'climatecontrol': 'climatecontrol'},
    include_package_data=True,
    install_requires=requirements,
    license='MIT',
    zip_safe=False,
    keywords='climatecontrol',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ],
    setup_requires=['pytest-runner', 'setuptools_scm'],
    tests_require=test_requirements
)
