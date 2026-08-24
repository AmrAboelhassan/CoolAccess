"""Exact provider-neutral heat-weighted-demand arithmetic."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation, localcontext
from math import ceil, log10


def as_finite_decimal(value: Decimal | int | float | str) -> Decimal:
    """Convert a supported numeric value to a finite canonical Decimal."""

    if isinstance(value, bool):
        raise ValueError("boolean values are not valid numeric inputs")
    if isinstance(value, float):
        raise ValueError("binary floating-point inputs are not accepted")
    try:
        converted = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("value must be a valid decimal number") from exc
    if not converted.is_finite():
        raise ValueError("numeric values must be finite")
    return canonical_decimal(converted)


def canonical_decimal(value: Decimal) -> Decimal:
    """Remove insignificant trailing zeroes without context rounding."""

    if not value.is_finite():
        raise ValueError("numeric values must be finite")
    if value == 0:
        return Decimal(0)
    sign, digits_tuple, raw_exponent = value.as_tuple()
    if not isinstance(raw_exponent, int):
        raise ValueError("numeric values must be finite")
    exponent = raw_exponent
    digits = list(digits_tuple)
    while digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    return Decimal((sign, tuple(digits), exponent))


def exact_product(left: Decimal, right: Decimal) -> Decimal:
    """Multiply terminating Decimals with enough local precision for an exact result."""

    precision = max(28, len(left.as_tuple().digits) + len(right.as_tuple().digits) + 2)
    with localcontext() as context:
        context.prec = precision
        return canonical_decimal(left * right)


def exact_sum(values: Iterable[Decimal]) -> Decimal:
    """Sum terminating Decimals in a precision sized from their aligned coefficients."""

    materialized = tuple(values)
    if not materialized:
        return Decimal(0)
    if any(not value.is_finite() for value in materialized):
        raise ValueError("numeric values must be finite")
    exponents = tuple(value.as_tuple().exponent for value in materialized)
    if not all(isinstance(exponent, int) for exponent in exponents):
        raise ValueError("numeric values must be finite")
    finite_exponents = tuple(int(exponent) for exponent in exponents)
    minimum_exponent = min(finite_exponents)
    aligned_digits = max(
        len(value.as_tuple().digits) + exponent - minimum_exponent
        for value, exponent in zip(materialized, finite_exponents, strict=True)
    )
    carry_digits = ceil(log10(len(materialized))) if len(materialized) > 1 else 0
    with localcontext() as context:
        context.prec = max(28, aligned_digits + carry_digits + 2)
        return canonical_decimal(sum(materialized, Decimal(0)))


def exact_mean(values: Iterable[Decimal]) -> Decimal:
    """Return a deterministic Decimal mean for a non-empty collection."""

    materialized = tuple(values)
    if not materialized:
        raise ValueError("cannot calculate a mean for an empty collection")
    total = exact_sum(materialized)
    with localcontext() as context:
        context.prec = max(28, len(total.as_tuple().digits) + 18)
        return canonical_decimal(total / Decimal(len(materialized)))


def calculate_heat_weighted_demand(population: Decimal, thermal_priority: Decimal) -> Decimal:
    """Calculate the scenario-relative planning weight population times thermal priority."""

    population_value = as_finite_decimal(population)
    priority_value = as_finite_decimal(thermal_priority)
    if population_value < 0:
        raise ValueError("population must be non-negative")
    if priority_value < 0 or priority_value > 1:
        raise ValueError("thermal_priority must be in the inclusive range [0, 1]")
    return exact_product(population_value, priority_value)
