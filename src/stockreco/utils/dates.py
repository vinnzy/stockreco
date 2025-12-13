from __future__ import annotations
import datetime as dt

def parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)

def today_ist() -> dt.date:
    # We don't compute timezone here; caller supplies target-date explicitly for reproducibility.
    return dt.date.today()

def previous_business_day(d: dt.date) -> dt.date:
    # NSE trading calendar has holidays; this is a simple fallback.
    # For accuracy, later replace with an NSE holiday calendar.
    wd = d.weekday()
    if wd == 0:  # Monday -> Friday
        return d - dt.timedelta(days=3)
    if wd == 6:  # Sunday -> Friday
        return d - dt.timedelta(days=2)
    if wd == 5:  # Saturday -> Friday
        return d - dt.timedelta(days=1)
    return d - dt.timedelta(days=1)
