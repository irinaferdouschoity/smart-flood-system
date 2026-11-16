"""Rainfall indicator: 3-day rainfall compared with each city's historical thresholds.

Pure Python (no database) so it can be tested on its own. The thresholds (95th and 99th percentile of
3-day rainfall) come from data/city_specific_risk.csv; the rainfall itself comes from the newest days stored
in MySQL, so the indicator always has the same date as the charts.
"""
from datetime import date

BELOW = "Below high-rainfall threshold"
HIGH = "High rainfall"
VERY_HIGH = "Very high rainfall"


def three_day_total(rows):
    """rows: (date, precipitation) pairs in any order. Returns (latest_date, total_of_last_3_calendar_days).

    Days with no value are ignored; returns (None, None) when there is no rainfall value at all.
    """
    valid = [(d, float(v)) for d, v in rows if d is not None and v is not None]
    if not valid:
        return None, None
    latest = max(d for d, _ in valid)
    total = sum(v for d, v in valid if 0 <= (latest - d).days <= 2)
    return latest, round(total, 2)


def classify(total: float, threshold_95: float, threshold_99: float) -> str:
    if total >= threshold_99:
        return VERY_HIGH
    if total >= threshold_95:
        return HIGH
    return BELOW


def choose_source(csv_date, live_date):
    """Use the live (MySQL) reading unless it is older than the saved file."""
    if live_date is None:
        return "csv"
    if csv_date is None:
        return "live"
    csv_day = date.fromisoformat(str(csv_date)[:10])
    return "live" if live_date >= csv_day else "csv"
