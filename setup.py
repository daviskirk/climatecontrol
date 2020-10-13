#!/usr/bin/env python

"""Setup climatecontrol."""

import os

from setuptools import find_packages, setup

requirements: list = ["wrapt"]

dataclasses_requirements = [
    "dacite",
    "dataclasses; python_version < '3.7'",
    "pydantic",
]

test_requirements = [
    "pytest",
    "pytest-mock",
    "coverage",
    "toml>=0.9.2",
    "pyyaml",
    "click>=7.0",
] + dataclasses_requirements

rootdir = os.path.abspath(os.path.dirname(__file__))

setup(
    name="climatecontrol",
    use_scm_version=True,
    description="Python library for loading app configurations from files and/or namespaced environment variables",
    long_description=open(os.path.join(rootdir, "README.rst")).read(),
    author="Davis Kirkendall",
    author_email="davis.e.kirkendall@gmail.com",
    url="https://github.com/daviskirk/climatecontrol",
    packages=find_packages(),
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
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    setup_requires=["pytest-runner", "setuptools_scm"],
    extras_require={
        "dev": ["invoke", "black", "mypy", "isort>=5.0.9", "flake8"]
        + test_requirements,
        "dataclasses": dataclasses_requirements,
    },
    tests_require=test_requirements,
)
