"""Download NASA POWER daily data for all 64 districts + upstream (India) stations.

Files are cached in data/power_daily/<location_id>.csv, so the download is resumable and a
re-run only fetches what is missing or new.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import pandas as pd

from . import config
from .power_api import PowerClientError, PowerError, fetch, load_plan


def points() -> pd.DataFrame:
    """All locations we download: 64 districts and the upstream stations."""
    d = pd.read_csv(config.DISTRICTS_CSV)
    d = d.assign(name=d["district"], kind="district")[["location_id", "name", "latitude", "longitude", "kind"]]
    u = pd.read_csv(config.UPSTREAM_CSV)
    u = u.assign(kind="upstream")[["location_id", "name", "latitude", "longitude", "kind"]]
    return pd.concat([d, u], ignore_index=True)


def _year_chunks(start: date, end: date):
    cur = start
    while cur <= end:
        stop = min(date(cur.year, 12, 31), end)
        yield cur, stop
        cur = stop + timedelta(days=1)


def _fetch_range(lat, lon, start, end, params, community):
    """One request for the whole range; if that fails (timeout, size) fall back to yearly pieces."""
    try:
        return fetch(lat, lon, start, end, params, community)
    except PowerClientError:
        raise
    except PowerError:
        parts = [fetch(lat, lon, a, b, params, community) for a, b in _year_chunks(start, end)]
        return pd.concat(parts).sort_index()


def _download_point(row, plan, start: date, end: date, refresh_days: int, force: bool):
    path = config.POWER_DIR / f"{int(row.location_id)}.csv"
    existing = None
    if path.exists() and not force:
        existing = pd.read_csv(path, index_col="date", parse_dates=True)

    fetch_start = start
    if existing is not None and len(existing):
        if existing.index.min() <= pd.Timestamp(start) + pd.Timedelta(days=3):
            # We already hold the start of the range: only top up the end (re-fetch the last
            # days too, because NASA fills recent days in late).
            fetch_start = max(start, (existing.index.max() - pd.Timedelta(days=refresh_days)).date())
    if fetch_start > end:
        return "up to date"

    parts = []
    for community, params in plan.items():
        parts.append(_fetch_range(row.latitude, row.longitude, fetch_start, end, params, community))
        time.sleep(0.2)
    new = pd.concat(parts, axis=1).sort_index()
    merged = new if existing is None else new.combine_first(existing)
    merged.index.name = "date"
    config.POWER_DIR.mkdir(parents=True, exist_ok=True)
    merged.sort_index().to_csv(path)
    return f"{len(new)} days"


def download_all(start: date, end: date, workers: int = 4, refresh_days: int = 10,
                 force: bool = False, ids=None, log=print) -> dict:
    plan = load_plan(log)
    pts = points()
    if ids:
        pts = pts[pts["location_id"].isin(ids)]
    log(f"Downloading NASA POWER daily data {start} -> {end} for {len(pts)} locations "
        f"({workers} parallel requests) ...")

    lock = threading.Lock()
    done = [0]
    errors = {}

    def work(row):
        try:
            msg = _download_point(row, plan, start, end, refresh_days, force)
            err = None
        except Exception as exc:                       # noqa: BLE001 - report every failure
            msg, err = "", str(exc)
        with lock:
            done[0] += 1
            tag = "ERROR " + err if err else msg
            log(f"  [{done[0]:>2}/{len(pts)}] {row.name_:<28} {tag}")
        return int(row.location_id), err

    rows = list(pts.rename(columns={"name": "name_"}).itertuples())
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(work, r) for r in rows]
        for f in as_completed(futures):
            loc, err = f.result()
            if err:
                errors[loc] = err
    if errors and len(errors) == len(pts):
        raise PowerError("Every download failed - check your internet connection. "
                         f"Example error: {next(iter(errors.values()))}")
    if errors:
        log(f"Finished with {len(errors)} failed location(s); run the command again to retry them.")
    else:
        log("Download complete.")
    return {"locations": len(pts), "errors": errors}
