"""Train and honestly evaluate the district flood model.

Evaluation = leave-one-year-out cross-validation: each calendar year is held out in turn, the
model is trained on the other years and predicts the held-out year. Together these "out-of-fold"
predictions are used for every metric, the alert threshold and the probability calibration.
"""
import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

from . import __version__, config
from .features import META_COLS


def load_dataset(path=config.DATASET_CSV) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError("Dataset not found. Run:  python -m floodml dataset")
    df = pd.read_csv(path, parse_dates=["date"], low_memory=False)
    return df.sort_values(["location_id", "date"]).reset_index(drop=True)


def feature_columns(df: pd.DataFrame):
    """Model inputs: numeric, non-label columns that actually vary (empty/constant ones are dropped,
    e.g. a NASA parameter that is not available for this region)."""
    return [c for c in df.columns
            if c not in META_COLS and df[c].dtype != object and df[c].nunique(dropna=True) >= 2]


def make_target(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """target = 1 if the district floods on any of the NEXT `horizon` days (today's features only).

    Recession-buffer days are unknown (NaN). Rows whose future window is unknown are dropped.
    """
    d = df.copy()
    d["_f"] = d["flooded"].astype(float).where(d["label_status"] != "recession_buffer")

    def per_district(g):
        fut = pd.concat([g["_f"].shift(-k) for k in range(1, horizon + 1)], axis=1)
        t = fut.max(axis=1)
        unknown = fut.isna().any(axis=1) & (t != 1)
        g = g.copy()
        g["target"] = t.where(~unknown)
        return g

    out = pd.concat([per_district(g) for _, g in d.groupby("location_id")], ignore_index=True)
    out = out[out["label_status"] != "recession_buffer"]
    return out.dropna(subset=["target"]).drop(columns="_f")


def new_model():
    return HistGradientBoostingClassifier(
        max_iter=250, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40,
        l2_regularization=1.0, class_weight="balanced", random_state=0)


def _f2_threshold(y, score):
    p, r, thr = precision_recall_curve(y, score)
    p, r = p[:-1], r[:-1]
    f2 = np.where((4 * p + r) > 0, 5 * p * r / (4 * p + r + 1e-12), 0)
    i = int(np.nanargmax(f2))
    return float(thr[i]), float(p[i]), float(r[i]), float(f2[i])


def _scores(y, s, base):
    return {
        "pr_auc": round(float(average_precision_score(y, s)), 4),
        "roc_auc": round(float(roc_auc_score(y, s)), 4),
        "baseline_rain3d_pr_auc": round(float(average_precision_score(y, base)), 4),
        "baseline_rain3d_roc_auc": round(float(roc_auc_score(y, base)), 4),
    }


def cross_validate(data: pd.DataFrame, feats, horizon: int, min_train_pos=30, min_test_pos=5):
    years = data["date"].dt.year
    oof, per_year, last = [], [], None
    for year in sorted(years.unique()):
        test = data[years == year]
        start = pd.Timestamp(year=int(year), month=1, day=1)
        train = data[(years != year) & ~((data["date"] >= start - pd.Timedelta(days=horizon)) & (data["date"] < start))]
        if train["target"].sum() < min_train_pos or train["target"].nunique() < 2:
            continue
        model = new_model().fit(train[feats], train["target"])
        score = model.predict_proba(test[feats])[:, 1]
        part = test[["location_id", "date", "target", "label_status"]].copy()
        part["score"] = score
        part["rain_3d"] = test["rain_3d"].fillna(0).to_numpy()
        oof.append(part)
        if test["target"].sum() >= min_test_pos and test["target"].nunique() > 1:
            per_year.append({"year": int(year), "flood_rows": int(test["target"].sum()),
                             **_scores(test["target"], score, part["rain_3d"])})
            last = (model, test)
    if len(per_year) < 2:
        raise ValueError("Too few flood examples to validate the model (need at least two years with "
                         f"{min_test_pos}+ flood-warning days). Add more events to bd_flood_events.csv.")
    return pd.concat(oof, ignore_index=True), per_year, last


def event_detection(oof: pd.DataFrame, labels: pd.DataFrame, threshold: float, horizon: int) -> pd.DataFrame:
    """For every documented event-district: did the out-of-fold model raise an alert in time?"""
    idx = oof.set_index(["location_id", "date"])["score"]
    rows = []
    for (event_id, loc), g in labels.groupby(["event_id", "location_id"]):
        s, e = g["date"].min(), g["date"].max()
        window = pd.date_range(s - pd.Timedelta(days=horizon), e)
        sc = [(d, idx.get((loc, d), np.nan)) for d in window]
        sc = [(d, v) for d, v in sc if not np.isnan(v)]
        if not sc:
            continue
        alerts = [d for d, v in sc if v >= threshold]
        first = alerts[0] if alerts else None
        rows.append({"event_id": event_id, "location_id": int(loc), "district": g["district"].iloc[0],
                     "start": s.date(), "end": e.date(),
                     "confidence": g["confidence"].iloc[0], "detected": first is not None,
                     "lead_days": (s - first).days if first is not None else None,
                     "max_score": round(max(v for _, v in sc), 4)})
    return pd.DataFrame(rows)


def run_training(horizon: int = config.HORIZON_DAYS, log=print) -> dict:
    df = load_dataset()
    data = make_target(df, horizon)
    feats = feature_columns(data)
    log(f"Dataset: {len(df):,} district-days | training rows: {len(data):,} | "
        f"flood-warning rows: {int(data['target'].sum()):,} ({data['target'].mean():.2%}) | features: {len(feats)}")

    log("Validating (leave-one-year-out) ...")
    oof, per_year, last = cross_validate(data, feats, horizon)
    oof_ok = oof[oof["label_status"] != "recession_buffer"]
    y, s = oof_ok["target"].to_numpy(), oof_ok["score"].to_numpy()
    overall = _scores(y, s, oof_ok["rain_3d"])

    thr, p_at, r_at, f2 = _f2_threshold(y, s)
    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(s, y)
    p_high = float(calibrator.predict([thr])[0])
    levels = {"moderate": round(p_high / 2, 4), "high": round(p_high, 4), "very_high": round(min(0.9, 2 * p_high), 4)}

    labels = pd.read_csv(config.LABELS_CSV, parse_dates=["date"])
    labels = labels[(labels["date"] >= df["date"].min()) & (labels["date"] <= df["date"].max())]
    ev = event_detection(oof, labels, thr, horizon)
    alerts_nf = oof_ok[(oof_ok["target"] == 0) & (oof_ok["score"] >= thr)]
    nf_rows = int((oof_ok["target"] == 0).sum())
    far = len(alerts_nf) / max(1, nf_rows) * 365          # false-alert days per district per year

    # which inputs matter? (permutation importance on the most recent held-out year)
    imp = pd.DataFrame()
    if last is not None:
        m, test = last
        sample = test.sample(min(len(test), 25000), random_state=0)
        pi = permutation_importance(m, sample[feats], sample["target"], scoring="average_precision",
                                    n_repeats=3, random_state=0, n_jobs=1)
        imp = (pd.DataFrame({"feature": feats, "importance": pi.importances_mean})
               .sort_values("importance", ascending=False).reset_index(drop=True))

    log("Training the final model on all years ...")
    final = new_model().fit(data[feats], data["target"])

    metrics = {
        "version": __version__, "trained_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "horizon_days": horizon, "data_start": str(df["date"].min().date()), "data_end": str(df["date"].max().date()),
        "districts": int(df["location_id"].nunique()), "training_rows": int(len(data)),
        "flood_warning_rows": int(data["target"].sum()), "features": len(feats),
        "events_in_period": int(ev["event_id"].nunique()) if len(ev) else 0,
        "overall_out_of_fold": overall,
        "alert_threshold_score": round(thr, 4), "precision_at_threshold": round(p_at, 4),
        "recall_at_threshold": round(r_at, 4), "f2_at_threshold": round(f2, 4),
        "false_alert_days_per_district_year": round(far, 2),
        "event_district_hit_rate": round(float(ev["detected"].mean()), 3) if len(ev) else None,
        "median_lead_days": float(ev.loc[ev["detected"], "lead_days"].median()) if len(ev) and ev["detected"].any() else None,
        "per_year": per_year, "risk_level_probabilities": levels,
    }

    config.OUT.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": final, "features": feats, "horizon_days": horizon, "threshold": thr,
                 "calibrator": calibrator, "levels": levels, "metrics": metrics}, config.MODEL_PATH)
    config.METRICS_JSON.write_text(json.dumps(metrics, indent=2))
    oof.to_csv(config.OOF_CSV, index=False)
    imp.to_csv(config.IMPORTANCE_CSV, index=False)
    ev.to_csv(config.EVENT_CHECK_CSV, index=False)
    config.REPORT_MD.write_text(_report(metrics, ev, imp), encoding="utf-8")
    log(f"Saved model and report to {config.OUT}")
    return metrics


def _report(m: dict, ev: pd.DataFrame, imp: pd.DataFrame) -> str:
    o = m["overall_out_of_fold"]
    L = [f"# Flood-risk model report", "",
         f"Generated {m['trained_at']} | model version {m['version']}", "",
         "## Setup",
         f"- Period: {m['data_start']} to {m['data_end']}, {m['districts']} districts, "
         f"{m['training_rows']:,} district-days, {m['features']} features (NASA POWER daily + IMERG).",
         f"- Target: a documented flood in the district within the next {m['horizon_days']} days "
         f"({m['flood_warning_rows']:,} such days, {m['events_in_period']} documented event windows).",
         "- Validation: leave-one-year-out (each year predicted by a model that never saw it).", "",
         "## Does it beat a simple rule?",
         f"| | PR-AUC | ROC-AUC |", "|---|---|---|",
         f"| **Model** | **{o['pr_auc']}** | **{o['roc_auc']}** |",
         f"| Rule: heavy 3-day rain | {o['baseline_rain3d_pr_auc']} | {o['baseline_rain3d_roc_auc']} |", "",
         "PR-AUC is the more informative number here because floods are rare. If the model does not clearly beat the rule, "
         "do not rely on it.", "",
         "## Alert behaviour",
         f"- Alert threshold (maximises F2, i.e. favours catching floods): precision {m['precision_at_threshold']:.2f}, "
         f"recall {m['recall_at_threshold']:.2f}.",
         f"- False-alert days: about {m['false_alert_days_per_district_year']} per district per year.",
         f"- Event hit rate: {m['event_district_hit_rate']} of documented event-district windows received an alert; "
         f"median lead time {m['median_lead_days']} days before the documented start.", "",
         "## By year", "| Year | Flood-warning days | Model PR-AUC | Rain-rule PR-AUC | Model ROC-AUC | Rain-rule ROC-AUC |", "|---|---|---|---|---|---|"]
    for y in m["per_year"]:
        L.append(f"| {y['year']} | {y['flood_rows']} | {y['pr_auc']} | {y['baseline_rain3d_pr_auc']} | {y['roc_auc']} | {y['baseline_rain3d_roc_auc']} |")
    if len(imp):
        L += ["", "## Most important inputs (permutation importance, latest held-out year)", "| Feature | Importance |", "|---|---|"]
        L += [f"| {r.feature} | {r.importance:.4f} |" for r in imp.head(12).itertuples()]
    if len(ev):
        L += ["", "## Event detection by confidence of the label", "| Confidence | Event-districts | Detected |", "|---|---|---|"]
        for c, g in ev.groupby("confidence"):
            L.append(f"| {c} | {len(g)} | {g['detected'].mean():.0%} |")
    L += ["", "## Limits you must keep in mind",
          "- Labels come from public reports of major floods; dates are approximate and unlisted floods count as 'no flood'.",
          "- Most big Bangladesh floods are river floods driven by upstream rain; the model sees upstream rainfall only at a few Indian points.",
          "- NASA POWER lags real time by a few days, so predictions describe recent conditions, not a weather forecast.",
          "- This is a research tool, not an official warning system. Follow FFWC/BMD bulletins for decisions."]
    return "\n".join(L) + "\n"
