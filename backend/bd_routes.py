"""API for the Bangladesh 64-district flood-risk model (reads files written by `python -m floodml`)."""
import csv
import json
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from floodml import config  # noqa: E402

router = APIRouter(prefix="/bd", tags=["Bangladesh districts"])

_HINT = "Run:  python -m floodml all   (first time)  or  python -m floodml predict"


@router.get("/districts")
def districts():
    """The 64 districts (works even before any data is downloaded)."""
    from floodml.district_view import list_districts
    return list_districts()


@router.get("/district/{location_id}")
def district(location_id: int):
    """Everything the dashboard needs for one district: latest prediction, NASA weather, flood events."""
    from floodml.district_view import district_payload
    try:
        return district_payload(location_id)
    except KeyError:
        raise HTTPException(404, "Unknown district")


@router.get("/predictions")
def predictions():
    """Latest risk for all 64 districts."""
    if not config.PRED_JSON.exists():
        raise HTTPException(404, f"No predictions yet. {_HINT}")
    return json.loads(config.PRED_JSON.read_text(encoding="utf-8"))


@router.get("/predictions.csv", include_in_schema=False)
def predictions_csv():
    if not config.PRED_CSV.exists():
        raise HTTPException(404, f"No predictions yet. {_HINT}")
    return FileResponse(config.PRED_CSV, media_type="text/csv", filename="bd_district_flood_risk.csv")


@router.get("/report")
def report():
    """Validation results of the trained model."""
    if not config.METRICS_JSON.exists():
        raise HTTPException(404, "Model not trained yet. Run:  python -m floodml train")
    return json.loads(config.METRICS_JSON.read_text(encoding="utf-8"))


@router.get("/events")
def events():
    """The documented flood events used as labels (with sources and confidence)."""
    if not config.EVENTS_CSV.exists():
        raise HTTPException(404, "Events file missing")
    with open(config.EVENTS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@router.post("/refresh")
async def refresh():
    """Download the newest NASA POWER data and re-score all districts (needs internet, ~1 minute)."""
    from floodml.predict import run_predict   # imported here so the app starts fast

    try:
        await run_in_threadpool(lambda: run_predict(refresh=True, log=lambda *_: None))
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc))
    except Exception as exc:                  # noqa: BLE001 - show the reason to the user
        raise HTTPException(502, f"Refresh failed: {exc}")
    return json.loads(config.PRED_JSON.read_text(encoding="utf-8"))
