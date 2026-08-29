# Multi-Day Benchmark Evaluation: CoolAccess (July 15 vs July 16, 2024)

> **Document Version:** 1.1.0  
> **Evaluation Date:** 2026-08-28  
> **Status:** Verified (Offline Deterministic Replay Across Two Historical Thermal Days)  
> **Scope:** Cross-day municipal cooling resource allocation comparison using official FortyGuard 100m API data and 2020 U.S. Census population layers.

---

## 1. Executive Summary & Purpose

This report documents a **second-day offline benchmark evaluation** of the CoolAccess deterministic maximum-coverage optimization engine using real FortyGuard historical API snapshots acquired for **July 16, 2024**, and compares the results against the frozen canonical **July 15, 2024** production baseline for Washington, DC.

### Benchmark Evaluation Framework
$$\text{Same City} + \text{Same 6 Public Facilities} + \text{Same 887 Census Blocks} + \text{Different Thermal Day} \implies \text{Auditable Deterministic Allocation}$$

---

## 2. Dataset Provenance & FortyGuard Acquisition Telemetry

All snapshots were acquired directly from the official FortyGuard tOS Enterprise API using the official `FortyGuardClient` SDK for the locked Washington, DC Downtown / Capitol Hill / SW Waterfront corridor (`14.61 km²`).

### Query Specifications
- **Granularity:** 100 meters
- **Filter Type:** `filter_type = 1` (Single-hour discrete snapshot)
- **Analytic Type:** `"tcm"` (Thermal Comfort Model)
- **Observed Field:** `average_temperature` in Celsius (°C)
- **Grid Stability:** Exactly **1,452 discrete polygon cells** returned per snapshot (100% geometric stability matching the canonical July 15 grid).

### Acquisition Telemetry & Credit Consumption (July 16, 2024)

| Timestamp (UTC) | Local Time Equiv. (EDT) | Provider Activity ID | Returned Tiles | Min Temp (°C) | Mean Temp (°C) | Max Temp (°C) | Raw 100m Spread (ΔT) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`14:00Z`** | ~10:00 EDT | `38fca794-6437-47f1-b438-ef979a0c2e44` | 1,452 | 38.345 | 38.500 | 38.717 | 0.372 °C |
| **`16:00Z`** | ~12:00 EDT | `c47857f1-d2eb-4837-ae6e-c57a9cddf489` | 1,452 | 38.129 | 38.396 | 38.598 | 0.469 °C |
| **`18:00Z`** | ~14:00 EDT | `6af12906-3821-4fa0-97ae-a84d1cbc94ae` | 1,452 | 37.224 | 37.441 | 37.524 | 0.300 °C |
| **`20:00Z`** | ~16:00 EDT | `ce463bc7-9fd1-4aba-ba9d-a505e1400b41` | 1,452 | 35.700 | 36.418 | 36.601 | 0.901 °C |
| **`22:00Z`** | ~18:00 EDT | `c26f2728-763b-4133-8233-ba8f0166b543` | 1,452 | 31.133 | 31.395 | 31.733 | 0.601 °C |

* **Credits Consumed for July 16 CoolAccess:** 21,100 credits (5 single-hour snapshots × 4,220 credits/query).
* **Provenance & Reproducibility Note:** Canonical July 15 is reproducible from committed prepared benchmark artifacts in the repository. July 16 provides an auditable acquisition manifest (`acquisition_manifest.json`) and deterministic replay workflow; raw FortyGuard provider payloads are retained local-only to maintain repository hygiene.
* **Cross-Day Normalization:** Cross-day evaluation retains the canonical July 15 robust P1/P99 normalization anchors (`p1_lower_anchor_c = 32.022°C`, `p99_upper_anchor_c = 37.699°C`) for calibration consistency across evaluation days. Normalized thermal-priority values outside `[32.022°C, 37.699°C]` are clamped to `[0.0, 1.0]`.

---

## 3. Spatial Ranking Dynamics & Spearman Correlation

Pairwise Spearman rank correlation between midday and late-afternoon states:
- **July 15, 2024 (Canonical):** $r_s = -0.9696$ (Measured spatial rank inversion across $N = 1,452$ cells; 0 / 363 top-quartile overlap).
- **July 16, 2024 (Second-Day Evaluation):** $r_s = +0.7214$ ($N = 1,452$ cells; measured spatial rank stability throughout the diurnal cycle).

The optimizer objective — not Spearman correlation — is authoritative for facility selection:
1. Coinciding with measured spatial rank inversion on July 15 ($r_s = -0.9696$), the optimizer selected `{DC_089, DC_135, DC_166}` at 20:00 UTC.
2. Coinciding with measured spatial rank stability on July 16 ($r_s = +0.7214$), the optimizer retained `{DC_089, DC_148, DC_166}` at 20:00 UTC because it remained mathematically optimal under the objective function.

---

## 4. Deterministic Combinatorial Allocation Results (K = 3, Radius = 750m)

Exhaustive combinatorial evaluation of all 42 subsets up to facility-count budget $K = 3$:

| Timestamp (UTC) | Local Time Equiv. (EDT) | Optimal Facility Subset ($K=3$) | Covered Heat-Weighted Demand | Demand Coverage (%) | Covered Census Population | Population Coverage (%) | Decisive Tie-Break Criterion |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`14:00`** | ~10:00 EDT | `DC_089, DC_148, DC_166` | 41,876.00 | 41.71% | 41,876 | 41.71% | Heat-Weighted Demand |
| **`16:00`** | ~12:00 EDT | `DC_089, DC_148, DC_166` | 41,876.00 | 41.71% | 41,876 | 41.71% | Heat-Weighted Demand |
| **`18:00`** | ~14:00 EDT | `DC_089, DC_148, DC_166` | 39,790.14 | 41.60% | 41,876 | 41.71% | Heat-Weighted Demand |
| **`20:00`** | ~16:00 EDT | `DC_089, DC_148, DC_166` | 32,627.90 | 42.12% | 41,876 | 41.71% | Heat-Weighted Demand |
| **`22:00`** | ~18:00 EDT | `DC_089, DC_148, DC_166` | 0.00 | 0.00% | 41,876 | 41.71% | Raw Population |

*Facility Key:* `DC_089` = Shaw Library (Watha T. Daniel); `DC_148` = Northeast Library; `DC_166` = Randall Recreation Center.

---

## 5. Baseline Comparisons at 20:00 UTC (Radius = 750m)

### Static Baseline (Reusing 16:00 Midday Plan)
- **Dynamic Optimal Objective (July 16, 20:00):** `32,627.90` (41,876 residents)
- **Static Baseline Objective (July 16, 20:00):** `32,627.90` (41,876 residents)
- **Static Gain:** `+0.00 (+0.00%)`
- **Significance:** Because the spatial rank structure remained positively correlated on July 16 ($r_s = +0.7214$), maintaining the midday plan at 20:00 remained mathematically optimal.

### Naive Thermal Baseline (Top Mean Heat Catchments)
- **Naive Selected Facilities:** `DC_135, DC_166, DC_168` (MLK Library, Randall Rec, Southwest Library)
- **Naive Objective:** `24,224.64`
- **Dynamic Optimizer Gain over Naive:** **`+8,403.26 (+34.69%)`**
- **Significance:** At July 16 20:00 UTC, the deterministic $K=3$ optimum exceeded the naive thermal baseline by 8,403.26 heat-weighted demand units, or 34.69%.

---

## 6. One-for-One Replacement Loss Evidence (20:00 UTC @ 750m)

Every single one-for-one substitution of an optimal facility with an unselected alternative (`DC_135`, `DC_159`, `DC_168`) strictly reduces covered heat-weighted demand:

| Selected Facility to Replace | Alternative Facility | Covered Demand Delta | Raw Population Delta | Comparator Outcome |
|---|---|:---:|:---:|:---:|
| `DC_089` (Shaw Library) | `DC_135` (MLK Library) | **-687.44** | -1,673 | `ORIGINAL_PREFERRED` |
| `DC_089` (Shaw Library) | `DC_159` (Southeast Library) | **-4,406.69** | -6,304 | `ORIGINAL_PREFERRED` |
| `DC_089` (Shaw Library) | `DC_168` (Southwest Library) | **-5,659.82** | -7,902 | `ORIGINAL_PREFERRED` |
| `DC_148` (Northeast Library) | `DC_135` (MLK Library) | **-2,743.44** | -3,519 | `ORIGINAL_PREFERRED` |
| `DC_148` (Northeast Library) | `DC_159` (Southeast Library) | **-4,683.17** | -5,897 | `ORIGINAL_PREFERRED` |
| `DC_148` (Northeast Library) | `DC_168` (Southwest Library) | **-7,715.82** | -9,748 | `ORIGINAL_PREFERRED` |
| `DC_166` (Randall Recreation) | `DC_135` (MLK Library) | **-3,601.72** | -4,575 | `ORIGINAL_PREFERRED` |
| `DC_166` (Randall Recreation) | `DC_159` (Southeast Library) | **-6,427.06** | -8,080 | `ORIGINAL_PREFERRED` |
| `DC_166` (Randall Recreation) | `DC_168` (Southwest Library) | **-1,626.50** | -2,065 | `ORIGINAL_PREFERRED` |

---

## 7. Secondary Sensitivity Analysis (500m & 1000m Radii)

| Timestamp (UTC) | 500m Optimal Facilities | 500m Objective | 500m Pop | 1000m Optimal Facilities | 1000m Objective | 1000m Pop |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`14:00`** | `DC_148, DC_166, DC_168` | 24,567.00 | 24,567 | `DC_135, DC_148, DC_166` | 61,028.00 | 61,028 |
| **`16:00`** | `DC_148, DC_166, DC_168` | 24,567.00 | 24,567 | `DC_135, DC_148, DC_166` | 61,028.00 | 61,028 |
| **`18:00`** | `DC_089, DC_166, DC_168` | 23,520.13 | 24,495 | `DC_135, DC_148, DC_166` | 58,147.93 | 61,028 |
| **`20:00`** | `DC_148, DC_166, DC_168` | 19,518.07 | 24,567 | `DC_135, DC_148, DC_166` | 48,298.18 | 61,028 |
| **`22:00`** | `DC_148, DC_166, DC_168` | 0.00 | 24,567 | `DC_135, DC_148, DC_166` | 0.00 | 61,028 |

---

## 8. Cross-Day Comparison: July 15 vs July 16, 2024

| Dimension | Canonical Production Demo (July 15, 2024) | Second-Day Offline Evaluation (July 16, 2024) | Cross-Day Evidence Note |
|---|---|---|---|
| **Diurnal Temperature Range** | 31.36 °C to 37.78 °C | 31.13 °C to 38.72 °C | July 16 is ~1.0 °C warmer during peak morning/midday hours. |
| **Spatial Rank Correlation (16Z vs 20Z)** | $r_s = -0.9696$ (Rank Inversion, $N=1,452$) | $r_s = +0.7214$ (Rank Stability, $N=1,452$) | Relative spatial heat distributions exhibit different diurnal dynamics across days. |
| **Midday (16:00 UTC) Selection** | `{DC_089, DC_148, DC_166}` | `{DC_089, DC_148, DC_166}` | **Identical baseline selection** across both days. |
| **Late Afternoon (20:00 UTC) Selection** | `{DC_089, DC_135, DC_166}` | `{DC_089, DC_148, DC_166}` | Selected `{DC_089, DC_135, DC_166}` on July 15 coinciding with measured spatial rank inversion; retained `{DC_089, DC_148, DC_166}` on July 16 coinciding with measured spatial rank stability. |
| **Static Baseline Comparison (20:00 UTC)** | Dynamic: 8,328.93 (38,357 pop) vs Static: 6,734.48 (41,876 pop) → **+1,594.45 (+23.68%)** | Dynamic: 32,627.90 (41,876 pop) vs Static: 32,627.90 (41,876 pop) → **+0.00 (+0.00%)** | Dynamic optimizer captured +23.68% gain when spatial ranks inverted on July 15; held optimal plan when stable on July 16. |
| **Naive Thermal Baseline (20:00 UTC)** | Naive: 8,328.93 (Tie / +0.0% gain) | Naive: 24,224.64 → **+8,403.26 (+34.69% gain)** | At July 16 20:00 UTC, the deterministic K=3 optimum exceeded the naive thermal baseline by 8,403.26 heat-weighted demand units, or 34.69%. |
| **Decision Classification** | *Canonical Baseline* | **`PARTIAL CROSS-DAY DECISION CHANGE`** | Midday decision is stable across both days; late-afternoon decision differs based on observed diurnal heat pattern. |

---

## 9. Scope & Limitations

1. **Two Historical Days Evaluated:** Evaluates July 15 and July 16, 2024. No statistical generalization claim across all seasons, weather regimes, or cities.
2. **Prepared Data Replay:** Replays historical FortyGuard data; does not ingest live feeds or weather forecast models.
3. **Census Population Representation:** Population figures reflect residential decennial Census headcounts (usual residents from 2020 Table P1), not real-time pedestrian or commercial foot-traffic.
4. **No Medical / Health Outcome Claims:** Optimizes covered heat-weighted demand units; does not claim health risk reduction, medical protection, or physiological safety outcomes.
5. **Operational Eligibility Scope:** Benchmark scope treats all six locked candidate public facilities as operationally eligible. Operating hours, current activation status, and facility service capacity are not modeled.
6. **Geodesic Centroid Catchment Proxy:** Proximity is modeled as a 750m geodesic facility-to-Census-block-centroid catchment proxy, not individualized walking-network pedestrian routing.
