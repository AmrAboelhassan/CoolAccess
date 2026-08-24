# CoolAccess Hackathon Build Plan

## Operating rules

- This document remains the dependency-ordered build plan. A narrowly scoped provider-independent Phase 1 foundation was implemented on 2026-08-17; the status notes below do not complete the gated real-data tasks.
- Build period is August 18-30, 2026. Submission deadline is August 30, 2026 at 11:59 PM GST / 12:59 PM PT.
- Whether competition-specific application code may be written before the build period remains unresolved.
- Tasks 01A and 01B are hard gates. Lock no city, data source, thermal formula, proximity radius, or scenario before both pass.
- Complete and deploy P0 Core before P1/P2. P0 Conditional must never destabilize core.
- Use relative complexity `S`, `M`, or `L`; do not estimate hours.
- Preserve deterministic operation without an LLM and never present synthetic provider data as real.

## Dependency path

```text
01A API/competition capability verification
  +
01B city/data feasibility spike
  -> 02 provider adapter
  -> 03 external-data normalization
  -> 04 spatial demand + fixed thermal reference
  -> 05 proximity catchments
  -> 06 deterministic optimizer
  -> 07 static + naive baselines
  -> 08 interactive map
  -> 09 NOW/future comparison
  -> 10 evidence and replacement panel
  -> 11 reliability/cache
  -> 12 deployment
  -> 13 demo/submission polish

01A + 01B + stable 04-10 + verified hours/temporal economics
  -> 09C multi-hour facility-hours (P0 Conditional, L)
```

## Task 01A - Competition/API capability verification

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Participant credentials and authorization to perform the spike

### Goal

Verify how confirmed FortyGuard capabilities behave under participant access without re-questioning their conceptual existence.

### Inputs

- Participant credentials and portal.
- Confirmed U.S. coverage, hour-by-hour data, and forecast horizon up to 12 hours.
- Official API documentation and organizer responses.
- Bounded candidate AOIs from Task 01B.

### Outputs

- Capability matrix: `verified`, `unavailable`, or `unknown` under participant credentials.
- Sanitized request/result/status/error shapes.
- Credit, rate, concurrency, AOI, granularity, latency, and timestamp observations.
- Range-semantics decision versus bounded discrete requests.
- Cache/prepared-data/attribution answers when available.
- P0 and P0 Conditional pass/fail evidence.

### Acceptance criteria

- Authentication, submission, polling, terminal states, and errors are observed.
- Exact units, time semantics, valid times, geometry, coverage, and authoritative temperature fields are documented.
- Practical NOW and future samples are available for at least one candidate AOI.
- Credits/costs, rate/concurrency, AOI/granularity behavior, latency, and range shape are recorded or explicitly unknown.
- Multi-hour work remains disabled unless independently usable samples and economics are proven.
- No unverified schema becomes a provider contract.

## Task 01B - City/data feasibility spike

**Priority:** P0  
**Complexity:** L  
**Dependencies:** Task 01A access; candidate-source research

### Goal

Select a city and scenario only after the complete data intersection produces a material, explainable decision.

### Inputs

- Unranked candidate shortlist and scorecard.
- Authenticated FortyGuard samples.
- Facility, population, geographic, and license candidates.
- Candidate fixed-reference and proximity methods.

### Outputs

- Completed city scorecards and rejection reasons.
- Selected city/AOI only when one passes.
- Locked facility eligibility rule and approximately 6-10 candidates.
- Selected population/facility/geographic sources and license ledger.
- Selected thermal formula/reference and proximity method/radius.
- Recorded low-contrast and decision-materiality criteria based on observed distributions.
- Reproducible NOW/future scenario with optimized, static, and naive results.

### Acceptance criteria

- No city or population source is treated as preferred before comparison.
- AOI/eligibility rules are fixed before inspecting optimizer winners.
- The selected data sources are licensed, usable, reproducible, and appropriately sized.
- One fixed thermal reference supports NOW/future comparison.
- Real thermal divergence is understandable and not trivial under the recorded rule.
- At least one facility changes and improvement over both baselines is non-trivial and explainable.
- If no city passes, the task remains failed and another combination is tested.

## Task 02 - Provider adapter

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Tasks 01A and 01B

### Goal

Isolate verified FortyGuard authentication, request, polling, validation, normalization, and error behavior.

### Inputs

- Verified schemas and temporal strategy.
- Temperature/provenance contracts.
- Locked AOI and timestamps.

### Outputs

- Submit/status/result operations.
- Strict result/geometry validation.
- Provider-neutral samples and typed failures.
- Redacted logging and synthetic test-only fixtures.

### Acceptance criteria

- Pending, complete, failed, auth, rate-limit, timeout, malformed, and partial states are handled.
- Units, valid/source/retrieval times, forecast status, and geometry are preserved.
- Provider fields do not leak into demand/optimizer/UI layers.
- Missing temperatures are never inferred.
- Secrets never reach logs or clients.

## Task 03 - External-data normalization

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Task 01B

### Goal

Produce validated, licensed, provider-neutral facility, population, AOI, and geographic records.

### Inputs

- Locked sources, versions, licenses, and transformations.
- Facility eligibility rules.

### Outputs

- Normalized population units and facilities.
- Source/provenance registry.
- Coverage, duplicate, geometry, and missing-field reports.

### Acceptance criteria

- Counts, totals, coordinate systems, IDs, and AOI filters reconcile to sources.
- Every transformation is documented and reproducible.
- Source facts remain distinct from configured eligibility.
- Missing hours do not block otherwise valid facilities or generate schedule claims.
- License and attribution metadata are complete.

## Task 04 - Spatial demand and fixed thermal reference

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Tasks 02 and 03

### Goal

Assign temperature to population units, build one fixed reference, calculate thermal planning priority, and enforce contrast rules.

### Inputs

- Normalized temperature samples and population units.
- Locked spatial-assignment and thermal-normalization decisions.

### Outputs

- Population-temperature observations by time.
- Versioned normalization reference.
- `P_i`, `H_i,t`, `W_i,t`, coverage/completeness, and contrast results.

### Acceptance criteria

- NOW/future reuse an identical normalization reference.
- Per-timestamp percentile recalculation is absent from final behavior.
- Missing/ambiguous data blocks or reduces results under the locked rule.
- Low contrast is warned and cannot be demo-ready.
- Thermal priority is labeled a planning weight, not health risk.

## Task 05 - Proximity catchments

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Task 03

### Goal

Create the disclosed geographic accessibility proxy and `A_i,j` relationships.

### Inputs

- Facilities, population geometry, AOI, locked radius/method.

### Outputs

- Facility catchments and population-facility edges.
- Completeness, edge-effect, and geometry warnings.

### Acceptance criteria

- Known boundary cases and hand-calculated distances pass.
- Population is not double counted in union coverage.
- Method/radius/version appear in evidence.
- UI/API terminology says proximity/geographic proxy, never walking time/distance.
- Invalid geometry is isolated without fabricated edges.

## Task 06 - Deterministic optimizer

**Phase 1 status (2026-08-17):** Provider-independent exhaustive enumeration, exact union coverage, maximum-budget handling, canonical fingerprints, and deterministic evidence fields are implemented and tested. Real normalized demand and real accessibility inputs remain blocked by Tasks 01A/01B and Tasks 04/05.

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Tasks 04 and 05

### Goal

Select the maximum-coverage facility set for each timestamp under `K=3`.

### Inputs

- Heat-weighted demand and proximity edges.
- Eligible facilities and `K`.

### Outputs

- Enumerated allocation, objective, uncovered demand, raw population coverage, and tie reasons.

### Acceptance criteria

- Results match hand-calculated examples and equivalent formulation checks.
- Union coverage contains no duplicate demand.
- `K` and eligibility are always respected.
- Ties follow objective, raw population, fewer selected facilities, then stable facility IDs.
- Identical input always returns identical output.
- No LLM or facility-hours dependency exists.

## Task 07 - Static and naive baselines

**Phase 1 status (2026-08-17):** Provider-independent Static and Naive Thermal algorithms, fair-comparison fingerprints, zero-denominator handling, and synthetic tests are implemented. The naive equal-`PopulationCell` observation unit is a Phase 1 assumption that Task 01B must revisit; no real scenario or materiality result exists.

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Task 06

### Goal

Prove value against retaining NOW and selecting facilities by heat alone.

### Inputs

- NOW/future normalized inputs and optimized allocations.

### Outputs

- Static NOW-set evaluation at future.
- Naive mean-catchment-thermal top-`K` allocation.
- Comparable metrics and gains.

### Acceptance criteria

- All approaches use identical timestamp, facilities, population, reference, proximity, and `K`.
- Static uses exactly the NOW-selected set.
- Naive ignores population and overlap exactly as documented.
- Zero denominators return `not applicable`.
- Optimized objective is not below either valid baseline.
- Locked demo meets the recorded materiality criterion against both.

## Task 08 - Interactive map

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Tasks 03-07

### Goal

Connect thermal demand, candidates, selections, proximity coverage, and resource constraint on one map.

### Inputs

- Map-ready scenario and allocation contracts.

### Outputs

- Thermal/demand layers, facility states, catchments, legend, attribution, selection synchronization, and clean loading/error states.

### Acceptance criteria

- Approximately 6-10 candidates and selected/unselected state are legible on a laptop.
- Time, units, fixed scale, `K`, source mode, and attribution remain visible.
- Color is not the only state cue.
- Missing geometry does not crash the entire screen.
- No walking or unsupported hours claim appears.

## Task 09 - NOW/future comparison

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Tasks 04-08

### Goal

Show a coherent allocation change under one fixed reference and constant non-thermal inputs.

### Inputs

- Valid samples and all three allocation results.

### Outputs

- NOW/future controls, atomic view model, change indicators, and scenario-constant disclosure.

### Acceptance criteria

- Map, allocation, baselines, metrics, and evidence always share one timestamp.
- NOW/future use the same facilities, population, proximity rule, `K`, and thermal reference.
- Unsupported timestamps cannot be selected.
- Low contrast is visible and cannot masquerade as a money shot.
- The locked scenario visibly changes at least one facility.

## Task 09C - Multi-hour facility-hours

**Priority:** P0 Conditional  
**Complexity:** L  
**Dependencies:** Passed Tasks 01A/01B and stable Tasks 04-10

### Goal

Optimize a verified facility-hour budget across multiple honest forecast samples without weakening core.

### Acceptance criteria

- Credits, latency, range semantics, sample coverage, and facility-hour inputs are verified.
- Sampled temporal coverage is explicit and missing periods are not interpolated silently.
- Facility-hours consumed and population-hours covered/uncovered are deterministic.
- The feature is stopped immediately if it threatens P0 deployment or clarity.

## Task 10 - Evidence and replacement panel

**Phase 1 status (2026-08-17):** Structured replacement, unique/overlap, and unused-budget marginal-addition evidence are implemented and tested. The frontend panel, real provenance presentation, and demo integration remain incomplete.

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Tasks 06-09

### Goal

Make one selected-versus-unselected decision auditable within the demo.

### Inputs

- Allocation, baselines, replacement calculations, source registry, and warnings.

### Outputs

- Evidence drawer with unique/overlap demand, replacement loss, inputs, method versions, and provenance.

### Acceptance criteria

- All numbers come from deterministic response fields.
- Equivalent replacements explain the tie instead of claiming superiority.
- Missing values display unavailable, not zero.
- The presenter can explain the decision within 30 seconds.
- Evidence separates source facts, configuration, and derived values.

## Task 11 - Reliability and cache

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Complete P0 analysis flow

### Goal

Make the judged path predictable under latency, quotas, missing data, and network/provider failure.

### Outputs

- Bounded polling/retry, request budget, analysis deadline, cache, structured errors, telemetry, and optional permitted prepared mode.

### Acceptance criteria

- No retry loop is unbounded.
- Cache keys include AOI/time/parameters and adapter version.
- Cache/prepared states preserve original source time and visible labeling.
- Prepared data is real, redacted, provenance-preserved, and explicitly permitted.
- Provider, partial-data, low-contrast, geometry, and baseline failures have tested clean states.

## Task 12 - Deployment

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Stable Tasks 02-11 and confirmed hosting details

### Goal

Publish a reproducible public demo with minimal operational surface.

### Acceptance criteria

- Public URL works signed out and from a clean browser.
- Secrets remain server-side and absent from assets/logs/responses.
- Map assets, attribution, health check, and outbound provider access work.
- Cold/warm behavior fits the demo.
- Deployment is reproducible from repository instructions.

## Task 13 - Demo and submission polish

**Priority:** P0  
**Complexity:** M  
**Dependencies:** Task 12; confirmed remaining portal/media rules

### Goal

Deliver a clear, credible, rule-compliant entry by the confirmed deadline.

### Acceptance criteria

- The 90-150 second script repeatedly shows a material change and both baselines.
- Claims remain planning/accessibility proxies.
- Repository is public, live link works, and `fortyguard` is a collaborator.
- Source mode, timestamps, limitations, licenses, and attribution are visible.
- Final checks find no secrets, broken links, unsupported claims, or optional dependency.
- Submission is completed before August 30, 2026 at 11:59 PM GST / 12:59 PM PT and confirmation is retained.

## Stop rules

- Stop adapter work when authenticated schemas/semantics remain ambiguous.
- Stop city lock when the data/license intersection is incomplete.
- Stop scenario polish when contrast or allocation materiality fails.
- Stop schedule wording when verified hours are absent.
- Stop prepared-data work when retention permission is absent.
- Stop conditional/optional work until deployed P0 is repeatable.
