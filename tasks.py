#!/usr/bin/env python3

"""Development tasks for convenience."""

from invoke import Collection, Task, task


@task
def format(c):
    """Format the code to make it compatible with the `check` command."""
    print("> sorting imports]")
    c.run("isort -rc -y")

    print("> [painting all the code black]")
    c.run("black .")


@task
def test(c, aliases=["pytest"]):
    """Run all tests using pytest."""
    print("")
    print("[running pytest]")
    c.run("coverage run -m pytest")
    c.run("coverage report")


@task
def check(c):
    """Check the code is ok by running flake8, black, isort and mypy."""
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


# Configure default collection to change default pty setting
# Pytest will run much nicer if pty is set to true.
ns = Collection(*(item for item in locals().values() if isinstance(item, Task)))
ns.configure({"run": {"pty": True}})
