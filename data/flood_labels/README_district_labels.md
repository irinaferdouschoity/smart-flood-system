# District flood labels (2017-2026)

## Files
- **`bd_flood_events.csv`** - 43 documented flood events: districts, start/end date, `flood_type`
  (river_flood / flash_flood / urban_waterlogging), `confidence` (medium / low), notes and **source URLs**.
  This is the only file you edit.
- `bd_district_flood_labels.csv` - generated (one row per flooded district-day) by `python -m floodml labels`.

## Coverage
- 2022-2026: 35 events (NE flash floods 2022/2023/2024/2026, southeast floods 2023/2024/2026, Teesta and Jamuna river floods
  2022-2026, Chattogram waterlogging 2026). 2017-2020: 8 older events, used only if you train with `--start` before 2022.
- Labels are considered complete up to **2026-10-08** (`LABELS_COMPLETE_UNTIL` in `floodml/config.py`).

## Read before trusting the labels
- Compiled from public reports (UN, IFRC/BDRCS, WHO, Copernicus, DFO, FFWC bulletins, news). **Check the source URLs.**
  2026 entries partly rely on a compiled timeline of FFWC bulletins and news; verify them against the original bulletins.
- Start dates are usually reliable, end dates and per-district timing are approximate; a district is labelled flooded for the
  whole window.
- Only notable floods are listed. Every district-day not listed counts as "no flood", so missing floods lower measured accuracy.
  Not yet included: cyclone storm-surge floods, small local flash floods, 2021 and 2018 events.

## Add more floods
Add a row, then run `python -m floodml labels` (it stops and names any unknown district):

    event_id,event_name,districts,start_date,end_date,confidence,notes,source_urls,flood_type
    BDF-2025-XX,Short name,Sylhet;Sunamganj,2025-06-10,2025-06-18,medium,what the source says,https://...,flash_flood

Districts are separated by `;` and may use common spellings (Comilla/Cumilla, Bogra/Bogura ...).
Then re-train: `python -m floodml dataset` and `python -m floodml train` (or `run_ml.bat` option 4).

## Better label sources
FFWC daily bulletins (river levels vs danger level), Sentinel-1 radar flood maps (Copernicus EMS, UNOSAT, Google Earth Engine),
Dartmouth Flood Observatory archive, Global Flood Database.
