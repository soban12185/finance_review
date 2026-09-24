"""Deterministic money handling.

Authoritative financial arithmetic is performed in integer cents only.
Floating point is never used for authoritative calculations.

  * ``value_to_cents`` converts raw values (str / int / float / Decimal) to int cents.
  * ``cents_to_amount`` converts int cents to a float dollar amount for display.
  * ``cents_to_decimal`` converts int cents to a ``Decimal`` dollar amount.
"""
from __future__ import annotations

import decimal
from decimal import Decimal

_CENTS = Decimal(100)
ROUND = decimal.ROUND_HALF_UP


def clean_decimal(value) -> Decimal:
    """Convert a raw value into a Decimal without float drift."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value))


def value_to_cents(value) -> int:
    """Convert a monetary value to integer cents exactly.

    Raises ``ValueError`` when the value cannot be interpreted as money.
    """
    try:
        d = clean_decimal(value)
    except (decimal.InvalidOperation, TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid monetary value: {value!r}") from exc
    if not d.is_finite():
        raise ValueError(f"Invalid monetary value: {value!r}")
    cents = d * _CENTS
    if cents != cents.to_integral_value(rounding=ROUND):
        raise ValueError(f"Monetary value has unsupported sub-cent precision: {value!r}")
    return int(cents.to_integral_value(rounding=ROUND))


def cents_to_amount(cents: int) -> float:
    """Convert integer cents to a float dollar amount (display / JSON only)."""
    return int(cents) / 100.0


def cents_to_decimal(cents: int) -> Decimal:
    """Convert integer cents to a ``Decimal`` dollar amount (precise)."""
    return Decimal(int(cents)) / _CENTS


def format_amount(cents: int, thousands_sep: bool = False) -> str:
    """Human friendly dollar string for an integer cents value."""
    sign = "-" if int(cents) < 0 else ""
    d = cents_to_decimal(int(cents)).copy_abs()
    left, _, right = str(d).partition(".")
    if thousands_sep:
        left = f"{int(left):,}"
    return f"{sign}${left}.{right.ljust(2, '0')}"


def pct_change(prev_cents: int, curr_cents: int) -> float | None:
    """Percentage change between two cents amounts.

    Returns None when there is no basis for the comparison (prev == 0).
    The result is a plain float used for display characterised to 4dp.
    """
    prev = int(prev_cents)
    curr = int(curr_cents)
    if prev == 0:
        return None
    return round((curr - prev) / abs(prev) * 100.0, 4)