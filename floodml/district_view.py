"""Per-district view of the data (used by the dashboard): prediction, recent weather, flood events."""
import json

import pandas as pd

from . import config
from .names import norm


def list_districts() -> list:
    d = pd.read_csv(config.DISTRICTS_CSV)
    return [{"location_id": int(r.location_id), "district": r.district, "division": r.division,
             "latitude": float(r.latitude), "longitude": float(r.longitude)} for r in d.itertuples()]


def events_for(district: str) -> list:
    """Documented flood events that included this district, newest first (shaped like the dashboard's history table)."""
    if not config.EVENTS_CSV.exists():
        return []
    ev = pd.read_csv(config.EVENTS_CSV)
    key = norm(district)
    rows = []
    for e in ev.itertuples():
        if key in {norm(n) for n in str(e.districts).split(";")}:
            rows.append({"event_date": f"{e.start_date} to {e.end_date}", "severity": f"{e.confidence} confidence",
                         "description": f"{e.event_name} ({str(e.flood_type).replace('_', ' ')}). {e.notes}",
                         "_start": e.start_date})
    rows.sort(key=lambda r: r["_start"], reverse=True)
    for r in rows:
        r.pop("_start")
    return rows


def _weather_from_db(location_id: int, days: int) -> list:
    """Hosted copy: no CSV cache, so read the daily weather from the bundled SQLite file (flood.db)."""
    import sqlite3
    db_file = config.ROOT / "flood.db"
    if not db_file.exists():
        return []
    con = sqlite3.connect(db_file)
    try:
        rows = con.execute(
            "SELECT observation_date, COALESCE(imerg_precip, pcorr_precip, rain_mm), t2m, rh2m "
            "FROM bd_daily_data WHERE location_id=? ORDER BY observation_date DESC LIMIT ?",
            (int(location_id), int(days))).fetchall()
    finally:
        con.close()
    return [{"date": r[0], "precipitation": r[1], "temperature_avg": r[2], "humidity": r[3]} for r in reversed(rows)]


def weather_series(location_id: int, days: int = 90) -> list:
    p = config.POWER_DIR / f"{int(location_id)}.csv"
    if not p.exists():
        return _weather_from_db(location_id, days)
    df = pd.read_csv(p, index_col="date", parse_dates=True).sort_index()
    rain = df["IMERG_PRECTOT"].fillna(df["PRECTOTCORR"]) if "IMERG_PRECTOT" in df.columns else df.get("PRECTOTCORR")
    out = pd.DataFrame({
        "precipitation": rain,
        "temperature_avg": df.get("T2M"),
        "humidity": df.get("RH2M"),
    })
    out = out.dropna(how="all").tail(days)
    out = out.astype(object).where(out.notna(), None)
    return [{"date": d.date().isoformat(), "precipitation": r.precipitation,
             "temperature_avg": r.temperature_avg, "humidity": r.humidity} for d, r in out.iterrows()]


def latest_prediction(location_id: int):
    if not config.PRED_JSON.exists():
        return None, None
    payload = json.loads(config.PRED_JSON.read_text(encoding="utf-8"))
    for row in payload["districts"]:
        if int(row.get("location_id", -1)) == int(location_id):
            return row, payload["meta"]
    return None, payload["meta"]


def district_payload(location_id: int, days: int = 90) -> dict:
    match = [d for d in list_districts() if d["location_id"] == int(location_id)]
    if not match:
        raise KeyError(location_id)
    d = match[0]
    pred, meta = latest_prediction(location_id)
    weather = weather_series(location_id, days)
    notes = []
    if not weather:
        notes.append("No NASA data downloaded for this district yet. Run run_ml.bat (option 1) or: python -m floodml download")
    if pred is None:
        notes.append("No prediction yet. Run run_ml.bat (option 1) or: python -m floodml all")
    return {**d, "prediction": pred, "prediction_meta": meta, "weather": weather,
            "history": events_for(d["district"]), "notes": notes}
