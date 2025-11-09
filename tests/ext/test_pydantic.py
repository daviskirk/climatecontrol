#!/usr/bin/env python3
import pytest

try:
    from pydantic import BaseModel, ValidationError
except ImportError:
    pytest.skip("pydantic not installed", allow_module_level=True)

from climatecontrol.ext.pydantic import Climate


def test_climate_simple(mock_empty_os_environ):
    """Test basic pydantic climate object."""

    class A(BaseModel):
        a: int = 1
        b: str = "yeah"

    climate = Climate(model=A)
    assert climate.settings.a == 1
    assert climate.settings.b == "yeah"


def test_climate(mock_empty_os_environ):
    """Test climate with pydantic models."""

    class C(BaseModel):
        d: str = "weee"
        e: int = 0

    class A(BaseModel):
        c: C = C()
        a: int = 1
        b: str = "yeah"

    climate = Climate(model=A)
    assert climate.settings.c.d == "weee"
    climate.update({"b": "changed"})
    assert len(climate._fragments) == 1
    assert climate.settings.b == "changed"
    assert climate.settings.c.d == "weee"
    assert climate.settings.c.e == 0

    climate.update({"c": {"d": "test"}})
    assert len(climate._fragments) == 2
    assert climate.settings.c.d == "test"

    climate.update({"c": C(d="test2")})
    assert len(climate._fragments) == 3
    assert climate.settings.c.d == "test2"

    with pytest.raises(ValidationError):
        # assigning a list to a "str" field should fail
        climate.update({"c": {"d": [1, 2, 3]}})
    # no update should have been performed.
    assert len(climate._fragments) == 3


def test_climate_nested_models(mock_empty_os_environ):
    """Test climate with nested pydantic models."""

    class D(BaseModel):
        value: str = "nested"

    class C(BaseModel):
        d: D = D()
        name: str = "middle"

    class A(BaseModel):
        c: C = C()
        a: int = 1

    climate = Climate(model=A)
    assert climate.settings.c.d.value == "nested"
    assert climate.settings.c.name == "middle"
    assert climate.settings.a == 1

    climate.update({"c": {"d": {"value": "updated"}}})
    assert climate.settings.c.d.value == "updated"


def test_climate_type_validation(mock_empty_os_environ):
    """Test that pydantic type validation works."""

    class A(BaseModel):
        number: int
        flag: bool = False

    climate = Climate(model=A)

    climate.update({"number": 42})
    assert climate.settings.number == 42

    climate.update({"flag": True})
    assert climate.settings.flag is True

    # String to int should work for valid integers
    climate.update({"number": "123"})
    assert climate.settings.number == 123

    # Invalid type conversion should fail
    with pytest.raises(ValidationError):
        climate.update({"number": "not a number"})


def test_climate_with_defaults(mock_empty_os_environ):
    """Test climate with default values."""

    class Settings(BaseModel):
        host: str = "localhost"
        port: int = 8080
        debug: bool = False

    climate = Climate(model=Settings)
    assert climate.settings.host == "localhost"
    assert climate.settings.port == 8080
    assert climate.settings.debug is False

    climate.update({"port": 3000, "debug": True})
    assert climate.settings.host == "localhost"  # unchanged
    assert climate.settings.port == 3000
    assert climate.settings.debug is True
