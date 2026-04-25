from datetime import date
import logging

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