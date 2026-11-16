"""Assemble the full training table: features + flood labels, one row per district per day."""
from datetime import date, timedelta

import pandas as pd

from . import config
from .features import build_features, load_power
from .labels import build_labels


def build_dataset(start: str = config.DEFAULT_START, end: str = config.LABELS_COMPLETE_UNTIL,
                  buffer_days: int = config.RECESSION_BUFFER_DAYS, write: bool = True,
                  rebuild_labels: bool = True) -> pd.DataFrame:
    districts = pd.read_csv(config.DISTRICTS_CSV)
    upstream = pd.read_csv(config.UPSTREAM_CSV)
    power = load_power(list(districts["location_id"]) + list(upstream["location_id"]))
    feats = build_features(power, districts, upstream)
    feats["date"] = pd.to_datetime(feats["date"])
    feats = feats[(feats["date"] >= pd.Timestamp(start)) & (feats["date"] <= pd.Timestamp(end))]
    if feats.empty:
        raise ValueError("No data in the requested period - download NASA POWER data first.")

    labels = build_labels(write=True) if (rebuild_labels or not config.LABELS_CSV.exists()) \
        else pd.read_csv(config.LABELS_CSV)
    labels["date"] = pd.to_datetime(labels["date"])

    per_day = (labels.groupby(["location_id", "date"])
               .agg(event_id=("event_id", lambda s: ";".join(sorted(set(s)))),
                    flood_type=("flood_type", lambda s: ";".join(sorted(set(map(str, s))))),
                    label_confidence=("confidence", lambda s: min(s, key=["low", "medium", "high"].index)))
               .reset_index())
    df = feats.merge(per_day, on=["location_id", "date"], how="left")
    df["flooded"] = df["event_id"].notna().astype(int)

    # days right after an event ends: water may still be standing -> neither "flood" nor "no flood"
    df["label_status"] = df["flooded"].map({1: "flood", 0: "no_flood"})
    ends = labels.groupby(["location_id", "event_id"])["date"].max().reset_index()
    buf = []
    for e in ends.itertuples():
        for k in range(1, buffer_days + 1):
            buf.append((e.location_id, e.date + pd.Timedelta(days=k)))
    if buf:
        b = pd.DataFrame(buf, columns=["location_id", "date"]).drop_duplicates().assign(_buf=1)
        df = df.merge(b, on=["location_id", "date"], how="left")
        df.loc[(df["_buf"] == 1) & (df["flooded"] == 0), "label_status"] = "recession_buffer"
        df = df.drop(columns="_buf")

    meta = districts[["location_id", "district", "division"]]
    df = df.merge(meta, on="location_id", how="left")
    first = ["location_id", "district", "division", "date"]
    last = ["flooded", "label_status", "event_id", "flood_type", "label_confidence"]
    df = df[first + [c for c in df.columns if c not in first + last] + last]
    df = df.sort_values(["location_id", "date"]).reset_index(drop=True)
    if write:
        df.to_csv(config.DATASET_CSV, index=False)
    return df
