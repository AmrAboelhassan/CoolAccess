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
* **Automated Verification:** Repository tests cover contracts, optimizer, baselines, coverage, replacement loss, repeatability, scenario loading, trust boundaries, and API endpoints. Run the suite for the current count and result.
* **Inspectable & Provenance-Preserved:** Full-state SHA-256 fingerprints, immutable data provenance registries, and explicit AI/fallback status.

---

## 1. What CoolAccess Does

During extreme summer heat, temperatures can vary across adjacent neighborhoods. Municipalities typically operate multiple public facilities (libraries and recreation centers) but may have resources to prioritize only a small subset ($K = 3$) for cooling-access planning. CoolAccess does not infer the physical cause of an observed temperature pattern.

Traditional heatmaps only display where heat is located; they do not account for where residents live, facility proximity reach, overlapping service areas, or hard budget limits.

CoolAccess solves this with a **deterministic combinatorial optimization engine**:
1. Ingests FortyGuard street-level thermal intelligence, mapped onto an internal 100m geospatial analysis grid across the municipal area of interest.
2. Combines thermal priority with official residential population at Census-block resolution to compute heat-weighted demand.
3. Constructs geographic accessibility catchments around candidate public facilities.
4. Deterministically evaluates every eligible facility subset up to the `K` limit to maximize union heat-weighted demand coverage without double counting.
5. Proves allocation value against two rigorous baselines: a **Static Baseline** (retaining the midday plan) and a **Naive Thermal Baseline** (ranking facilities by mean thermal priority across accessible catchment cells without population weighting or overlap accounting).
6. Generates full one-for-one **Replacement Loss Evidence** quantifying the objective and population-coverage effect of each eligible substitution.

---

## 2. Validated Empirical Benchmark (Washington, DC)

CoolAccess includes a fully validated, provenance-tracked empirical scenario for **Washington, DC** (`14.61 km²` Downtown / Capitol Hill / SW Waterfront corridor):

* **Official Population:** 2020 U.S. Census Bureau Decennial Census Redistricting Data (Table P1: `100,389` residents across `887` retained Census blocks, mapped 100% to FortyGuard grid cells).
* **Thermal Evidence:** 5 diurnal FortyGuard street-level thermal snapshots evaluated across the internal 100m analysis grid on July 15, 2024 (`14:00`, `16:00`, `18:00`, `20:00`, `22:00` UTC).
* **Candidate Facilities:** 6 public DC libraries and recreation centers from DC Open Data / OCTO under fixed budget $K = 3$.
* **Empirical Finding:** As midday heat (`16:00 UTC`) transitions to late afternoon (`20:00 UTC`), optimal activation dynamically shifts from `{DC_089, DC_148, DC_166}` to `{DC_089, DC_135, DC_166}` (activating MLK Jr. Memorial Library `DC_135` over Northeast Library `DC_148`).
* **Measured Static-Baseline Gain at 20:00:** `8,328.93 - 6,734.48 = 1,594.45` additional heat-weighted demand units, or **`23.68%`**, at the locked 750m radius.
* **Naive Baseline at 20:00:** The naive hottest-catchment baseline selects the same set and produces the same objective as the dynamic optimum, so the gain over naive is **zero** at this timestamp.
* **Population Trade-off at 20:00:** Dynamic resident coverage is `38,357`, versus `41,876` for the retained 16:00 set: `3,519` fewer residents covered while the heat-weighted objective is higher.

### Independent Allocation Robustness Checks

- **Population-Only Ablation:** At 20:00 UTC, population-only coverage retains `{DC_089, DC_148, DC_166}`, while FortyGuard-weighted allocation selects `{DC_089, DC_135, DC_166}` (the canonical DC_148 $\to$ DC_135 facility transition does not occur in the population-only ablation).
- **Catchment Sensitivity:** Positive dynamic-vs-static gain persisted across all 9 tested 500m–1000m geographic radii; the canonical DC_148 $\to$ DC_135 transition persisted at 8 of 9 tested radii.
- **Normalization Set Stability:** Optimal facility sets and diurnal transitions remained 100% stable across canonical P1/P99, empirical P5/P95, and snapshot min/max normalization anchors.
- **Reproducible Evidence Tooling:** Run offline verification directly via `python scripts/run_allocation_robustness_evidence.py`.

---

## Multi-Day FortyGuard Benchmark

- **Canonical Production Demo:** July 15, 2024 (Washington, DC, 14:00–22:00 UTC)
- **Additional Offline Benchmark:** July 16, 2024 (Washington, DC, 14:00–22:00 UTC)

Beyond the canonical July 15 production demo, CoolAccess was replayed offline against a second official FortyGuard historical day (July 16, 2024) using the same six facilities, Census population layer, catchments, K=3 budget, normalization, and deterministic optimizer with no parameter retuning.

At 20:00 UTC, the July 16 optimum retained DC_089, DC_148, and DC_166 and matched the static baseline, while exceeding the naive thermal baseline by 8,403.26 heat-weighted demand units (+34.69%). In contrast, July 15 produced the DC_148 → DC_135 transition at the same timestamp.

See the offline reproducible benchmark evaluation report: [`docs/MULTI_DAY_BENCHMARK_EVALUATION.md`](docs/MULTI_DAY_BENCHMARK_EVALUATION.md).

*Benchmark Scope & Limitations:*
- Operational eligibility scope: all six locked candidate facilities are treated as operationally eligible. Operating hours, current activation status, and facility service capacity are not modeled.
- Accessibility model: 750m geodesic facility-to-Census-block-centroid catchment proxy; not walking-network travel distance.
- Cross-day normalization: July 16 evaluation retains the canonical July 15 robust P1/P99 normalization anchors ([32.022°C, 37.699°C]) for calibration consistency; values outside are clamped to [0,1].
- Reproducibility: Canonical July 15 is reproducible from committed prepared benchmark artifacts in the repository; July 16 provides an auditable acquisition manifest and deterministic replay workflow with raw FortyGuard provider payloads retained local-only.
- Prepared historical data only; zero live weather feeds or forecast modeling.
- Two historical days evaluated; no claim of statistical generalization across all weather regimes or seasons.
- Population counts reflect decennial residential headcounts (2020 Census Table P1), not real-time foot-traffic.
- Decision support proxy; does not represent medical, physiological, or health outcome claims.

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
|                                         |              |
|                              +----------v-----------+  |
|                              | Evidence Claim Ledger|  |
|                              +----------+-----------+  |
|                                         |              |
|                              +----------v-----------+  |
|                              | Optional OpenRouter  |  |
|                              | tool/claim organizer |  |
|                              +----------------------+  |
+--------------------------------------------------------+
```

### Deterministic Decision Authority vs. AI Augmentation

* **Deterministic Decision Authority:** In municipal and emergency heat response, critical resource allocation decisions cannot be delegated to probabilistic or generative models. The CoolAccess combinatorial optimizer holds exclusive mathematical authority over all facility allocations, baseline evaluations, and replacement losses.
* **Bounded AI Strategy:** The current optional OpenRouter path classifies a supported question, proposes bounded read-only tools, and organizes authoritative claim IDs. A deterministic evidence planner resolves explicit entities, supplies mandatory evidence, validates timestamps and parameters, and enforces the final tool budget. Displayed factual prose is server-rendered from the active claim ledger; the model cannot write authoritative metrics or change the allocation.
* **Fail-Closed Independence:** CoolAccess is completely self-contained and fully functional without an external LLM dependency or API key.

### AI Architecture Positioning

CoolAccess intentionally separates **decision authority** from **decision explanation**:

* The deterministic combinatorial optimizer is the sole decision authority. It produces all facility selections, coverage metrics, baseline comparisons, and replacement evidence.
* The optional LLM is a **read-only query-routing and evidence-organization layer**. It selects from closed tools and claim IDs. The server validates intent, explicit facility precedence, tool semantics, mandatory evidence, claim references, and requested highlights before rendering claim-ledger text.
* Provider, schema, semantic, or grounding failure returns an intent-aware deterministic brief. Deterministic fallback is used only when authoritative scenario state exists. Mutation, medical/safety, regulatory, forecast, and live-weather requests return an explicit scope boundary.
* This separation ensures that every allocation recommendation is fully reproducible, mathematically verifiable, and independent of any external AI service availability.

---

## 4. Interactive Demo Walkthrough

The single-page GIS application demonstrates the municipal decision workflow across five key states:

1. **Scenario Canvas:** View the Washington, DC bounding corridor (`14.61 km²`), all 6 eligible public facilities, and the fixed budget constraint ($K = 3$).
2. **Midday Optimal Allocation (`16:00 UTC`):** Observe the midday thermal pattern and initial optimal facility subset (`{DC_089, DC_148, DC_166}`).
3. **Diurnal Allocation Change (`20:00 UTC`):** Advance the timeline slider. Using the prepared 20:00 FortyGuard temperature state, the deterministic optimizer replaces `DC_148` with `DC_135` (MLK Jr. Memorial Library). CoolAccess does not assert an unmeasured physical cause.
4. **Baseline Proof Panel:** Compare the dynamic allocation against the **Static Baseline** (retaining the 16:00 facilities: **`+1,594.45`, `+23.68%`**) and the **Naive Hottest-Catchment Baseline** (a tie at 20:00).
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
# Run the full test suite (the current count is reported by pytest)
python -m pytest

# Code style and lint checks
python -m ruff check .
python -m ruff format --check .

# Static type checking
python -m mypy src tests

# Frontend production build verification
cd frontend && npm run build
```

### Optional AI configuration

The packaged runtime supports OpenRouter through generic HTTPS; no provider SDK is required. AI is disabled by default and the deterministic product remains usable without a key.

```dotenv
COOLACCESS_AI_ENABLED=false
COOLACCESS_AI_PROVIDER=openrouter
COOLACCESS_AI_MODEL=openrouter/free
COOLACCESS_AI_API_KEY=
```

Do not expose the key to the frontend. Gemini is not a selectable packaged runtime provider because `google-genai` is not a project dependency.

---

## 6. Documentation

- [Competition specification](docs/COOLACCESS_COMPETITION_SPEC_V1.md) - archived pre-build scope; superseded details are labeled
- [Product and demo](docs/PRODUCT_AND_DEMO.md) - archived planning journey; current metrics live in this README and the app
- [Technical architecture](docs/TECHNICAL_ARCHITECTURE.md) - planning contracts plus a current-runtime clarification
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

The organizer describes broader FortyGuard live, historical, and forecast capabilities. This submission uses a prepared historical July 15, 2024 benchmark transformed to an internal 100m analysis grid. CoolAccess does not present that benchmark as live weather or a forecast.

The judging rubric is Impact & Relevance 40%, Technical Execution 35%, Innovation 15%, and Communication 10%. Confirmed submission requirements include a public GitHub repository, a live website/demo link, and adding `fortyguard` as a repository collaborator. The participant retains project ownership and FortyGuard receives a license to showcase it.
