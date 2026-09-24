"""Money utilities are the foundation - test exactness carefully."""
import pytest

from app.financial.money import (
    cents_to_amount,
    cents_to_decimal,
    format_amount,
    pct_change,
    value_to_cents,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("17.10", 1710),
        (123.45, 12345),
        ("123.45", 12345),
        (0, 0),
        (-52.30, -5230),
        ("0.1", 10),
        ("0.29", 29),
        ("9999999.99", 999999999),
        ("-0.01", -1),
    ],
)
def test_value_to_cents_exact(raw, expected):
    assert value_to_cents(raw) == expected


def test_float_no_binary_drift():
    # 0.1 + 0.2 == 0.3 in floats would be 0.30000000000000004;
    # our decimal conversion keeps 0.3 -> 30 cents.
    assert value_to_cents(0.1) == 10
    assert value_to_cents(0.2) == 20
    assert value_to_cents(0.3) == 30


@pytest.mark.parametrize("bad", [None, "", "abc", "12.3456", float("nan"), "12,4"])
def test_value_to_cents_invalid(bad):
    with pytest.raises(ValueError):
        value_to_cents(bad)


def test_sub_cent_rejected():
    with pytest.raises(ValueError):
        value_to_cents("0.001")


def test_conversions_roundtrip():
    assert cents_to_amount(12345) == pytest.approx(123.45)
    assert cents_to_decimal(12345) == __import__("decimal").Decimal("123.45")


def test_format_amount():
    assert format_amount(12345) == "$123.45"
    assert format_amount(-12345) == "-$123.45"
    assert format_amount(1234567, thousands_sep=True) == "$12,345.67"


def test_pct_change():
    assert pct_change(10000, 15000) == 50.0
    assert pct_change(10000, 5000) == -50.0
    assert pct_change(0, 5000) is None
    assert pct_change(-10000, -5000) == 50.0


def test_formulas_consistency_engine_semantics():
    # Gross Profit = Revenue - |COGS| == Revenue + COGS (negative)
    revenue = value_to_cents("1000.00")
    cogs = value_to_cents("-400.00")
    assert revenue + cogs == value_to_cents("600.00")

    gp = revenue + cogs
    payroll = value_to_cents("-200.00")
    opex = value_to_cents("-100.00")
    assert gp + payroll + opex == value_to_cents("300.00")