# CoolAccess Municipal Dashboard — Frontend

Interactive municipal decision dashboard for **CoolAccess: Dynamic Cooling Resource Allocation**.

This frontend provides a professional GIS and operational decision interface for municipal heat-response, resilience, and emergency-management teams working under a constrained cooling-facility count ($K = 3$).

---

## 1. Frontend Architecture

The frontend is built with **React + TypeScript + Vite**, utilizing **Leaflet** for geospatial map visualization and standard React state hooks for reactive, atomic state synchronization.

### Key Architectural Principles
* **Municipal/GIS Aesthetic:** High-contrast, clean administrative typography, slate/neutral surfaces, and standardized GIS symbology. Avoids gaming/neon styles in favor of municipal decision clarity.
* **Terminology Precision:** 
  * FortyGuard heat data is labeled as **100m thermal grid GeoJSON overlay**.
  * Population is labeled as **2020 Decennial Census residential population**.
  * Catchments are labeled as **750m geographic accessibility proxies**.
* **Atomic State Updates:** Switching timestamps atomically updates the thermal grid overlay, facility selections ($K=3$), demand metrics, baseline comparison cards, and 1-for-1 replacement evidence.
* **Pure React State:** No external heavyweight state libraries; uses clean React hooks (`useState`, `useEffect`, `useMemo`, `useCallback`) and typed fetch client.

### Component Structure
```text
frontend/src/
├── main.tsx                    # React application entry point
├── App.tsx                     # Main layout & coordinator state (selected timestamp, layer visibility)
├── index.css                   # Global reset, typography, and municipal theme tokens
├── types/
│   └── index.ts                # TypeScript interfaces matching FastAPI JSON schema
├── api/
│   └── client.ts               # Typed REST client with error handling
└── components/
    ├── Header.tsx              # Scenario context bar (City, AOI, Date, Budget K=3, Radius, Provenance)
    ├── TimelineControl.tsx     # 5-timestamp diurnal switcher with prominent 16:00 vs 20:00 demo triggers
    ├── AllocationImpactStrip.tsx # First-screen allocation, baseline, and population trade-off proof
    ├── MapView.tsx             # Leaflet GIS map with FortyGuard 100m thermal grid, catchments, and facilities
    ├── ThermalLegend.tsx       # Standardized continuous thermal legend (32.0°C – 37.7°C)
    ├── MetricsSummary.tsx      # Heat-weighted demand and Census residential population cards
    ├── FacilityList.tsx        # Active K=3 facility status cards with unique demand contributions
    ├── BaselineComparison.tsx  # Side-by-side proof panel (Dynamic Optimum vs Static vs Naive Baseline)
    ├── HeatIntelligencePanel.tsx # Bounded query routing and authoritative claim-ledger presentation
    ├── ReplacementDrawer.tsx   # Deterministic 1-for-1 facility substitution evidence
    └── DisclosuresFooter.tsx   # Official data sources, legal notices, and methodology disclosures
```

---

## 2. Setup & Installation

### Prerequisites
* **Node.js**: v18.0+ (tested on v22.16+)
* **npm**: v9.0+ (tested on v11.4+)
* **Python**: 3.11+ (for the FastAPI backend)

### Install Dependencies
From the repository root or inside `frontend/`:

```bash
cd frontend
npm install
```

Installed dependencies:
* `react`, `react-dom`
* `leaflet`, `react-leaflet`, `@types/leaflet`
* `lucide-react` (clean administrative icons)

---

## 3. Backend Connection

The frontend connects to the CoolAccess FastAPI backend service running at `http://127.0.0.1:8000`.

### Backend API Endpoints Utilized:
* `GET /api/health` — Service readiness & scenario identification.
* `GET /api/scenario` — Scenario metadata, AOI, candidate facilities ($N=6$), timestamps, and provenance.
* `GET /api/allocate?timestamp={ts}&baseline_timestamp=16:00` — Dynamic optimum, static baseline, naive baseline, per-facility metrics.
* `GET /api/replacement?timestamp={ts}&selected_id={sid}&unselected_id={uid}` — 1-for-1 facility replacement evidence & loss calculations.
* `GET /api/geojson?layer={layer}&timestamp={ts}` — Map GeoJSON features for AOI, facilities, 100m thermal grid, and demand blocks.

### Local Development Proxy
During development, Vite proxies all requests starting with `/api` to `http://127.0.0.1:8000`:
```typescript
// vite.config.ts
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
```

---

## 4. Development & Build Commands

### Start the FastAPI Backend (Terminal 1)
From the repository root:
```bash
python -m uvicorn coolaccess.server:app --host 127.0.0.1 --port 8000 --reload
```

### Start the Frontend Dev Server (Terminal 2)
From `frontend/`:
```bash
cd frontend
npm run dev
```
Open your browser at `http://localhost:5173`.

### Production Build & Typecheck
```bash
cd frontend
npm run build
```
Build output is generated in `frontend/dist/`.

---

## 5. Judge Presentation & Demo Flow

The dashboard is optimized for a 90–120 second municipal presentation:

1. **Establish Decision Context:**
   - Washington, DC ($14.61\text{ km}^2$ corridor, 100,389 Census residents, 6 public facilities).
   - Fixed budget limit of **$K = 3$** cooling centers.
2. **State 1 — Static-Baseline Reference (`16:00 UTC / 12:00 EDT`):**
   - Click **`16:00 UTC (Reference)`**.
   - Optimal Set: `{DC_089 Shaw, DC_148 Northeast, DC_166 Randall}`.
3. **State 2 — Allocation Change (`20:00 UTC / 16:00 EDT`):**
   - Click **`20:00 UTC (Late Afternoon)`**.
   - The prepared FortyGuard grid supplies the observed temperature state; the benchmark does not contain fields that establish physical causes for the spatial pattern.
   - Dynamic reallocation shifts to `{DC_089 Shaw, DC_135 MLK Memorial, DC_166 Randall}` (Northeast Library is replaced by MLK Memorial Library).
4. **Baseline Proof:**
   - The dynamic set covers **8,328.93** heat-weighted demand units versus **6,734.48** for the retained 16:00 set: **+1,594.45** or **+23.68%**, under the same $K=3$ facility-count budget.
   - The naive hottest-catchment baseline selects the same set and objective at 20:00, so the dynamic optimum has **zero gain over naive** at this timestamp.
   - Dynamic population coverage is **38,357**, versus **41,876** for the retained set: **3,519 fewer residents** while the heat-weighted objective is higher.
5. **Replacement Evidence Inspection:**
   - Open Replacement Inspector (`DC_135` vs `DC_148`).
   - Substituting `DC_148` adds **3,519** residents of coverage but lowers the deterministic heat-weighted-demand objective by **1,594.45** units. CoolAccess does not infer why the observed temperatures differ.
