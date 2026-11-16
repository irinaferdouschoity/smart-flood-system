# What did NASA see when floods began?

Based on 35 documented flood events = 90 event-districts, 2022-05-17 to 2026-09-02. Conditions are NASA POWER / GPM IMERG values on the first flood day and the 10 days before it, compared with ordinary (no-flood) days of the same district and calendar month.

> This shows what is *associated* with floods, not proven causes. Event dates are approximate and many floods are river floods fed by rain that fell days earlier and far upstream.

## Key findings
- **Rain:** in half of the floods the district received at least 145 mm in the 3 days and 225 mm in the 7 days before the flood began (30 days: 704 mm).
- **Unusual rain:** in 46% of the event-districts the 7-day rain was in the top 10% of ordinary days of that district and month. The other 54% flooded without exceptional local rain - typically river floods from upstream water.
- **Soil:** median root-zone soil wetness at onset was 0.98 (ordinary days: 0.9).
- **Timing:** the heaviest 7-day rain at the district fell a median 0 days before the flood began.

## Upstream (India) rain before river floods
| Station | Median 7-day peak (mm) | Median days before flood onset |
|---|---|---|
| Cherrapunji | 234 | 0 |
| Guwahati | 106 | 0 |
| Siliguri | 168 | 0 |
| Agartala | 136 | 1 |
| Dibrugarh | 157 | 0 |
| Patna | 79 | 0 |

## By flood type
| Flood Type | Event-districts | Median rain 3d (mm) | Median rain 7d (mm) | Median rain 30d (mm) | Typical percentile of 7-day rain* | Soil wetness (root) | Local rain peak (days before) |
|---|---|---|---|---|---|---|---|
| flash_flood | 61 | 172 | 273 | 792 | 86% | 0.99 | 0 |
| river_flood | 28 | 105 | 175 | 571 | 92% | 0.97 | 0 |
| urban_waterlogging | 1 | 127 | 225 | 861 | 76% | 1.00 | 10 |

## By division
| Division | Event-districts | Median rain 3d (mm) | Median rain 7d (mm) | Median rain 30d (mm) | Typical percentile of 7-day rain* | Soil wetness (root) | Local rain peak (days before) |
|---|---|---|---|---|---|---|---|
| Chattogram | 28 | 165 | 252 | 672 | 88% | 0.98 | 0 |
| Dhaka | 4 | 93 | 200 | 683 | 81% | 0.97 | 4 |
| Mymensingh | 7 | 126 | 209 | 794 | 84% | 0.98 | 1 |
| Rajshahi | 3 | 146 | 188 | 561 | 96% | 0.97 | 0 |
| Rangpur | 22 | 95 | 163 | 552 | 90% | 0.96 | 0 |
| Sylhet | 26 | 201 | 280 | 1017 | 89% | 1.00 | 0 |

\* percentile among ordinary days of the same district and month (50% = a typical day, 90% = very wet).

## Which conditions separate flood days from ordinary days? (AUC: 0.5 = no difference, 1.0 = perfect)
| Variable | Flood onset (median) | Ordinary day (median) | Floods above ordinary 90th pct | AUC |
|---|---|---|---|---|
| rain_3d | 144.51 | 27.58 | 80% | 0.93 |
| rain_1d | 49.615 | 7.44 | 77% | 0.922 |
| rain_7d | 225.275 | 73.19 | 66% | 0.901 |
| humidity | 92.13 | 86.25 | 64% | 0.9 |
| soil_top | 0.96 | 0.88 | 57% | 0.897 |
| div_rain_7d | 207.526 | 76.574 | 62% | 0.892 |
| rain_max_7d | 76.095 | 25.08 | 61% | 0.877 |
| soil_root | 0.98 | 0.9 | 57% | 0.86 |
| rain_14d | 377.83 | 163.04 | 58% | 0.847 |
| rain_30d | 703.915 | 368.03 | 52% | 0.844 |
| soil_prof | 0.95 | 0.86 | 39% | 0.823 |
| nat_rain_7d | 123.508 | 76.245 | 31% | 0.808 |
| rain_prior_8_30d | 468.245 | 276.315 | 38% | 0.757 |
| soil_root_chg7 | 0.04 | 0.0 | 10% | 0.735 |
| wet_days_7d | 7.0 | 7.0 | 0% | 0.706 |
| pressure_chg3 | 0.07 | 0.0 | 6% | 0.582 |
| pressure | 99.94 | 100.11 | 0% | 0.361 |
| temp | 27.725 | 28.29 | 0% | 0.35 |

## Average daily rain before the flood began (mm/day)
| Days before onset | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Mean rain | 61.1 | 56.2 | 40.5 | 31.3 | 27.2 | 18.3 | 16.1 | 18.5 | 16.3 | 21.0 | 18.6 |

## How this is used
The same NASA data is turned into the training table `data/bd_district_training_dataset.csv` (every district, every day, flood days marked) on which the model is trained - see `outputs/report.md`. The per-event evidence is in `data/bd_flood_event_conditions.csv`.
