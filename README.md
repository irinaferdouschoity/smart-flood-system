---
title: Smart Flood System
sdk: docker
app_port: 7860
---
# Smart Flood Monitoring and Warning System

Two parts in one project:

1. **City dashboard** (FastAPI + MySQL): weather, rainfall indicators and flood history for six cities.
2. **Bangladesh district flood-risk model** (`floodml`): machine learning on **NASA POWER daily data** and
   **GPM IMERG** satellite rainfall for all **64 districts**, with a map page and a validation report.

> Research tool. It is **not** an official flood warning. Follow FFWC / BMD bulletins for decisions.

**New to this? Follow [`HOW_TO_RUN.md`](HOW_TO_RUN.md).**

---

## Quick start (Windows)

| I want to... | Do this |
|---|---|
| Run the **district model** (no database needed) | double-click **`run_ml.bat`** -> choose **1** (first time, 20-40 min) |
| See **all 64 districts** | `run_ml.bat` -> choose **3**: map page http://127.0.0.1:8000/bangladesh, and the main dashboard (`/`) lists every district in the Location menu (Bangladesh districts group) with its own charts, flood history and **Run prediction** |
| Refresh predictions with newest NASA data | `run_ml.bat` -> choose **2**, or press *Refresh from NASA* on the map page |
| Run the **city dashboard** | start MySQL in XAMPP, run `setup.bat` once, then `run.bat` |

## What the district model does

```
NASA POWER daily API ──► data/power_daily/   (70 points: 64 districts + 6 upstream India stations)
        │   rainfall (IMERG + corrected), soil wetness, temperature, humidity, wind,
        │   pressure, solar radiation
        ▼
features (rain totals 1-30 days, antecedent wetness, soil moisture trend, pressure drop,
          upstream rain in India, regional rain, season, location)
        ▼  + flood labels from 43 sourced events (data/flood_labels/bd_flood_events.csv)
data/bd_district_training_dataset.csv   <- one row per district per day, with flood days marked
        ▼
HistGradientBoosting classifier  ──►  "flood within the next 3 days?"  per district
        ▼
outputs/report.md  +  outputs/latest_predictions.csv  +  /bangladesh map page
```

Scientific safeguards built in: features use only past days (tested), leave-one-year-out validation,
comparison with a simple "heavy rain" rule, probability calibration, a recession buffer after events,
and event-level checks (hit rate, lead time, false alerts). See [`MODEL_CARD.md`](MODEL_CARD.md).

## Learning from NASA data on flood days (no Haor data)

The district model does **not** use the Haor dataset or the Haor model. It is built the way you proposed:
1. take the days when floods were documented (`data/flood_labels/bd_flood_events.csv`, 43 events with sources),
2. look up what NASA POWER / IMERG measured on those days and the days before (rainfall over 1-30 days, soil wetness, pressure,
   temperature, humidity, upstream rain in India),
3. put it in one table with every other day as the "no flood" comparison: `data/bd_district_training_dataset.csv`,
4. train the model on that table.

`python -m floodml analyze` (or `run_ml.bat` option 7) shows the evidence: how much rain fell before each flood, how unusual it was
for that district and season, soil wetness, when the heaviest rain fell, and how upstream rain in India preceded river floods.
Per-event numbers: `data/bd_flood_event_conditions.csv`. The old Haor model is only used by the original six-city dashboard for cities outside Bangladesh.

## Commands

All commands: `python -m floodml <command>` (virtual environment active).

| Command | What it does |
|---|---|
| `doctor` | checks packages, internet, NASA POWER parameters and data |
| `download` | downloads NASA POWER daily data (resumable, 4 parallel requests) |
| `labels` | builds flood-day labels from `bd_flood_events.csv` |
| `dataset` | builds `data/bd_district_training_dataset.csv` |
| `analyze` | **what NASA saw when floods began**: rainfall and conditions at every documented flood vs ordinary days (`outputs/flood_drivers.md`) |
| `train` | trains + validates, writes `outputs/report.md` and the model |
| `predict` | downloads the newest days and scores all 64 districts |
| `all` | download -> labels -> dataset -> analyze -> train -> predict |
| `export-mysql` | writes the daily data, flood labels and predictions into MySQL (tables `bd_*`) |

Useful options: `--start 2022-01-01`, `--horizon 3` (days ahead), `--workers 4`, `--force`, `--no-refresh`, `--mysql` (also export to MySQL after `predict` / `all`).

## Daily data in MySQL (optional)

The model itself works from CSV files, but every result can also be stored in MySQL (XAMPP): `run_ml.bat` options 1 and 2 do it
automatically when MySQL is running, and option 6 / `python -m floodml export-mysql` exports everything on demand.
Safe to repeat: rows are updated, never duplicated. Nothing in your existing tables is changed.

| Table | Content |
|---|---|
| `bd_locations` | 64 districts + 6 upstream stations (id, name, division, coordinates) |
| `bd_daily_data` | one row per location per day: IMERG and corrected rainfall, `rain_mm` (combined), temperature, humidity, wind, pressure, soil wetness, solar |
| `bd_flood_events`, `bd_flood_days` | the documented flood events (with sources) and one row per flooded district-day |
| `bd_predictions` | model output per district per date (history is kept) |
| `bd_latest_risk` | VIEW: newest risk of every district |

Ready-to-use queries: `sql/bd_example_queries.sql`.

## Dashboard tips

- **Light / dark mode:** button in the left panel on both pages (remembered; default follows the computer's setting).
- **Day-to-day data:** under the charts, the city dashboard lists the latest day, the average for the current month and the newest 30 days.
- **Rainfall indicator:** uses the newest rain stored in MySQL (same date as the charts) compared with each city's historical thresholds.

## Project layout

| Path | Purpose |
|---|---|
| `floodml/` | the model package (NASA client, features, labels, training, prediction, CLI) |
| `data/bangladesh_districts.csv` | 64 districts with division and centre coordinates |
| `data/upstream_stations.csv` | 6 Indian upstream rainfall points (Ganges, Brahmaputra, Teesta, Meghalaya, Tripura) |
| `data/flood_labels/bd_flood_events.csv` | **the labels**: sourced flood events - edit this to improve the model |
| `outputs/` | model, report, predictions (created by the commands) |
| `backend/`, `frontend/` | web app and pages (`/` city dashboard, `/bangladesh` district map) |
| `tests/` | tests using a simulated NASA server (`python -m unittest -v`) and a fake-browser check of the dashboard (`node tests/ui_smoke.js`) |
| `sql/bd_example_queries.sql` | example SQL for the new `bd_*` tables |
| `haor_model/`, `sql/`, `scripts/` | original city dashboard, Haor model and database scripts |

## API (when the web app is running)

`GET /bd/predictions` | `GET /bd/report` | `GET /bd/events` | `POST /bd/refresh` | docs at `/docs`

## Data sources

- **NASA POWER** daily point API (power.larc.nasa.gov): meteorology, soil wetness and GPM IMERG precipitation
  (IMERG_PRECTOT). Free, no login. Please keep to a few parallel requests (the code uses 4).
- **Flood events**: public reports (UN, IFRC/BDRCS, WHO, Copernicus, Dartmouth Flood Observatory, FFWC bulletins, news);
  every row in `bd_flood_events.csv` lists its source URLs. Dates are approximate - verify before publishing results.

## Testing

`python -m unittest -v` runs the unit tests and the complete pipeline (download, dataset, training, validation, prediction) against a simulated
NASA server in about 2-3 minutes. Results from the simulation are synthetic and meaningless; the test checks the machinery.

## Troubleshooting

| Problem | Fix |
|---|---|
| `NASA POWER problem ...` | internet issue - run the same command again; downloads resume |
| `PowerClientError / 422` on `doctor` | NASA changed a parameter - send the message; the code skips unavailable parameters automatically |
| `/bangladesh` shows "No predictions yet" | run `run_ml.bat` option 1 (or `python -m floodml all`) |
| Too few flood examples | add events to `bd_flood_events.csv` (see `data/flood_labels/README_district_labels.md`) |
| MySQL errors | the city dashboard and the optional export need MySQL - see `HOW_TO_RUN.md` Part B; the model itself does not |
