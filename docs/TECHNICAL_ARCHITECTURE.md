# Technical Architecture

## 1. Architecture goals

In priority order:

1. Solo hackathon delivery and a repeatable public demo.
2. One clear municipal allocation decision.
3. Deterministic, inspectable optimization and baselines.
4. Fixed-reference temporal comparability.
5. Data provenance, licensing, and honest failure behavior.
6. Provider isolation and secret safety.
7. No infrastructure or optional feature that does not improve the judged product.

## 2. Proposed runtime shape

Use a small modular monolith: a desktop-first React map interface and a Python HTTP backend, deployed under one public origin when the selected host supports it.

```text
Browser
  -> scenario / analysis / status / allocation requests
Backend
  -> scenario service
  -> FortyGuard adapter
  -> external-data loader and normalizer
  -> spatial demand builder
  -> proximity builder
  -> fixed-reference thermal model
  -> deterministic optimizer and baselines
  -> evidence/provenance builder
  -> bounded cache and analysis coordinator
  -> FortyGuard API and approved public sources
```

The exact frontend framework, map library, backend framework, and host are provisional until the build period and deployment constraints are confirmed. The preferred implementation shape is React, Leaflet, FastAPI, and one container because it fits the small geospatial workload, but the planning contracts do not depend on those choices.

No database, durable queue, authentication system, microservice fleet, custom ML pipeline, or LLM service is required for P0.

## 3. Separation of responsibilities

### Frontend

- Render the map, candidates, selections, proximity coverage, time control, fixed-scale legend, metrics, baseline comparison, warnings, and evidence drawer.
- Treat a complete allocation response as one atomic timestamped state.
- Never compute authoritative temperatures, normalization, coverage, selection, or improvement.
- Never expose provider credentials.
- Never label proximity as walking access.

### Scenario service

- Return the locked city, AOI, timezone, `K`, data-source metadata, facility eligibility configuration, proximity configuration, and available samples.
- Keep source facts separate from prototype configuration and derived values.
- Refuse to mark a scenario demo-ready until Tasks 01A/01B evidence and materiality criteria pass.

### FortyGuard adapter

- Encapsulate authentication, requests, activity polling, statuses, errors, and provider fields.
- Validate timestamps, observed/forecast status, units, spatial geometry, and coverage.
- Normalize verified responses into provider-neutral temperature samples.
- Preserve source/retrieval times and safe activity provenance.
- Never create substitute temperatures.

Confirmed product capabilities include U.S. coverage, real/near-real-time data, history from 2021-01-01, hour-by-hour data, approximately 20-meter resolution, and forecasts up to 12 hours. Task 01A still must verify participant entitlements, exact schemas, practical timestamps, credits, AOI behavior, range semantics, and latency.

### External-data normalizer

- Load the selected facility, population, boundary, and optional geographic sources.
- Validate source version, license, coordinate reference system, stable identifiers, geometry, and required fields.
- Apply only documented transformations.
- Separate missing hours/capacity/accessibility fields from facility eligibility.
- Produce a data-quality and coverage report.

### Spatial demand builder

- Assign validated FortyGuard temperatures to population units using the locked spatial method.
- Construct the single fixed normalization reference from the full evaluated scenario sample.
- Calculate thermal priority and heat-weighted demand.
- Calculate spatial/temporal contrast evidence and apply the locked low-contrast rule.
- Preserve raw inputs and transformation versions.

### Proximity builder

- Generate disclosed geodesic/straight-line catchments.
- Relate population units to facilities as `A_i,j`.
- Report AOI edge effects, invalid geometries, unassigned population, and method completeness.
- Make no route, walking-time, capacity, or attendance claim.

### Optimizer and baseline service

- Enumerate eligible facility combinations up to `K`.
- Calculate union heat-weighted and raw population coverage without double counting.
- Apply stable ties.
- Independently optimize each timestamp.
- Evaluate the static NOW allocation and naive thermal allocation at the same future timestamp.
- Return replacement comparisons and machine-owned reason codes.

### Evidence and metrics builder

- Construct every authoritative number displayed by the frontend.
- Attach timestamps, units, source, vintage, license reference, normalization version, proximity method, cache mode, completeness, and warnings.
- Distinguish source facts, configured assumptions, and derived values.
- Return `not_applicable`, not misleading percentages, for zero denominators.

### Analysis coordinator and cache

- Submit bounded provider work and expose `pending`, `ready`, `partial`, or `failed` state.
- Poll without blocking browser requests indefinitely.
- Enforce request budgets, concurrency, deadlines, bounded retry, and cache policy.
- Keep in-process state for P0 unless observed host behavior proves it inadequate.

## 4. Provider-neutral semantic contracts

Exact serialization is deferred to implementation; these fields are required.

### `TemperatureSample`

- `sample_id`, `valid_time`, `sample_interval`, `timezone`
- `observed_or_forecast`, `temperature_unit`, normalized geometry/values
- `coverage_fraction`, `provider`, safe provider reference
- `retrieved_at`, `data_mode`, `cache_state`, validation warnings

### `NormalizationReference`

- `normalization_version`, `method`
- evaluated AOI and timestamp set
- fixed anchors or pooled-distribution metadata
- exclusions, degeneracy/contrast statistics, locked materiality rule

### `PopulationUnit`

- `population_unit_id`, geometry or representative point
- `population`, source, vintage, license, retrieved date
- transformation and assignment method, warnings

### `Facility`

- `facility_id`, name, point geometry, facility type
- source, vintage/update time, license, retrieved date
- source-provided fields including hours only when verified
- configured eligibility and reason; source facts remain distinct

### `ProximityEdge`

- `population_unit_id`, `facility_id`, `is_covered`
- method/version, radius/configuration, distance when calculated
- geometry/completeness warnings

### `AllocationResult`

- scenario ID, timestamp, `K`, selected facility IDs
- objective covered/uncovered, raw population covered
- normalization/proximity versions, reason/tie codes
- contrast/materiality state and warnings

### `BaselineResult`

- baseline type: `STATIC_NOW_SET` or `NAIVE_THERMAL`
- evaluated timestamp and selected IDs
- identical input/version references
- objective metrics and difference from optimized

### `ReplacementEvidence`

- selected and unselected facility IDs
- optimal and replacement sets/objectives
- unique and overlap demand/population
- replacement loss and tie explanation

### `DataProvenance`

- source/provider, dataset title, URL/reference, license
- source time/vintage, retrieval time, transformation version
- live/cache/stale/prepared state and redaction metadata

### `ScenarioResponse`

- atomic selected timestamp and available timestamps
- map-ready data, allocation, both baselines, metrics, evidence dictionary
- source registry, normalization reference, proximity method
- warnings, contrast/materiality result, and provenance

## 5. Proposed HTTP boundaries

- `GET /api/v1/scenarios/demo` returns locked scenario metadata and no invented environmental values.
- `POST /api/v1/analyses` accepts a known scenario/mode, validates bounds, uses cache, and submits only verified provider work.
- `GET /api/v1/analyses/{analysis_id}` returns safe status and bounded retry guidance.
- `GET /api/v1/analyses/{analysis_id}/allocation?at={timestamp}` returns one atomic optimized/baseline/evidence state for a valid sample.
- `GET /api/v1/health` reports application readiness without disclosing configuration or forcing remote calls.

The browser may not supply arbitrary provider endpoints, temperatures, population values, facility eligibility, or objective values.

## 6. Temporal strategy

Task 01A chooses between:

1. One verified range request that yields separately timestamped usable samples.
2. A bounded set of explicit timestamp requests within verified credits and latency.

In both cases:

- Normalize time to UTC internally and preserve city-local display time.
- Retain one fixed normalization reference across all samples.
- Record every evaluated timestamp.
- Exclude missing samples rather than interpolate silently.
- Require NOW and at least one future sample for P0.
- Gate multi-hour facility-hours separately.

## 7. Failure behavior

| Failure | Product behavior | Never do |
|---|---|---|
| Provider slow/pending | Bounded polling and visible progress | Block indefinitely |
| Auth/credit/rate failure | Explicit unavailable state; permitted cache if present | Substitute synthetic data |
| Ambiguous units/time | Block normalization/allocation | Guess |
| Missing sample/cell | Exclude and apply coverage gate | Treat as zero |
| Low thermal contrast | Warning and demo-gate failure | Claim meaningful reallocation |
| Population gap | Disclose/exclude under locked rule | Invent residents |
| Missing facility hours | Use priority framing without schedule claims | Invent hours |
| Malformed geometry | Isolate/reject affected record | Crash full page |
| Invalid baseline | Mark comparison unavailable | Compare inconsistent inputs |
| Optional LLM failure | No effect on P0 | Block or alter result |

## 8. Cache and prepared data

Cache normalized observations by AOI, time/range, granularity, request parameters, and adapter version. Preserve original source and retrieval times. Current/forecast TTL is set only after authenticated testing.

Prepared-demo data is allowed only after organizer/provider permission. It must be a real, redacted, provenance-preserved response captured in a permitted period, visibly labeled, and never described as live. If retention is prohibited, use live flow and an allowed recording rather than fabricated fixtures.

## 9. Security and observability

- Server-only environment variables for credentials.
- Redact headers, keys, sensitive errors, and disallowed provider identifiers.
- Validate AOI, timestamps, scenario IDs, geometry sizes, and mode.
- Log analysis ID, timing, provider status, cache outcome, data completeness, normalization version, contrast state, allocation reason, and baseline deltas without secrets.
- Track provider success/failure, latency, cache hits, excluded data, low-contrast samples, and demo-gate status.
- No personal data is required.

## 10. Deployment assumptions

- Public website/demo link is required.
- Prefer one same-origin artifact to reduce CORS and demo failures.
- One process and in-memory cache are sufficient unless the chosen host proves otherwise.
- Repository must be public and add `fortyguard` as collaborator.
- Hosting provider, deployment lifetime, portal, and media details remain unresolved.

## 11. Architecture acceptance criteria

- Provider fields remain behind the adapter.
- External source facts and prototype assumptions remain distinct.
- Identical inputs produce identical selections, baselines, metrics, and evidence.
- NOW/future use one fixed normalization reference.
- The system detects low contrast and cannot present it as material.
- Baseline inputs are identical to optimized inputs except for selection logic.
- P0 works without facility hours, network routing, an LLM, database, or queue.
- Every recommendation traces to temperature, population, facility, proximity, formula, timestamp, and provenance.
- Failure paths never generate facts.

