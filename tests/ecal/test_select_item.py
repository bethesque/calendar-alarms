from datetime import date
import pytest

from ecal import select_item
from ecal.select_item import select_item_by_date  # adjust import


def test_basic_progression():
    items = ["A", "B", "C"]
    period = 7

    assert select_item_by_date(items, date(2026, 1, 1), period) == "A"
    assert select_item_by_date(items, date(2026, 1, 8), period) == "B"
    assert select_item_by_date(items, date(2026, 1, 15), period) == "C"
    assert select_item_by_date(items, date(2026, 1, 22), period) == "A"  # wraps


def test_same_item_within_period():
    items = ["A", "B", "C"]
    period = 7

    # All within first 7 days → same item
    assert select_item_by_date(items, date(2026, 1, 1), period) == "A"
    assert select_item_by_date(items, date(2026, 1, 7), period) == "A"


def test_boundary_transition():
    items = ["A", "B"]
    period = 7

    # Day 7 still first bucket, day 8 moves to next
    assert select_item_by_date(items, date(2026, 1, 7), period) == "A"
    assert select_item_by_date(items, date(2026, 1, 8), period) == "B"


def test_wraparound_multiple_cycles():
    items = ["A", "B", "C"]
    period = 3

    # Move far enough to wrap multiple times
    assert select_item_by_date(items, date(2026, 1, 1), period) == "A"
    assert select_item_by_date(items, date(2026, 1, 10), period) == "A"


def test_single_item_always_returned():
    items = ["only"]
    period = 5

    for day in range(1, 3):
        assert select_item_by_date(items, date(2026, 1, day), period) == "only"


def test_empty_items_raises():
    with pytest.raises(ValueError):
        select_item_by_date([], date(2026, 1, 1), 7)


def test_invalid_period_raises():
    items = ["A"]

    with pytest.raises(ValueError):
        select_item_by_date(items, date(2026, 1, 1), 0)

    with pytest.raises(ValueError):
        select_item_by_date(items, date(2026, 1, 1), -5)


def test_leap_year_handling():
    items = ["A", "B"]
    period = 30

    # Feb 29 exists in leap years
    assert select_item_by_date(items, date(2024, 2, 29), period) in items


def test_different_year_same_day_of_year():
    items = ["A", "B", "C"]
    period = 10

    # Same day-of-year → same result regardless of year
    assert select_item_by_date(items, date(2025, 3, 1), period) == \
           select_item_by_date(items, date(2026, 3, 1), period)