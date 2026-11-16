"""What did NASA see on the days floods began? An evidence table + report from documented flood events.

For every documented flood (event x district) this takes the NASA POWER / IMERG conditions on the day the
flood began and the days before it, and compares them with ordinary days of the same district and season.
It shows what is statistically ASSOCIATED with flooding. It does not prove causes: floods in Bangladesh are
often river floods caused by rain that fell days earlier and far upstream, so local rain on the start day
can be unremarkable - the lag columns and upstream stations are there to show exactly that.
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from . import config
from .train import load_dataset

LAGS = range(0, 11)           # days before the flood began (0 = first flood day)
CONDITION_VARS = ["rain_1d", "rain_3d", "rain_7d", "rain_14d", "rain_30d", "rain_max_7d", "wet_days_7d",
                  "rain_prior_8_30d", "soil_top", "soil_root", "soil_prof", "soil_root_chg7",
                  "humidity", "temp", "pressure", "pressure_chg3", "div_rain_7d", "nat_rain_7d"]
PERCENTILE_VARS = ["rain_1d", "rain_3d", "rain_7d", "rain_14d", "rain_30d", "soil_root"]


def output_paths():
    """Resolved at call time so tests can redirect the folders."""
    return (config.DATA / "bd_flood_event_conditions.csv",
            config.OUT / "flood_vs_background.csv",
            config.OUT / "flood_drivers.md")


def _lookup(idx: pd.DataFrame, col: str, loc, dates) -> np.ndarray:
    key = pd.MultiIndex.from_arrays([np.asarray(loc), pd.DatetimeIndex(dates)])
    return idx[col].reindex(key).to_numpy(dtype=float)


def event_conditions(df: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """One row per documented event-district: conditions on the first flood day and the days before."""
    lab = labels[(labels["date"] >= df["date"].min()) & (labels["date"] <= df["date"].max())]
    on = (lab.groupby(["event_id", "location_id"])
             .agg(onset=("date", "min"), last_day=("date", "max"), district=("district", "first"),
                  confidence=("confidence", "first"), flood_type=("flood_type", "first")).reset_index())
    if on.empty:
        raise ValueError("No documented flood events fall inside the dataset period.")
    on["duration_days"] = (on["last_day"] - on["onset"]).dt.days + 1
    names = pd.read_csv(config.EVENTS_CSV).set_index("event_id")["event_name"]
    on.insert(1, "event_name", on["event_id"].map(names))
    on = on.merge(df[["location_id", "division"]].drop_duplicates(), on="location_id", how="left")

    idx = df.set_index(["location_id", "date"]).sort_index()
    loc = on["location_id"].to_numpy()
    for col in [c for c in CONDITION_VARS if c in idx.columns]:
        on[col] = _lookup(idx, col, loc, on["onset"])

    # daily rain on the days leading up to the flood
    for k in LAGS:
        on[f"rain_d-{k}"] = _lookup(idx, "rain_1d", loc, on["onset"] - pd.Timedelta(days=k))

    # when did the heaviest 7-day rain fall at the district and at each upstream (India) station?
    def peak(col, name):
        m = np.column_stack([_lookup(idx, col, loc, on["onset"] - pd.Timedelta(days=k)) for k in LAGS])
        has = ~np.isnan(m).all(axis=1)
        mm = np.where(np.isnan(m), -np.inf, m)
        on[f"{name}_peak_mm"] = np.where(has, mm.max(axis=1), np.nan)
        on[f"{name}_peak_lag_days"] = np.where(has, mm.argmax(axis=1), np.nan)

    peak("rain_7d", "local_7d")
    for col in [c for c in idx.columns if c.startswith("up_") and c.endswith("_7d")]:
        peak(col, col[:-3])

    # how unusual is each value compared with ordinary days of the same district and calendar month?
    bg = df[df["label_status"] == "no_flood"]
    groups = {k: g for k, g in bg.groupby(["location_id", bg["date"].dt.month])}
    for var in [v for v in PERCENTILE_VARS if v in idx.columns]:
        out = []
        for r in on.itertuples():
            g = groups.get((r.location_id, r.onset.month))
            val = getattr(r, var.replace("-", "_"))
            if g is None or len(g) < 20 or pd.isna(val):
                out.append(np.nan)
                continue
            ref = np.sort(g[var].dropna().to_numpy())
            out.append(np.searchsorted(ref, val, side="right") / len(ref) if len(ref) else np.nan)
        on[f"pct_{var}"] = out
    return on.drop(columns="last_day")


def compare_to_background(df: pd.DataFrame, cond: pd.DataFrame, max_bg: int = 100000) -> pd.DataFrame:
    """Flood-onset days vs ordinary days of the same districts and months: median, share above the
    ordinary-day 90th percentile, and AUC (0.5 = no difference, 1.0 = floods always have higher values)."""
    bg = df[(df["label_status"] == "no_flood") & df["location_id"].isin(cond["location_id"])
            & df["date"].dt.month.isin(cond["onset"].dt.month)]
    if len(bg) > max_bg:
        bg = bg.sample(max_bg, random_state=0)
    rows = []
    for v in [c for c in CONDITION_VARS if c in cond.columns and c in bg.columns]:
        a, b = cond[v].dropna(), bg[v].dropna()
        if len(a) < 5 or len(b) < 20 or b.nunique() < 2:
            continue
        auc = roc_auc_score(np.r_[np.ones(len(a)), np.zeros(len(b))], np.r_[a.to_numpy(), b.to_numpy()])
        rows.append({"variable": v, "flood_onset_median": round(float(a.median()), 3),
                     "ordinary_day_median": round(float(b.median()), 3),
                     "share_above_ordinary_p90": round(float((a > b.quantile(0.9)).mean()), 3),
                     "auc": round(float(auc), 3), "n_floods": int(len(a))})
    return pd.DataFrame(rows).sort_values("auc", ascending=False).reset_index(drop=True)


def _group_table(cond: pd.DataFrame, by: str) -> str:
    L = [f"| {by.replace('_', ' ').title()} | Event-districts | Median rain 3d (mm) | Median rain 7d (mm) | Median rain 30d (mm) | "
         "Typical percentile of 7-day rain* | Soil wetness (root) | Local rain peak (days before) |",
         "|---|---|---|---|---|---|---|---|"]
    for k, g in cond.groupby(by):
        pct = g["pct_rain_7d"].median()
        L.append(f"| {k} | {len(g)} | {g['rain_3d'].median():.0f} | {g['rain_7d'].median():.0f} | {g['rain_30d'].median():.0f} | "
                 f"{'' if pd.isna(pct) else f'{pct:.0%}'} | {g['soil_root'].median():.2f} | {g['local_7d_peak_lag_days'].median():.0f} |")
    return "\n".join(L)


def _report(cond: pd.DataFrame, comp: pd.DataFrame, n_days: int) -> str:
    n = len(cond)
    extreme = float((cond["pct_rain_7d"] >= 0.9).mean())
    L = ["# What did NASA see when floods began?", "",
         f"Based on {cond['event_id'].nunique()} documented flood events = {n} event-districts, "
         f"{cond['onset'].min().date()} to {cond['onset'].max().date()}. Conditions are NASA POWER / GPM IMERG values on the first "
         "flood day and the 10 days before it, compared with ordinary (no-flood) days of the same district and calendar month.", "",
         "> This shows what is *associated* with floods, not proven causes. Event dates are approximate and many floods are river floods "
         "fed by rain that fell days earlier and far upstream.", "",
         "## Key findings",
         f"- **Rain:** in half of the floods the district received at least {cond['rain_3d'].median():.0f} mm in the 3 days and "
         f"{cond['rain_7d'].median():.0f} mm in the 7 days before the flood began (30 days: {cond['rain_30d'].median():.0f} mm).",
         f"- **Unusual rain:** in {extreme:.0%} of the event-districts the 7-day rain was in the top 10% of ordinary days of that district and month. "
         + ("Almost every documented flood came with exceptional local rain." if extreme >= 0.95 else
            f"The other {1 - extreme:.0%} flooded without exceptional local rain - typically river floods from upstream water."),
         f"- **Soil:** median root-zone soil wetness at onset was {cond['soil_root'].median():.2f} "
         f"(ordinary days: {comp.loc[comp.variable == 'soil_root', 'ordinary_day_median'].iloc[0] if (comp.variable == 'soil_root').any() else 'n/a'}).",
         f"- **Timing:** the heaviest 7-day rain at the district fell a median {cond['local_7d_peak_lag_days'].median():.0f} days before the flood began.", ""]
    up = [c for c in cond.columns if c.startswith("up_") and c.endswith("_peak_lag_days")]
    if up:
        L += ["## Upstream (India) rain before river floods", "| Station | Median 7-day peak (mm) | Median days before flood onset |", "|---|---|---|"]
        for c in up:
            key = c[3:-len("_peak_lag_days")]
            sub = cond[cond["flood_type"] == "river_flood"] if (cond["flood_type"] == "river_flood").any() else cond
            L.append(f"| {key.title()} | {sub[f'up_{key}_peak_mm'].median():.0f} | {sub[c].median():.0f} |")
        L.append("")
    L += ["## By flood type", _group_table(cond, "flood_type"), "",
          "## By division", _group_table(cond, "division"), "",
          "\\* percentile among ordinary days of the same district and month (50% = a typical day, 90% = very wet).", "",
          "## Which conditions separate flood days from ordinary days? (AUC: 0.5 = no difference, 1.0 = perfect)",
          "| Variable | Flood onset (median) | Ordinary day (median) | Floods above ordinary 90th pct | AUC |", "|---|---|---|---|---|"]
    L += [f"| {r.variable} | {r.flood_onset_median} | {r.ordinary_day_median} | {r.share_above_ordinary_p90:.0%} | {r.auc} |"
          for r in comp.itertuples()]
    prof = cond[[f"rain_d-{k}" for k in LAGS]].mean()
    L += ["", "## Average daily rain before the flood began (mm/day)", "| Days before onset | " + " | ".join(str(k) for k in LAGS) + " |",
          "|---|" + "---|" * len(LAGS), "| Mean rain | " + " | ".join(f"{prof[f'rain_d-{k}']:.1f}" for k in LAGS) + " |", "",
          "## How this is used",
          "The same NASA data is turned into the training table `data/bd_district_training_dataset.csv` (every district, every day, "
          "flood days marked) on which the model is trained - see `outputs/report.md`. The per-event evidence is in "
          "`data/bd_flood_event_conditions.csv`."]
    return "\n".join(L) + "\n"


def run_analysis(log=print) -> dict:
    df = load_dataset()
    labels = pd.read_csv(config.LABELS_CSV, parse_dates=["date"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        cond = event_conditions(df, labels)
    comp = compare_to_background(df, cond)
    out_cond, out_comp, out_report = output_paths()
    config.OUT.mkdir(parents=True, exist_ok=True)
    cond.to_csv(out_cond, index=False)
    comp.to_csv(out_comp, index=False)
    out_report.write_text(_report(cond, comp, len(df)), encoding="utf-8")
    log(f"{len(cond)} event-districts analysed.")
    log(f"Evidence table: {out_cond}")
    log(f"Report:         {out_report}")
    return {"events": len(cond), "median_rain_3d": float(cond["rain_3d"].median()),
            "median_rain_7d": float(cond["rain_7d"].median())}
