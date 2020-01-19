#!/usr/bin/env python

"""Setup climatecontrol."""

import os

from setuptools import setup

requirements: list = []

test_requirements = [
    "pytest",
    "pytest-mock",
    "pytest-cov>=2.5.1",
    "toml>=0.9.2",
    "pyyaml",
    "click>=7.0",
]

rootdir = os.path.abspath(os.path.dirname(__file__))

setup(
    name="climatecontrol",
    use_scm_version=True,
    description="Python library for loading app configurations from files and/or namespaced environment variables",
    long_description=open(os.path.join(rootdir, "README.rst")).read(),
    author="Davis Kirkendall",
    author_email="davis.e.kirkendall@gmail.com",
    url="https://github.com/daviskirk/climatecontrol",
    packages=["climatecontrol"],
    package_dir={"climatecontrol": "climatecontrol"},
    include_package_data=True,
    install_requires=requirements,
    license="MIT",
    zip_safe=False,
    keywords="climatecontrol",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    setup_requires=["pytest-runner", "setuptools_scm"],
    tests_require=test_requirements,
)
