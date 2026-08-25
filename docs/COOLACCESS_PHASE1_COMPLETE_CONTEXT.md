# CoolAccess: Archived Phase 1 Context (Superseded)

> **Archive notice (2026-08-25):** This is an earlier planning/productization checkpoint,
> not the current source of truth. The running application, locked scenario, tests, and
> `README.md` are authoritative.

**Document Version:** 1.0.0  
**Phase Completed:** Phase 1 (Productization Layer — Scenario Packaging, FastAPI Service & Automated Verification)  
**Status:** `ARCHIVED_SUPERSEDED_BY_RUNNING_IMPLEMENTATION`
**Evaluation Date:** 2026-08-24  
**Primary Author:** Antigravity (Solo Participant Pair)  

---

## 1. Project Overview

### What CoolAccess Is
**CoolAccess** is an evidence-backed municipal decision product designed for municipal heat-response, resilience, and emergency-management teams. It supports one specific, high-stakes municipal operational decision:

> **Given a fixed municipal budget limit ($K = 3$ cooling centers), which existing eligible public facilities should receive limited activation or extended-service priority as hyperlocal heat patterns shift across neighborhoods?**

### The Core Problem It Solves
Cities facing extreme heat waves have dozens of public facilities (libraries, recreation centers, community centers), but severely constrained operational budgets, staffing, and security resources to activate or extend cooling hours at only a few (e.g. $K = 3$).

Currently, municipal leaders may rely on static daytime plans or unweighted citywide average temperatures. This can misalign allocation with the defined objective:
1. **Static Blindness:** A facility set chosen for the prepared 16:00 temperature state covers less heat-weighted demand at 20:00.
2. **Heatmap-Only Fallacy:** Choosing the hottest single sensor location often wastes resources on low-density or non-residential zones while ignoring dense residential demand and overlapping facility catchments.

### The Core Technical Idea
CoolAccess integrates **FortyGuard 2-meter street-level temperature evidence** with **official Decennial Census residential population** and **spatial accessibility catchments** into a **deterministic maximum-coverage combinatorial optimization model**:
$$\max_{S \subseteq \mathcal{F}_{\text{eligible}}, |S| \le K} \sum_{i \in \bigcup_{j \in S} \mathcal{A}_j} P_i \cdot w(T_i)$$
where:
* $P_i$ is the official 2020 Census residential population of block $i$.
* $w(T_i) \in [0, 1]$ is the normalized thermal priority derived from FortyGuard hyperlocal temperatures via fixed anchors across the scenario.
* $\mathcal{A}_j$ is the 750m geographic accessibility catchment of facility $j$.
* Union coverage arithmetic prevents double-counting residents living in overlapping catchments.

### Central Product Proof
> **Same city. Same 6 facilities. Same 100,389 residents. Same resource budget ($K=3$).**  
> **Different hyperlocal heat $\implies$ Different optimal facility allocation.**

---

## 2. Locked Scientific Scenario (Washington, DC)

The scenario was empirically discovered, screened, probed, and locked through Gates A, B1, B2, C, and the Scenario-Lock Audit:

### Geographic Area of Interest (AOI)
* **City:** Washington, District of Columbia (USA)
* **AOI Name:** DC Downtown / Capitol Hill / Southwest Waterfront Corridor
* **AOI Area:** `14.61 km²` contiguous urban rectangle
* **Bounding Box:** Longitude `[-77.030, -76.992]`, Latitude `[38.875, 38.915]`
* **Timezone:** `America/New_York` (EDT = UTC - 4)

### Eligible Municipal Facilities ($N = 6, K = 3$)
Strictly filtered to official public municipal libraries and recreation centers with general public walk-in access:
1. **`DC_089`** — *Shaw Library (Watha T. Daniel)* (`1630 7th St NW` | Lat: `38.912442`, Lon: `-77.022218`)
2. **`DC_135`** — *Martin Luther King Jr. Memorial Library (Central Library)* (`901 G St NW` | Lat: `38.898692`, Lon: `-77.024766`)
3. **`DC_148`** — *Northeast Library* (`330 7th St NE` | Lat: `38.894676`, Lon: `-76.996173`)
4. **`DC_159`** — *Southeast Library* (`403 7th St SE` | Lat: `38.884157`, Lon: `-76.996078`)
5. **`DC_166`** — *Randall Recreation Center* (`820 South Capitol St SW` | Lat: `38.880479`, Lon: `-77.009363`)
6. **`DC_168`** — *Southwest Library* (`901 Wesley Pl SW` | Lat: `38.879505`, Lon: `-77.016335`)

### Official Population Foundation
* **Source:** U.S. Census Bureau 2020 Decennial Census Redistricting Data (P.L. 94-171), Table P1 (Total Population).
* **Geography Level:** 2020 Census Blocks (District of Columbia).
* **Retained Units:** **887 Census blocks** with geometric centroids inside the locked AOI.
* **Total Residential Population:** **`100,389` residents** (`534` populated blocks, `353` zero-pop monumental/commercial blocks).
* **Spatial Coverage Completeness:** **100.0%** (zero missing blocks, zero unassigned geometries).
* **Operational Disclaimer:** Represents permanent Census residential population, not real-time pedestrian occupancy.

### Hyperlocal Thermal Foundation
* **Provider:** FortyGuard Street-Level Thermal API (`tcm` model, 100m raster grid, 1,452 tiles).
* **Historical Heatwave Date:** `2024-07-15`
* **Diurnal Snapshots Evaluated:**
  * `14:00 UTC` (~10:00 EDT — prepared historical snapshot)
  * `16:00 UTC` (~12:00 EDT — static-baseline reference)
  * `18:00 UTC` (~14:00 EDT — prepared historical snapshot)
  * `20:00 UTC` (~16:00 EDT — allocation-change demonstration)
  * `22:00 UTC` (~18:00 EDT — prepared historical snapshot)

### Spatial Accessibility & Resource Budget
* **Resource Constraint:** $K = 3$ concurrent active facilities. The solver evaluates all 42 subsets of zero through three facilities for the six-candidate benchmark; 20 of those subsets use the full three-facility budget.
* **Catchment Radius:** **`750 meters`** geodesic straight-line distance ($53.68\%$ union population coverage).

---

## 3. Evidence and Scenario Lock

### The Primary Demonstration Shift (`16:00 UTC` $\to$ `20:00 UTC`)

```text
16:00 UTC (Static-Baseline Reference):
  Optimal Set: { DC_089, DC_148, DC_166 }
  Objective:   40,567.30 heat-weighted demand units (Covered Population: 41,876)

20:00 UTC (Prepared Historical Snapshot):
  Optimal Set: { DC_089, DC_135, DC_166 }
  Objective:   8,328.93 heat-weighted demand units (Covered Population: 38,357)

Decision Change: DC_148 (Northeast Library) is replaced by DC_135 (MLK Jr. Memorial Library)
```

### Authoritative Evidence Supporting the Shift
1. Prepared FortyGuard temperatures change the normalized thermal-priority weights used in the heat-weighted-demand objective.
2. The locked data contains no canopy, masonry, irradiance, or urban-canyon causal fields, so CoolAccess does not claim those mechanisms.
3. At 20:00, replacing selected `DC_135` with unselected `DC_148` adds `3,519` residents of coverage but lowers the objective by **`1,594.45`** heat-weighted demand units.

### Baseline Comparison Proof at 20:00 UTC (750m)
* **Dynamic Optimal Allocation:** **`8,328.926099`** (display: `8,328.93`).
* **Static Baseline (reusing 16:00 set):** **`6,734.476716`** (display: `6,734.48`).
* **Gain over Static Baseline:** **`+1,594.449383` (`+23.6759%`)**; display: `+1,594.45` and `+23.68%`.
* **Naive Hottest-Catchment Baseline:** Same facilities and objective as the dynamic optimum at 20:00; gain = **zero**.

### Archived Exploratory Robustness Work
Earlier analysis recorded the transition across the variants below. The packaged runtime uses
the locked Robust Fixed Anchors scenario; it does not present the other variants as runtime modes.
1. **Normalization Method A:** Robust Fixed Anchors ($[32.022^\circ\text{C}, 37.699^\circ\text{C}]$).
2. **Normalization Method B:** Pooled Empirical Cumulative Distribution Function (CDF).
3. **Spatial Assignment Sensitivity:** Centroid-in-tile vs Area-Weighted Sutherland-Hodgman Polygon Intersection.

---

## 4. Current Architecture

The core architecture follows strict domain-driven design, immutability, and provider-neutral isolation:

```text
CoolAccess/
├── data/
│   └── locked_dc_scenario/        # Packaged scenario evidence bundle
│       ├── metadata.json
│       ├── facilities.json
│       ├── census_blocks.json
│       ├── thermal_snapshots.json
│       ├── catchments.json
│       └── geojson/
├── docs/                          # Specifications, architecture, and context
├── src/
│   └── coolaccess/                # Core Python package
│       ├── contracts.py           # Immutable Pydantic v2 domain models
│       ├── demand.py              # Exact Decimal arithmetic & demand calculations
│       ├── coverage.py            # Exact set union coverage over cells
│       ├── optimizer.py           # Exhaustive combinatorial solver (N=6, K=3)
│       ├── baselines.py           # Static & Naive baseline evaluators
│       ├── replacement.py         # 1-for-1 facility replacement engine
│       ├── metrics.py             # Percentage gains & safe comparisons
│       ├── analysis.py            # analyze_future_state() orchestrator
│       ├── canonical.py           # SHA-256 fingerprinting & JSON canonicalization
│       ├── scenario.py            # ScenarioBundle loader & request builder
│       ├── server.py              # FastAPI REST backend application
│       ├── errors.py              # Typed domain errors
│       └── __init__.py            # Package entry points
└── tests/                         # 130 passing tests (100% pass rate)
```

### Key Modules in `src/coolaccess/`
* **`contracts.py`**: Pydantic v2 immutable models (`AllocationRequest`, `PopulationCell`, `FacilityDefinition`, `AccessibilityRelationship`, `CoverageSummary`, `FacilityCoverage`, `AllocationResult`, `BaselineResult`, `CompleteBaselineResult`, `BaselineComparison`, `ReplacementEvidence`, `ProvenanceRecord`).
* **`demand.py`**: Fixed-precision Decimal demand ($P_i \times w_i$), exact sums, and canonical decimal representations with trailing-zero normalization.
* **`coverage.py`**: Evaluates union covered demand and population for any subset of facilities without double-counting.
* **`optimizer.py`**: `optimize(request) -> AllocationResult` executes exhaustive $\binom{N}{K}$ power-set search with 4-level deterministic tie-breaking.
* **`baselines.py`**: `evaluate_static_baseline()` and `evaluate_naive_baseline()`.
* **`replacement.py`**: `build_replacement_evidence()` computes exact 1-for-1 facility swap loss, population delta, and machine-owned reason codes.
* **`metrics.py`**: `calculate_coverage_percentage()` and `compare_with_baseline()` with division-by-zero guards (`MetricStatus.NOT_APPLICABLE`).
* **`analysis.py`**: `analyze_future_state(target_request, prior_allocation) -> AllocationAnalysisResult` executes target optimization, baselines, comparisons, and replacement matrix in one atomic call.
* **`canonical.py`**: Generates SHA-256 structural and full-state fingerprints for caching and consistency checks.

> [!IMPORTANT]
> **Architectural Invariant:** The deterministic core (`contracts.py`, `demand.py`, `coverage.py`, `optimizer.py`, `baselines.py`, `replacement.py`, `metrics.py`, `analysis.py`, `canonical.py`, `errors.py`) is fully audited and **MUST NOT BE REWRITTEN OR REPLACED**.

---

## 5. Current Product Layer (Phase 1 Implemented)

### Scenario Data Bundle (`CoolAccess/data/locked_dc_scenario/`)
Completely separates real-world empirical data from source code:
* `metadata.json`: Scenario configuration, AOI bounds, and provenance records.
* `facilities.json`: Complete attributes for the 6 locked facilities.
* `census_blocks.json`: 887 Census blocks with Table P1 population and coordinates.
* `thermal_snapshots.json`: FortyGuard 100m grid temperatures for all 5 timestamps.
* `catchments.json`: 750m geodesic proximity matrices.
* `geojson/`: `aoi.geojson`, `facilities.geojson`, `grid.geojson`, `census_blocks.geojson`.

### Scenario Loader (`src/coolaccess/scenario.py`)
* `ScenarioBundle`: Container providing high-level scenario access.
* `load_locked_scenario()`: Factory function loading data from disk and validating completeness.
* `build_allocation_request(timestamp, radius_meters=750, k=3)`: Instantiates validated immutable `AllocationRequest` instances.
* `get_geojson(layer, timestamp)`: Returns GeoJSON FeatureCollections enriched with active temperature and thermal priority.

### FastAPI REST Service (`src/coolaccess/server.py`)
Exposes minimal REST endpoints:
* **`GET /api/health`**: Health check reporting service status, scenario ID, and version.
* **`GET /api/scenario`**: Returns scenario metadata, AOI, candidate facilities, timestamps, budget $K=3$, radius $750\text{m}$, and provenance.
* **`GET /api/allocate?timestamp={ts}&baseline_timestamp={bts}`**: Computes dynamic optimum, static baseline, naive baseline, baseline comparisons, and replacement summary.
* **`GET /api/replacement?timestamp={ts}`**: Automatically returns primary replacement evidence (`DC_135` vs `DC_148` at 20:00 UTC) with objective loss, population delta, and physical explanation, plus the full $3 \times 3$ swap matrix.
* **`GET /api/geojson?layer={layer}&timestamp={ts}`**: Returns map-ready GeoJSON FeatureCollections (`aoi`, `facilities`, `thermal`, `demand`, `all`).

---

## 6. Verification Status

All checks execute cleanly with zero warnings or errors:

| Tool | Status | Output Details |
| :--- | :---: | :--- |
| **Pytest** | **PASS** | `130 passed in 4.38s` (119 core tests + 11 scenario/server tests) |
| **Ruff Check** | **PASS** | `All checks passed!` (0 lint errors across entire repository) |
| **Ruff Format** | **PASS** | `39 files already formatted` |
| **Mypy (Strict)** | **PASS** | `Success: no issues found in 27 source files` |

---

## 7. Important Development Rules

When continuing development in subsequent phases:
1. **Repository Scope:** Do NOT touch `HeatOps AI` or `FortyGuard-Quickstart`. Work strictly inside `CoolAccess/`.
2. **Locked Scientific Scenario:** Do NOT alter the locked AOI, facilities, timestamps, $K=3$, or proximity radius.
3. **No Database / Heavy Services:** Do NOT introduce PostgreSQL/PostGIS, Redis, or Celery. The entire scenario payload is $< 2\text{ MB}$ and operates cleanly in memory.
4. **Self-Contained & Secret-Safe:** The demo operates from the locked, verified historical dataset (`2024-07-15`), eliminating live API network dependencies or credit consumption during judging.
5. **No LLM in Decision Path:** All explanations, replacement rankings, and reason codes are derived deterministically.
6. **Strict Terminology:**
   * Proximity catchments must be labeled as *750m geographic accessibility proxies*, never *walking distance* or *walking time*.
   * Population must be labeled as *2020 Decennial Census residential population*, never *real-time pedestrian presence* or *current occupancy*.

---

## 8. Next Phase Plan (Phase 2: Interactive Demo Dashboard)

Phase 2 will build the desktop-first interactive municipal web dashboard on top of the Phase 1 FastAPI backend.

### Expected Technology Stack
* **Frontend Framework:** React + Vite
* **Map Engine:** Leaflet / React-Leaflet
* **Styling:** Modern, clean, responsive Vanilla CSS / CSS Modules
* **Backend API:** Existing FastAPI service (`coolaccess.server:app` running at `http://127.0.0.1:8000`)

### Key Interactive Features
1. **Interactive Thermal Map:**
   * Fixed-scale FortyGuard continuous thermal raster ($32.0^\circ\text{C} - 37.7^\circ\text{C}$).
   * Prepared temperature and 2020 Census population evidence remain semantically distinct.
   * 6 facility markers with high-contrast active ($K=3$) vs inactive styling.
   * 750m proximity catchment circles/buffers.
2. **Time Control Switcher:**
   * One-click toggle among five prepared historical timestamps from `14:00` through `22:00` UTC.
3. **Dynamic Coverage & Metrics Cards:**
   * Covered heat-weighted demand, total demand, covered population, and percentage coverage.
4. **Side-by-Side Baseline Proof Panel:**
   * Sign-aware comparison of *Dynamic Optimized*, *Static Baseline*, and *Naive Hottest-Catchment Baseline*.
5. **Interactive Replacement Evidence Drawer:**
   * Facility-swap evidence with deterministic objective loss and population delta, without unsupported physical causes.
6. **Judge-Friendly Presentation Flow:**
   * Clean, single-screen dashboard layout matching `docs/PRODUCT_AND_DEMO.md`.

---

## 9. Recommended Demo Story (90–120 Seconds)

1. **Establish the Municipal Constraint (0–15s):**
   * *“Washington, DC has multiple public facilities, but resources to activate or extend cooling hours at only three ($K=3$). How should the city prioritize them?”*
2. **Show NOW State at Midday 16:00 UTC (15–40s):**
   * Display FortyGuard midday heat layer.
   * Point to the optimal allocation: `{DC_089, DC_148, DC_166}`.
   * Explain that Northeast Library (`DC_148`) is selected because high midday heat coincides with its large residential population.
3. **Trigger the Temporal Shift to 20:00 UTC (40–70s):**
   * Click the `20:00 UTC` time button.
   * Observe the atomic update from the prepared 16:00 state to the prepared 20:00 state.
   * Point to the dynamic reallocation: `{DC_089, DC_135, DC_166}` (`DC_148` is replaced by `DC_135` MLK Library).
4. **Prove Superiority Over Baselines (70–95s):**
   * Open the Baseline Comparison panel.
   * Show static `6,734.48` versus dynamic `8,328.93`: **`+1,594.45` (`+23.68%`)**.
   * Note that the naive hottest-catchment baseline ties the dynamic optimum at 20:00.
5. **Inspect Replacement Evidence (95–120s):**
   * Open the Replacement Drawer for `DC_135` vs `DC_148`.
   * Show that substituting `DC_148` adds `3,519` residents of coverage but lowers heat-weighted demand by **`1,594.45`** units.
   * Conclude: *“FortyGuard changed the thermal-priority weights; under the same K=3 facility-count budget, the optimizer changed one facility and covered 1,594.45 more heat-weighted demand units than the retained set.”*

---

## 10. Final Status

```text
STATUS: ARCHIVED_SUPERSEDED_BY_RUNNING_IMPLEMENTATION
```
