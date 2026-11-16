"""Turn the sourced flood-event list into one row per flooded district-day."""
import pandas as pd

from . import config
from .names import norm


def build_labels(write: bool = True) -> pd.DataFrame:
    events = pd.read_csv(config.EVENTS_CSV)
    districts = pd.read_csv(config.DISTRICTS_CSV)
    known = {norm(n): (int(i), n) for i, n in zip(districts["location_id"], districts["district"])}

    rows, problems = [], []
    for e in events.itertuples():
        start, end = pd.Timestamp(e.start_date), pd.Timestamp(e.end_date)
        if end < start:
            problems.append(f"{e.event_id}: end date is before start date")
            continue
        for name in str(e.districts).split(";"):
            hit = known.get(norm(name))
            if hit is None:
                problems.append(f"{e.event_id}: unknown district '{name.strip()}'")
                continue
            for day in pd.date_range(start, end):
                rows.append({"district": hit[1], "location_id": hit[0], "date": day.date(),
                             "flooded": 1, "event_id": e.event_id, "confidence": e.confidence,
                             "flood_type": getattr(e, "flood_type", "")})
    if problems:
        raise ValueError("Fix these problems in bd_flood_events.csv:\n  " + "\n  ".join(problems))

    out = pd.DataFrame(rows).sort_values(["date", "district"]).reset_index(drop=True)
    if write:
        out.to_csv(config.LABELS_CSV, index=False)
    return out
