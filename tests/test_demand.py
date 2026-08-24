"""SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA."""

from decimal import Decimal

import pytest

from coolaccess.demand import as_finite_decimal, calculate_heat_weighted_demand, exact_sum


@pytest.mark.parametrize(
    ("population", "priority", "expected"),
    [
        ("0", "1", "0"),
        ("100", "0", "0"),
        ("100", "1", "100"),
        ("0.1", "0.2", "0.02"),
        ("123.456", "0.789", "97.406784"),
    ],
)
def test_heat_weighted_demand_is_exact(population: str, priority: str, expected: str) -> None:
    assert calculate_heat_weighted_demand(Decimal(population), Decimal(priority)) == Decimal(
        expected
    )


@pytest.mark.parametrize(
    ("population", "priority"),
    [("-1", "0.5"), ("1", "-0.1"), ("1", "1.1"), ("NaN", "0.5"), ("1", "Infinity")],
)
def test_invalid_demand_inputs_fail(population: str, priority: str) -> None:
    with pytest.raises(ValueError):
        calculate_heat_weighted_demand(Decimal(population), Decimal(priority))


def test_exact_sum_avoids_order_sensitive_loss() -> None:
    values = (Decimal("1000000000000000000000"), Decimal("0.000000000001"), Decimal("2"))
    expected = Decimal("1000000000000000000002.000000000001")
    assert exact_sum(values) == expected
    assert exact_sum(reversed(values)) == expected


def test_binary_float_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="binary floating-point"):
        as_finite_decimal(0.1)
