#!/usr/bin/env python3
from dataclasses import dataclass

import dacite
import pytest

from climatecontrol.ext.dataclasses import Climate


def test_climate_simple(mock_empty_os_environ):
    """Test basic dataclass climate object."""

    @dataclass
    class A:
        a: int = 1
        b: str = "yeah"

    climate = Climate(dataclass_cls=A)
    assert climate.settings == A()


def test_climate(mock_empty_os_environ):
    """Test climate with dataclasses."""

    @dataclass
    class C:
        d: str = "weee"
        e: int = 0

    @dataclass
    class A:
        c: C = C()
        a: int = 1
        b: str = "yeah"

    climate = Climate(dataclass_cls=A)
    assert climate.settings.c.d == "weee"
    climate.update({"b": "changed"})
    assert len(climate._fragments) == 1
    assert climate.settings.b == "changed"
    assert climate.settings.c == C()
    climate.update({"c": {"d": "test"}})
    assert len(climate._fragments) == 2
    assert climate.settings.c == C(d="test")

    climate.update({"c": C(d="test2")})
    assert len(climate._fragments) == 3
    assert climate.settings.c == C(d="test2")

    with pytest.raises(dacite.WrongTypeError):
        # assigning an int to a "str" field should fail
        climate.update({"c": {"d": 4}})
    # no update should have been performed.
    assert len(climate._fragments) == 3
