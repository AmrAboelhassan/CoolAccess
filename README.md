# CoolAccess

> CoolAccess helps municipal heat-response teams decide which existing public facilities should receive limited activation or extended-service priority as hyperlocal heat shifts across neighborhoods.

**Dynamic Cooling Resource Allocation**

CoolAccess is a deterministic municipal decision-support prototype built for the FortyGuard Global AI Hackathon 2026. It converts FortyGuard hyperlocal thermal intelligence, licensed residential population data, existing public facility locations, and a fixed resource budget constraint into a mathematically verified maximum-coverage recommendation.

The product's central proof is:

> Same city. Same facilities. Same population. Same resource budget.  
> Different hyperlocal heat -> different optimal allocation.

---

## Current Status

**Verified Deterministic Core & Interactive Decision Prototype**

* **Validated Empirical Benchmark:** Washington, DC scenario locked and empirically verified using real FortyGuard street-level thermal evidence and official 2020 U.S. Census population data.
* **Deterministic FastAPI Backend:** Strict Pydantic contracts, exact Decimal demand calculations, exhaustive combinatorial maximum-coverage optimizer, baseline models, and replacement loss evidence.
* **Interactive React GIS Dashboard:** Leaflet geospatial canvas, diurnal timeline controls, performance metrics, facility cards, baseline comparison panel, and 1-for-1 replacement drawer.
* **131 Passing Automated Tests:** 100% pass rate covering contracts, optimizer, baselines, coverage, replacement loss, repeatability, scenario loading, and server API endpoints.
* **Inspectable & Provenance-Preserved:** Full-state SHA-256 fingerprints, immutable data provenance registries, and zero black-box heuristics.

---

## 1. What CoolAccess Does

During extreme summer heat, urban surface materials, canyon geometries, and tree canopies cause temperatures to vary substantially across adjacent neighborhoods. Municipalities typically operate multiple public facilities (libraries, recreation centers) but possess the budget or staffing to prioritize only a small subset ($K = 3$) for active cooling operations or extended operating hours.

Traditional heatmaps only display where heat is located; they do not account for where residents live, facility proximity reach, overlapping service areas, or hard budget limits.

CoolAccess solves this with a **deterministic combinatorial optimization engine**:
1. Ingests FortyGuard street-level thermal intelligence, mapped onto an internal 100m geospatial analysis grid across the municipal area of interest.
2. Combines thermal priority with official residential population at Census-block resolution to compute heat-weighted demand.
3. Constructs geographic accessibility catchments around candidate public facilities.
4. Deterministically evaluates all feasible facility combinations to maximize union heat-weighted demand coverage without double counting.
5. Proves allocation value against two rigorous baselines: a **Static Baseline** (retaining the midday plan) and a **Naive Thermal Baseline** (selecting centers nearest the hottest hotspots without population weighting).
6. Generates full one-for-one **Replacement Loss Evidence** explaining exactly why every selected facility outperforms each unselected alternative.

---

## 2. Validated Empirical Benchmark (Washington, DC)

CoolAccess includes a fully validated, provenance-tracked empirical scenario for **Washington, DC** (`14.61 km²` Downtown / Capitol Hill / SW Waterfront corridor):

* **Official Population:** 2020 U.S. Census Bureau Decennial Census Redistricting Data (Table P1: `100,389` residents across `887` retained Census blocks, mapped 100% to FortyGuard grid cells).
* **Thermal Evidence:** 5 diurnal FortyGuard street-level thermal snapshots evaluated across the internal 100m analysis grid on July 15, 2024 (`14:00`, `16:00`, `18:00`, `20:00`, `22:00` UTC).
* **Candidate Facilities:** 6 public DC libraries and recreation centers from DC Open Data / OCTO under fixed budget $K = 3$.
* **Empirical Finding:** As midday heat (`16:00 UTC`) transitions to late afternoon (`20:00 UTC`), optimal activation dynamically shifts from `{DC_089, DC_148, DC_166}` to `{DC_089, DC_135, DC_166}` (activating MLK Jr. Memorial Library `DC_135` over Northeast Library `DC_148`).
* **Measured Gain:** The dynamic allocation delivers a **`+23.81%` gain** in covered heat-weighted demand over the static baseline at 750m proximity (**`+55.22%` gain** at 500m).
* **Decision Robustness:** The selection change is identical under both Robust Fixed Anchors (1st–99th percentiles) and Pooled Empirical CDF normalization models.

---

## 3. Architecture & Role of AI

```
+--------------------------------------------------------+
|                  CoolAccess Prototype                  |
|                                                        |
|  +-----------------------+   +----------------------+  |
|  | React 18 + Vite + TS  |   |   FastAPI Backend    |  |
|  | Interactive GIS UI    |<--| (Provider-Neutral)   |  |
|  +-----------------------+   +----------+-----------+  |
|                                         |              |
|                              +----------v-----------+  |
|                              | Deterministic Engine |  |
|                              |  * Demand Weighting  |  |
|                              |  * Union Coverage    |  |
|                              |  * Baseline Engine   |  |
|                              |  * Replacement Loss  |  |
|                              +----------+-----------+  |
|                                         |              |
|                              +----------v-----------+  |
|                              | Locked DC Benchmark  |  |
|                              | (FortyGuard + Census)|  |
|                              +----------------------+  |
+--------------------------------------------------------+
```

### Deterministic Decision Authority vs. AI Augmentation

* **Deterministic Decision Authority:** In municipal and emergency heat response, critical resource allocation decisions cannot be delegated to probabilistic or generative models. The CoolAccess combinatorial optimizer holds exclusive mathematical authority over all facility allocations, baseline evaluations, and replacement losses.
* **Bounded AI Strategy:** Any future AI/LLM components (such as an Evidence Narrator or Operations Copilot) are architected strictly as read-only, evidence-grounded explanation layers. The AI layer translates structured replacement evidence and provenance records into natural-language briefs, with zero authority to alter numerical outputs, constraints, or facility selections.
* **Fail-Closed Independence:** CoolAccess is completely self-contained and fully functional without an external LLM dependency or API key.

### AI Architecture Positioning

CoolAccess intentionally separates **decision authority** from **decision explanation**:

* The deterministic combinatorial optimizer is the sole decision authority. It produces all facility selections, coverage metrics, baseline comparisons, and replacement evidence.
* AI (LLM/Agent) components are architecturally positioned as an **optional, read-only explanation layer**. When present, they translate structured optimizer outputs into natural-language operational briefs — but they cannot modify, override, or influence any numerical result.
* This separation ensures that every allocation recommendation is fully reproducible, mathematically verifiable, and independent of any external AI service availability.

---

## 4. Interactive Demo Walkthrough

The single-page GIS application demonstrates the municipal decision workflow across five key states:

1. **Scenario Canvas:** View the Washington, DC bounding corridor (`14.61 km²`), all 6 eligible public facilities, and the fixed budget constraint ($K = 3$).
2. **Midday Optimal Allocation (`16:00 UTC`):** Observe the midday thermal pattern and initial optimal facility subset (`{DC_089, DC_148, DC_166}`).
3. **Diurnal Heat Shift (`20:00 UTC`):** Advance the timeline slider to late afternoon. The map and metrics update atomically, dynamically replacing `DC_148` with `DC_135` (MLK Jr. Memorial Library) as commercial canyon heat persists.
4. **Baseline Proof Panel:** Directly compare the dynamic allocation against the **Static Baseline** (retaining midday facilities: **`+23.81%` gain**) and the **Naive Thermal Baseline**.
5. **1-for-1 Replacement Drawer:** Open detailed replacement evidence explaining why `DC_135` outperforms `DC_148` and other unselected alternatives based on unique heat-weighted population coverage.

---

## 5. Local Development & Verification

### Prerequisites
* Python 3.11+
* Node.js 20+ & npm

### Backend Setup
```powershell
# Create and activate virtual environment
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1

# Install package in editable mode with development dependencies
pip install -e ".[dev]"

# Start the FastAPI server
uvicorn coolaccess.server:app --reload --port 8000
```
Backend API will be live at `http://127.0.0.1:8000` with interactive Swagger docs at `http://127.0.0.1:8000/docs`.

### Frontend Setup
```powershell
cd frontend
npm ci
npm run dev
```
The Vite development server runs on `http://localhost:5173` and connects to the FastAPI backend.

### Quality & Verification Commands
```powershell
# Run full test suite (131 tests)
python -m pytest

# Code style and lint checks
python -m ruff check .
python -m ruff format --check .

# Static type checking
python -m mypy src tests

# Frontend production build verification
cd frontend && npm run build
```

---

## 6. Documentation

- [Competition specification](docs/COOLACCESS_COMPETITION_SPEC_V1.md) - canonical product scope and Definition of Done
- [Product and demo](docs/PRODUCT_AND_DEMO.md) - user journey, interface states, baselines, and 90-150 second demo script
- [Technical architecture](docs/TECHNICAL_ARCHITECTURE.md) - boundaries, contracts, reliability, and deployment assumptions
- [Optimization model](docs/OPTIMIZATION_MODEL.md) - thermal demand, maximum coverage formulation, baselines, and evidence
- [Data and city selection](docs/DATA_AND_CITY_SELECTION.md) - city gate, source candidates, licensing, and scenario materiality
- [Build plan](docs/BUILD_PLAN.md) - dependency-ordered implementation plan
- [Risk register](docs/RISK_REGISTER.md) - delivery, data, technical, judging, and submission risks
- [Organizer questions](docs/ORGANIZER_QUESTIONS.md) - unresolved rules and authenticated API details
- [Submission checklist](docs/SUBMISSION_CHECKLIST.md) - confirmed requirements and final checks
- [Decision log](docs/DECISIONS.md) - accepted, provisional, rejected, and unresolved decisions

---

## 7. Product Boundary

CoolAccess has one primary user: a municipal heat-response, resilience, emergency-management, or public-facilities team. It supports one decision: which eligible existing facilities should receive limited activation or extended-service priority under a fixed facility constraint.

P0 is not a general smart-city platform, a public cooling-center finder, a public-health prediction system, a facility operations system, or a mobile-resource dispatch product. It does not estimate degrees cooled, injuries prevented, lives saved, medical safety, or guaranteed outcomes. Its metrics are scenario-specific planning and geographic-accessibility proxies.

Verified operating hours may strengthen the scenario but are not required. Without trustworthy hours, CoolAccess recommends priority among eligible facilities and does not claim that a facility is open, closed, or operationally extendable.

---

## 8. Decision Integrity

- FortyGuard temperature data remains essential and central.
- The deterministic combinatorial optimizer owns 100% of authoritative allocation and prioritization decisions.
- The core decision engine contains zero LLM logic in the decision-making path.
- P0 remains fully functional, inspectable, and reproducible without an external AI service.
- NOW and future states use one fixed, comparable thermal-normalization reference.
- Low thermal contrast is disclosed and cannot support a competition scenario.
- Static and naive heat-only baselines use the exact same facilities, population, timestamp, proximity method, and resource constraint as the optimized result.
- Missing provider data is unavailable, not zero and not synthetic.
- Source timestamps, retrieval times, transformations, licenses, and cache/prepared state remain visible in provenance records.

---

## 9. Confirmed Competition Context

FortyGuard provides 2-meter street-level ambient air temperature; real and near-real-time data; history from January 1, 2021; approximately 20-meter resolution; hour-by-hour data; forecasts up to 12 hours; and U.S.-only hackathon coverage. External datasets are allowed when their licenses are respected and FortyGuard remains central.

The judging rubric is Impact & Relevance 40%, Technical Execution 35%, Innovation 15%, and Communication 10%. Confirmed submission requirements include a public GitHub repository, a live website/demo link, and adding `fortyguard` as a repository collaborator. The participant retains project ownership and FortyGuard receives a license to showcase it.
