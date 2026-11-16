# Model card - Bangladesh district flood-risk model

## Purpose
Estimate, for each of the 64 districts, the chance that a documented flood occurs within the next N days (default 3),
using NASA POWER daily data. Intended for research, teaching and prototyping. **Not** an operational warning system.

## Inputs (all from NASA POWER daily point API, using only data up to the prediction day)
- Rainfall: GPM IMERG (`IMERG_PRECTOT`, 0.1 degree) with `PRECTOTCORR` as fallback and as separate features;
  totals over 1, 2, 3, 5, 7, 14, 30 days, wet-day count, 7-day maximum, rain in days 8-30 (antecedent wetness).
- Soil wetness: `GWETTOP`, `GWETROOT`, `GWETPROF` and the 7-day change of root-zone wetness.
- Weather: `T2M`, `T2M_MAX`, `T2M_MIN`, `T2MDEW`, `RH2M`, `WS2M`, `PS` (+ 3-day pressure change), `ALLSKY_SFC_SW_DWN`.
- Upstream rain (outside Bangladesh): Cherrapunji, Guwahati, Siliguri, Agartala, Dibrugarh, Patna (3- and 7-day totals).
- Context: division- and country-mean rainfall, district latitude/longitude, season (sin/cos of day of year).
Parameters that NASA does not provide for a community are detected automatically and skipped (`python -m floodml doctor`).

## Relation to the Haor model
This model is trained only on the documented-flood table described below (NASA POWER / IMERG conditions on flood and non-flood days). It does not use the Haor dataset or the Haor model, which remain only in the original six-city dashboard.

## Labels
`data/flood_labels/bd_flood_events.csv`: 43 events (2017-2026; 35 in the default 2022-2026 study period) with districts,
start/end dates, flood type, confidence (`medium`/`low`) and source URLs. Each flooded district-day is a positive. Days not
covered by an event are negatives up to 2026-10-08 (`LABELS_COMPLETE_UNTIL`). The 3 days after an event ends are excluded
(`recession_buffer`) because standing water makes them ambiguous.

## Evaluation
Leave-one-year-out cross-validation; all metrics, the alert threshold (maximises F2) and the probability calibration
(isotonic regression) come from out-of-fold predictions. Baseline = "heavy 3-day rainfall" rule. Event-level metrics:
share of documented event-district windows that received an alert, median lead time, false-alert days per district-year.
The actual numbers are in `outputs/report.md` after training - **they are not claimed here because they depend on your data run.**

## Known limitations
1. **Label noise and incompleteness.** Only major, reported floods are listed; dates are approximate; smaller floods count as
   "no flood". This lowers measured precision and can bias the model.
2. **River floods.** Most severe Bangladesh floods are driven by upstream discharge (Ganges, Brahmaputra, Meghna) and tides.
   Local rainfall and six upstream points capture only part of that. River water levels (FFWC) would help most.
3. **Not a forecast.** NASA POWER lags real time by a few days; predictions describe recent conditions. A forecast needs
   numerical weather prediction rainfall as an extra input.
4. **Spatial resolution.** One point per district centre; IMERG is ~10 km, POWER meteorology ~50 km.
5. **Small sample.** Only a handful of flood years; results vary strongly by year (see per-year table in the report).
6. Risk levels (Moderate/High/Very high) are derived from the calibrated probability at the alert threshold and are
   heuristic, not official categories.

## Responsible use
Do not publish the output as a warning. Cite NASA POWER and the original event sources, and state the limitations above.
