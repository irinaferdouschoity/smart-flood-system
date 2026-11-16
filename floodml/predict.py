"""Score all 64 districts with the trained model using the newest NASA POWER data."""
import json
from datetime import date, datetime, timedelta

import joblib
import numpy as np
import pandas as pd

from . import config
from .download import download_all
from .features import build_features, load_power

CAVEAT = ("Research model. NASA POWER data lags real time by a few days, so this describes recent "
          "conditions - it is not a weather forecast and not an official flood warning. "
          "Follow FFWC / BMD bulletins for decisions.")


def load_bundle():
    if not config.MODEL_PATH.exists():
        raise FileNotFoundError("No trained model found. Run:  python -m floodml train")
    return joblib.load(config.MODEL_PATH)


def _level(p, levels):
    if p >= levels["very_high"]:
        return "VERY HIGH"
    if p >= levels["high"]:
        return "HIGH"
    if p >= levels["moderate"]:
        return "MODERATE"
    return "LOW"


def run_predict(refresh: bool = True, days: int = 75, workers: int = 4, log=print) -> pd.DataFrame:
    bundle = load_bundle()
    if refresh:
        end = date.today() - timedelta(days=1)
        download_all(end - timedelta(days=days), end, workers=workers, refresh_days=10, log=log)

    districts = pd.read_csv(config.DISTRICTS_CSV)
    upstream = pd.read_csv(config.UPSTREAM_CSV)
    power = load_power(list(districts["location_id"]) + list(upstream["location_id"]))
    feats = build_features(power, districts, upstream)
    feats["date"] = pd.to_datetime(feats["date"])

    # newest day for which (almost) every district has rainfall and weather
    have = feats[["rain_7d", "temp"]].notna().all(axis=1)
    need = have.groupby(feats["date"]).mean()
    ready = need[need >= 0.8]
    if ready.empty:
        raise ValueError("Not enough recent NASA POWER data. Run:  python -m floodml download")
    as_of = ready.index.max()
    day = feats[feats["date"] == as_of].copy()

    cols = bundle["features"]
    X = day.reindex(columns=cols)
    score = bundle["model"].predict_proba(X)[:, 1]
    prob = bundle["calibrator"].predict(score)

    meta = districts.set_index("location_id")
    out = pd.DataFrame({
        "location_id": day["location_id"].astype(int).to_numpy(),
        "district": meta.loc[day["location_id"], "district"].to_numpy(),
        "division": meta.loc[day["location_id"], "division"].to_numpy(),
        "latitude": day["latitude"].to_numpy(), "longitude": day["longitude"].to_numpy(),
        "as_of": as_of.date().isoformat(), "horizon_days": bundle["horizon_days"],
        "score": np.round(score, 4), "probability": np.round(prob, 4),
        "risk_level": [_level(p, bundle["levels"]) for p in prob],
        "rain_1d_mm": day["rain_1d"].round(1).to_numpy(),
        "rain_3d_mm": day["rain_3d"].round(1).to_numpy(),
        "rain_7d_mm": day["rain_7d"].round(1).to_numpy(),
        "soil_wetness_root": day["soil_root"].round(2).to_numpy(),
    })
    out = out.sort_values(["probability", "rain_3d_mm"], ascending=False).reset_index(drop=True)
    out.insert(0, "rank", np.arange(1, len(out) + 1))

    config.OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(config.PRED_CSV, index=False)
    meta_json = {
        "as_of": as_of.date().isoformat(), "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "horizon_days": bundle["horizon_days"], "model_trained_at": bundle["metrics"]["trained_at"],
        "levels": bundle["levels"], "counts": out["risk_level"].value_counts().to_dict(),
        "caveat": CAVEAT,
    }
    config.PRED_JSON.write_text(json.dumps({"meta": meta_json, "districts": out.to_dict(orient="records")}, indent=1))
    log(f"Predictions as of {as_of.date()} saved to {config.PRED_CSV}")
    log("Risk levels: " + ", ".join(f"{k} {v}" for k, v in meta_json["counts"].items()))
    return out
