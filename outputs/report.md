# Flood-risk model report

Generated 2026-11-16T17:28:21Z | model version 1.0.0

## Setup
- Period: 2022-01-01 to 2026-10-08, 64 districts, 110,952 district-days, 46 features (NASA POWER daily + IMERG).
- Target: a documented flood in the district within the next 3 days (977 such days, 35 documented event windows).
- Validation: leave-one-year-out (each year predicted by a model that never saw it).

## Does it beat a simple rule?
| | PR-AUC | ROC-AUC |
|---|---|---|
| **Model** | **0.1506** | **0.9384** |
| Rule: heavy 3-day rain | 0.1239 | 0.8985 |

PR-AUC is the more informative number here because floods are rare. If the model does not clearly beat the rule, do not rely on it.

## Alert behaviour
- Alert threshold (maximises F2, i.e. favours catching floods): precision 0.13, recall 0.52.
- False-alert days: about 11.4 per district per year.
- Event hit rate: 0.722 of documented event-district windows received an alert; median lead time 2.0 days before the documented start.

## By year
| Year | Flood-warning days | Model PR-AUC | Rain-rule PR-AUC | Model ROC-AUC | Rain-rule ROC-AUC |
|---|---|---|---|---|---|
| 2022 | 170 | 0.4528 | 0.1845 | 0.9765 | 0.9174 |
| 2023 | 78 | 0.1145 | 0.1404 | 0.9566 | 0.9577 |
| 2024 | 384 | 0.2375 | 0.1346 | 0.9545 | 0.8841 |
| 2025 | 63 | 0.007 | 0.0145 | 0.7944 | 0.8627 |
| 2026 | 282 | 0.2276 | 0.2396 | 0.9336 | 0.888 |

## Most important inputs (permutation importance, latest held-out year)
| Feature | Importance |
|---|---|
| rain_14d | 0.0722 |
| longitude | 0.0611 |
| soil_prof | 0.0610 |
| up_agartala_7d | 0.0390 |
| rain_max_7d | 0.0381 |
| rain_30d | 0.0296 |
| div_rain_7d | 0.0293 |
| soil_root | 0.0263 |
| soil_top | 0.0246 |
| div_rain_3d | 0.0113 |
| latitude | 0.0088 |
| rain_2d | 0.0049 |

## Event detection by confidence of the label
| Confidence | Event-districts | Detected |
|---|---|---|
| low | 44 | 66% |
| medium | 46 | 78% |

## Limits you must keep in mind
- Labels come from public reports of major floods; dates are approximate and unlisted floods count as 'no flood'.
- Most big Bangladesh floods are river floods driven by upstream rain; the model sees upstream rainfall only at a few Indian points.
- NASA POWER lags real time by a few days, so predictions describe recent conditions, not a weather forecast.
- This is a research tool, not an official warning system. Follow FFWC/BMD bulletins for decisions.
