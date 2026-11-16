"""Central settings: folders, dates and NASA POWER parameters."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
POWER_DIR = DATA / "power_daily"            # cached NASA POWER downloads (one CSV per point)
LABEL_DIR = DATA / "flood_labels"
OUT = ROOT / "outputs"                      # model, report, predictions

DISTRICTS_CSV = DATA / "bangladesh_districts.csv"
UPSTREAM_CSV = DATA / "upstream_stations.csv"
EVENTS_CSV = LABEL_DIR / "bd_flood_events.csv"
LABELS_CSV = LABEL_DIR / "bd_district_flood_labels.csv"
DATASET_CSV = DATA / "bd_district_training_dataset.csv"
PLAN_JSON = POWER_DIR / "_plan.json"

MODEL_PATH = OUT / "flood_model.joblib"
METRICS_JSON = OUT / "metrics.json"
REPORT_MD = OUT / "report.md"
OOF_CSV = OUT / "oof_predictions.csv"
IMPORTANCE_CSV = OUT / "feature_importance.csv"
EVENT_CHECK_CSV = OUT / "event_detection.csv"
PRED_CSV = OUT / "latest_predictions.csv"
PRED_JSON = OUT / "latest_predictions.json"

# ---- study period -----------------------------------------------------------
DEFAULT_START = "2022-01-01"
# FFWC reported no station above danger level on 8 Oct 2026, so days up to here can be
# treated as "no flood" when they are not covered by a documented event. Change this date
# when you add events beyond it.
LABELS_COMPLETE_UNTIL = "2026-10-08"
WARMUP_DAYS = 45            # extra history downloaded before the start (30-day rain windows)
HORIZON_DAYS = 3            # predict "flood within the next N days"
RECESSION_BUFFER_DAYS = 3   # days right after an event ends are ambiguous -> excluded from training

# ---- NASA POWER (daily, point) ----------------------------------------------
MAIN_PARAMS = [
    "PRECTOTCORR",   # corrected precipitation (mm/day)
    "T2M", "T2M_MAX", "T2M_MIN", "T2MDEW",
    "RH2M", "WS2M", "PS",
    "GWETTOP", "GWETROOT", "GWETPROF",   # soil wetness (surface / root zone / profile)
    "ALLSKY_SFC_SW_DWN",
]
IMERG_PARAM = "IMERG_PRECTOT"             # GPM IMERG satellite precipitation (mm/day, 0.1 degree)
COMMUNITIES = ["AG", "SB", "RE"]          # tried in this order for each parameter
