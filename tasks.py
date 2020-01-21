#!/usr/bin/env python3

"""Development tasks for convenience."""

from invoke import task


@task
def format(c):
    """Format the code to make it compatible with the `check` command."""
    _context(c)
    print("> sorting imports]")
    c.run("isort -rc -y")

    print("> [painting all the code black]")
    c.run("black .")


@task
def test(c, aliases=["pytest", "bla"]):
    """Run all tests using pytest."""
    _context(c)
    print("")
    print("[running pytest]")
    c.run("coverage run -m pytest")
    c.run("coverage report")


@task
def check(c):
    """Check the code is ok by running flake8, black, isort and mypy."""
    _context(c)
    print("> check that code is formatted well")
    c.run("black --check .")
    c.run("isort --check-only -rc")
    print("> lint with flake8")
    c.run("flake8")
    print("> typecheck")
    c.run("mypy .")


@task(pre=[format, check, test])
def all(c):
    """Run format, check and test all in one command."""


def _context(c):
    """Modify context such that default options are turned on."""
    c.config["run"].update({"pty": True})
