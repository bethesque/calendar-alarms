from datetime import date
import logging
from vcal.settings import Option
from datetime import datetime
import random

logger = logging.getLogger(__name__)

"""
Utility to select an item from a list based on the date, cycling through items every N days.
Resets at the start of each year.
This is used to change the alarm and announcement music periodically to help prevent the alarms
getting ignored.
"""

def select_item_by_date(items, d: date, period_days: int):
    if not items:
        raise ValueError("items must not be empty")
    if period_days <= 0:
        raise ValueError("period_days must be > 0")

    # Day of year (1–366)
    day_of_year = d.timetuple().tm_yday

    # How many periods have passed
    period_index = (day_of_year - 1) // period_days

    # Wrap around the list
    index = period_index % len(items)

    logger.debug(f"Selecting item for date {d}: day_of_year={day_of_year}, period_index={period_index}, selected_index={index}")

    return items[index]


def select_option(items: list[Option], now: datetime | None = None) -> Option:
    if not items:
        raise ValueError("No items available")

    now = now or datetime.now()

    never_used = [item for item in items if item.last_used is None]

    if never_used:
        selected = random.choice(never_used)
        selected.update_last_used(now)
        return selected


    sorted_items = sorted(items, key=lambda x: x.last_used_datetime(), reverse=True)

    exclude_count = min(
        len(sorted_items) // 4,
        len(sorted_items) - 1,
    )

    candidates = sorted_items[exclude_count:]

    weights = [
        max((now - item.last_used_datetime()).total_seconds(), 1.0) ** 1.5
        for item in candidates
    ]

    selected = random.choices(candidates, weights=weights, k=1)[0]
    selected.update_last_used(now)

    return selected
