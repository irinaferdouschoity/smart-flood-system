"""Feature engineering from NASA POWER daily data (all features use only today and earlier days)."""
import numpy as np
import pandas as pd

from . import config

RAIN_WINDOWS = (2, 3, 5, 7, 14, 30)

# Column names that are NOT model inputs (identifiers, dates and label information).
META_COLS = {"location_id", "district", "division", "date", "flooded", "event_id", "flood_type",
             "label_confidence", "label_status", "target"}


def load_power(ids) -> dict:
    out = {}
    for i in ids:
        p = config.POWER_DIR / f"{int(i)}.csv"
        if p.exists():
            out[int(i)] = pd.read_csv(p, index_col="date", parse_dates=True).sort_index()
    return out


def _col(df, name):
    return df[name] if name in df.columns else pd.Series(np.nan, index=df.index)


def _rain(df) -> pd.Series:
    """IMERG satellite rainfall, falling back to NASA's corrected precipitation where IMERG is missing."""
    return _col(df, config.IMERG_PARAM).fillna(_col(df, "PRECTOTCORR"))


def _daily(df: pd.DataFrame) -> pd.DataFrame:
    full = pd.date_range(df.index.min(), df.index.max(), freq="D")
    out = df.reindex(full)
    out.index.name = "date"
    return out


def point_features(df: pd.DataFrame) -> pd.DataFrame:
    g = _daily(df)
    r = _rain(g)
    out = pd.DataFrame(index=g.index)
    out["rain_1d"] = r
    for w in RAIN_WINDOWS:
        out[f"rain_{w}d"] = r.rolling(w, min_periods=w).sum()
    out["rain_max_7d"] = r.rolling(7, min_periods=7).max()
    out["wet_days_7d"] = (r >= 1).astype(float).where(r.notna()).rolling(7, min_periods=7).sum()
    out["rain_prior_8_30d"] = out["rain_30d"] - out["rain_7d"]      # how wet the ground already was

    pc = _col(g, "PRECTOTCORR")
    for w in (3, 7, 14):
        out[f"pcorr_{w}d"] = pc.rolling(w, min_periods=w).sum()

    for src, name in (("GWETTOP", "soil_top"), ("GWETROOT", "soil_root"), ("GWETPROF", "soil_prof")):
        out[name] = _col(g, src)
    out["soil_root_chg7"] = out["soil_root"] - out["soil_root"].shift(7)

    for src, name in (("T2M", "temp"), ("T2M_MAX", "temp_max"), ("T2M_MIN", "temp_min"),
                      ("T2MDEW", "dewpoint"), ("RH2M", "humidity"), ("WS2M", "wind"),
                      ("PS", "pressure"), ("ALLSKY_SFC_SW_DWN", "solar")):
        out[name] = _col(g, src)
    out["pressure_chg3"] = out["pressure"] - out["pressure"].shift(3)   # falling pressure = low-pressure system

    doy = out.index.dayofyear.to_numpy()
    out["season_sin"] = np.sin(2 * np.pi * doy / 365.25)
    out["season_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return out


def build_features(power: dict, districts: pd.DataFrame, upstream: pd.DataFrame) -> pd.DataFrame:
    """One row per district per day. Includes upstream (India) rainfall and regional context."""
    # upstream rainfall (river headwaters outside Bangladesh)
    up_cols = []
    for u in upstream.itertuples():
        if int(u.location_id) not in power:
            continue
        pf = point_features(power[int(u.location_id)])
        up = pf[["rain_3d", "rain_7d"]].rename(columns={"rain_3d": f"up_{u.key}_3d",
                                                        "rain_7d": f"up_{u.key}_7d"})
        up_cols.append(up)
    up_all = pd.concat(up_cols, axis=1) if up_cols else pd.DataFrame()

    parts = []
    for d in districts.itertuples():
        if int(d.location_id) not in power:
            continue
        f = point_features(power[int(d.location_id)])
        if len(up_all):
            f = f.join(up_all, how="left")
        f["location_id"] = int(d.location_id)
        f["latitude"] = float(d.latitude)
        f["longitude"] = float(d.longitude)
        f["division"] = d.division
        parts.append(f.reset_index())
    if not parts:
        raise ValueError("No NASA POWER files found. Run:  python -m floodml download")
    df = pd.concat(parts, ignore_index=True)

    # regional context: how wet is the whole division / country today?
    for w in (3, 7):
        df[f"div_rain_{w}d"] = df.groupby(["division", "date"])[f"rain_{w}d"].transform("mean")
        df[f"nat_rain_{w}d"] = df.groupby("date")[f"rain_{w}d"].transform("mean")
    return df.drop(columns=["division"])
