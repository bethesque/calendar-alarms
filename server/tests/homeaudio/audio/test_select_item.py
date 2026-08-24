from datetime import date, datetime, timedelta

import pytest

from homeaudio.audio import select_item
from homeaudio.audio.select_item import select_item_by_date, select_option
from homeaudio.audio.settings import Option


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


def test_no_items_raises():
    with pytest.raises(ValueError):
        select_option([])


def test_selects_never_used_item_and_updates_last_used():
    now = datetime(2026, 1, 1, 12, 0, 0)
    used = Option(text="used", last_used=(now - timedelta(days=5)).isoformat())
    unused = Option(text="unused", last_used=None)

    result = select_option([used, unused], now=now)

    assert result is unused
    assert result.last_used_datetime() == now
    # untouched items are not updated as a side effect
    assert used.last_used_datetime() == now - timedelta(days=5)


def test_multiple_never_used_only_candidates_are_never_used(monkeypatch):
    now = datetime(2026, 1, 1)
    used = Option(text="used", last_used=now.isoformat())
    unused1 = Option(text="u1")
    unused2 = Option(text="u2")

    captured = {}

    def fake_choice(seq):
        captured["seq"] = list(seq)
        return seq[0]

    monkeypatch.setattr(select_item.random, "choice", fake_choice)

    result = select_option([used, unused1, unused2], now=now)

    assert captured["seq"] == [unused1, unused2]
    assert result is unused1
    assert result.last_used_datetime() == now


def test_all_used_excludes_most_recently_used_quarter(monkeypatch):
    now = datetime(2026, 1, 10)
    # 4 items -> exclude_count = min(4 // 4, 3) = 1, so only the single
    # most-recently-used item is excluded from candidates.
    oldest = Option(text="oldest", last_used=(now - timedelta(days=40)).isoformat())
    old = Option(text="old", last_used=(now - timedelta(days=30)).isoformat())
    recent = Option(text="recent", last_used=(now - timedelta(days=5)).isoformat())
    most_recent = Option(text="most_recent", last_used=(now - timedelta(days=1)).isoformat())
    items = [oldest, old, recent, most_recent]

    captured = {}

    def fake_choices(population, weights, k):
        captured["population"] = list(population)
        captured["weights"] = weights
        return [population[0]]

    monkeypatch.setattr(select_item.random, "choices", fake_choices)

    select_option(items, now=now)

    assert not any(candidate is most_recent for candidate in captured["population"])
    assert len(captured["population"]) == 3
    for item in (oldest, old, recent):
        assert any(candidate is item for candidate in captured["population"])


def test_single_used_item_is_returned_without_exclusion():
    now = datetime(2026, 1, 10)
    only = Option(text="only", last_used=(now - timedelta(days=1)).isoformat())

    result = select_option([only], now=now)

    assert result is only
    assert result.last_used_datetime() == now


def test_weights_favor_longer_elapsed_time(monkeypatch):
    now = datetime(2026, 1, 10)
    a = Option(text="a", last_used=(now - timedelta(seconds=100)).isoformat())
    b = Option(text="b", last_used=(now - timedelta(seconds=1000)).isoformat())

    captured = {}

    def fake_choices(population, weights, k):
        captured["population"] = list(population)
        captured["weights"] = weights
        return [population[0]]

    monkeypatch.setattr(select_item.random, "choices", fake_choices)

    select_option([a, b], now=now)

    index_a = captured["population"].index(a)
    index_b = captured["population"].index(b)
    assert captured["weights"][index_a] == pytest.approx(100 ** 1.5)
    assert captured["weights"][index_b] == pytest.approx(1000 ** 1.5)


def test_weight_floor_for_zero_elapsed_time(monkeypatch):
    now = datetime(2026, 1, 10)
    just_used = Option(text="just_used", last_used=now.isoformat())
    long_ago = Option(text="long_ago", last_used=(now - timedelta(seconds=50)).isoformat())

    captured = {}

    def fake_choices(population, weights, k):
        captured["population"] = list(population)
        captured["weights"] = weights
        return [population[0]]

    monkeypatch.setattr(select_item.random, "choices", fake_choices)

    select_option([just_used, long_ago], now=now)

    index_just_used = captured["population"].index(just_used)
    assert captured["weights"][index_just_used] == pytest.approx(1.0 ** 1.5)


def test_selected_item_last_used_is_updated_to_now(monkeypatch):
    now = datetime(2026, 1, 10)
    a = Option(text="a", last_used=(now - timedelta(days=10)).isoformat())
    b = Option(text="b", last_used=(now - timedelta(days=20)).isoformat())

    monkeypatch.setattr(
        select_item.random,
        "choices",
        lambda population, weights, k: [population[-1]],
    )

    result = select_option([a, b], now=now)

    assert result.last_used_datetime() == now


def test_defaults_now_when_not_provided():
    unused = Option(text="unused")

    before = datetime.now()
    result = select_option([unused])
    after = datetime.now()

    assert before <= result.last_used_datetime() <= after
