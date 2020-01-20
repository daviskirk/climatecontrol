#!/usr/bin/env python3

"""Development tasks for convenience."""

from invoke import task


@task
def format(c):
    """Format the code to make it compatible with the `check` command."""
    _context(c)
    print("> sorting imports]")
    c.run("isort -rc -y", pty=True)

    print("> [painting all the code black]")
    c.run("black .", pty=True)


@task
def test(c, aliases=["pytest", "bla"]):
    """Run pytest."""
    _context(c)
    print("")
    print("[running pytest]")
    c.run("pytest", pty=True)


@task
def check(c):
    """Check the code is ok."""
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
    """Run all formatting commands, lints and tests."""


def _context(c):
    """Modify context such that default options are turned on."""
    c.config["run"].update({"pty": True})
