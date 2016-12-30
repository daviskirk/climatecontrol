#!/usr/bin/env python

"""
Module docstring.
"""

import os
import sys
from setuptools import setup
from setuptools import Command

requirements = [
    'toml>=0.9.2',
    'typing'
]

test_requirements = [
    'click',
    'pytest-mock',
    'pytest-cov',
    'pytest'
]

rootdir = os.path.abspath(os.path.dirname(__file__))


def read(fname):
    """Utility function to read the README file. Used for the long_description.
    It's nice, because now 1) we have a top level README file and 2) it's
    easier to type in the README file than to put a raw string in below ...

    """
    return open(os.path.join(rootdir, fname)).read()


class Typecheck(Command):

    user_options = [('mypy-args=', 'a', 'mypy args')]
    description = "Install and run mypy typechecker"

    def initialize_options(self):
        self.mypy_args = ''

    def finalize_options(self):
        pass

    def run(self):
        # import here, cause outside the eggs aren't loaded
        from subprocess import call
        bin_path = os.path.join(os.path.abspath(os.path.dirname(sys.executable)), 'mypy')
        if not os.path.isfile(bin_path):
            raise RuntimeError((
                'mypy must be installed before typecheck can be preformed.'
                'Try running:\n'
                'pip install mypy-lang\n'
                'and then repeating this command'))
        args = [bin_path, '-s', '--check-untyped-defs']
        if self.mypy_args:
            args.append(self.mypy_args)
        args += ['--package', 'climatecontrol']
        errno = call(args, cwd=rootdir)
        sys.exit(errno)


setup(
    name='climatecontrol',
    use_scm_version=True,
    description="Python library for loading app configurations from files and/or namespaced environment variables",
    long_description=read('README.rst'),
    author="Davis Kirkendall",
    author_email='davis.e.kirkendall@gmail.com',
    url='https://github.com/daviskirk/climatecontrol',
    packages=[
        'climatecontrol',
    ],
    package_dir={'climatecontrol': 'climatecontrol'},
    include_package_data=True,
    install_requires=requirements,
    license="MIT",
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
    tests_require=test_requirements,
    cmdclass={'typecheck': Typecheck},
)
