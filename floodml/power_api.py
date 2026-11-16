"""Small, robust client for the NASA POWER daily point API."""
import json
import time
from datetime import date, timedelta

import pandas as pd
import requests

from . import config

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"


class PowerError(RuntimeError):
    """Temporary or unexpected problem (network, server)."""


class PowerClientError(PowerError):
    """The request itself was rejected (HTTP 4xx) - retrying will not help."""


def _parse(payload: dict, parameters) -> pd.DataFrame:
    block = payload.get("properties", {}).get("parameter")
    if not block:
        raise PowerError("NASA POWER returned no data block")
    cols = {}
    for p in parameters:
        if p in block:
            s = pd.Series(block[p], dtype="float64")
            s.index = pd.to_datetime(s.index, format="%Y%m%d")
            cols[p] = s.where(s > -990)          # -999 = "no data"
    if not cols:
        raise PowerError("NASA POWER response contained none of the requested parameters")
    df = pd.DataFrame(cols).sort_index()
    df.index.name = "date"
    return df


def fetch(lat, lon, start: date, end: date, parameters, community,
          timeout=60, retries=4, session=None) -> pd.DataFrame:
    """Download daily values for one point. Returns a DataFrame indexed by date (NaN = no data)."""
    params = {
        "parameters": ",".join(parameters),
        "community": community,
        "latitude": round(float(lat), 4),
        "longitude": round(float(lon), 4),
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    http = session or requests
    last = None
    for attempt in range(retries):
        try:
            r = http.get(URL, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last = exc
            time.sleep(min(30, 2 ** attempt))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            last = PowerError(f"HTTP {r.status_code}")
            time.sleep(min(60, 3 * 2 ** attempt))
            continue
        if 400 <= r.status_code < 500:
            raise PowerClientError(f"HTTP {r.status_code}: {r.text[:300]}")
        try:
            return _parse(r.json(), parameters)
        except (ValueError, PowerError) as exc:
            last = exc
            time.sleep(min(30, 2 ** attempt))
    raise PowerError(f"NASA POWER request failed after {retries} tries: {last}")


# ---- which parameter is available in which community ----------------------------------

def build_plan(log=print, lat=23.8103, lon=90.4125) -> dict:
    """Probe the API once and decide, per community, which parameters to request.

    POWER only serves some parameters in some "communities" (AG, SB, RE). This finds a working
    combination for every parameter and saves it, so later downloads are simple and fast.
    """
    candidates = list(config.MAIN_PARAMS) + [config.IMERG_PARAM]
    end = date.today() - timedelta(days=12)
    start = end - timedelta(days=20)
    remaining = list(candidates)
    plan: dict[str, list] = {}

    for community in config.COMMUNITIES:
        if not remaining:
            break
        try:
            df = fetch(lat, lon, start, end, remaining, community, retries=2)
            ok = [p for p in remaining if p in df.columns]
        except PowerClientError:
            ok = []
            for p in remaining:                      # find the individual parameters that work
                try:
                    df = fetch(lat, lon, start, end, [p], community, retries=2)
                    if p in df.columns:
                        ok.append(p)
                except PowerClientError:
                    pass
        if ok:
            plan[community] = ok
            remaining = [p for p in remaining if p not in ok]
            log(f"  community {community}: {', '.join(ok)}")

    if remaining:
        log(f"  NOT available from NASA POWER (will be skipped): {', '.join(remaining)}")
    if not any(p in sum(plan.values(), []) for p in ("PRECTOTCORR", config.IMERG_PARAM)):
        raise PowerError("Neither IMERG nor corrected precipitation is available - cannot continue.")

    config.POWER_DIR.mkdir(parents=True, exist_ok=True)
    config.PLAN_JSON.write_text(json.dumps(plan, indent=2))
    return plan


def load_plan(log=print) -> dict:
    if config.PLAN_JSON.exists():
        return json.loads(config.PLAN_JSON.read_text())
    log("Checking which NASA POWER parameters are available ...")
    return build_plan(log)
