"""Variance calculation + materiality + driver identification."""
import pytest

from app.financial.engine import calculate_monthly_pnl
from app.financial.money import value_to_cents
from app.financial.variance import (
    calculate_variance,
    find_variance_drivers,
    is_material,
)


def test_is_material_basic():
    assert is_material(100000, 115000, materiality_percent=10.0, materiality_abs_cents=5000) is True
    assert is_material(100000, 105000, materiality_percent=10.0, materiality_abs_cents=5000) is False  # only 5%
    assert is_material(100000, 104999, materiality_percent=10.0, materiality_abs_cents=5000) is False
    assert is_material(100000, 105000, materiality_percent=10.0, materiality_abs_cents=10000) is False  # abs too small
    assert is_material(0, 5000 * 2, materiality_percent=10.0, materiality_abs_cents=5000) is True
    assert is_material(0, 4000, materiality_percent=10.0, materiality_abs_cents=5000) is False


def test_calculate_variance():
    v = calculate_variance(100000, 115000, line="revenue",
                           materiality_percent=10.0, materiality_abs_cents=5000)
    assert v.absolute_cents == 15000
    assert v.percent == 15.0
    assert v.material is True
    assert v.previous == 1000.0 and v.current == 1150.0


def test_calculate_variance_zero_denominator():
    v = calculate_variance(0, 60000)
    assert v.percent is None
    assert v.material is True


@pytest.fixture()
def months_seeded(db_session):
    """Seed Jan and Feb data with a material revenue change in food_sales."""
    from tests.sample_data import seed_two_months
    seed_two_months(db_session)
    return db_session


def test_month_variance_report(months_seeded):
    jan = calculate_monthly_pnl(months_seeded, "2026-01")
    feb = calculate_monthly_pnl(months_seeded, "2026-02")
    from app.financial.variance import calculate_month_variance
    variances = {v.line: v for v in calculate_month_variance(jan, feb)}

    revenue = variances["revenue"]
    assert revenue.absolute_cents > 0
    assert revenue.current_cents > revenue.previous_cents
    # percentage is well defined since Jan revenue != 0
    assert revenue.percent is not None


def test_variance_drivers_revenue(months_seeded):
    drivers = find_variance_drivers(months_seeded, "2026-01", "2026-02", "revenue")
    by_code = {d.category_code: d for d in drivers}
    food = by_code["food_sales"]
    assert food.absolute_cents > 0
    assert food.material is True
    assert food.transaction_count > 0
    assert food.transactions[0]["transaction_id"].startswith("T")
    # driver traceable to underlying transactions
    assert len(food.transactions) == food.transaction_count


def test_variance_drivers_invalid_line(months_seeded):
    with pytest.raises(ValueError):
        find_variance_drivers(months_seeded, "2026-01", "2026-02", "operating_profit")


def test_drivers_consistent_with_lines(months_seeded):
    jan = calculate_monthly_pnl(months_seeded, "2026-01")
    feb = calculate_monthly_pnl(months_seeded, "2026-02")
    delta = feb.lines["revenue"].amount_cents - jan.lines["revenue"].amount_cents
    drivers = find_variance_drivers(months_seeded, "2026-01", "2026-02", "revenue")
    total = sum(d.absolute_cents for d in drivers)
    assert total == delta