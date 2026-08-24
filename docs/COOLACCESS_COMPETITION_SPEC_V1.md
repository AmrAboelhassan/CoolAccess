# CoolAccess Competition Specification v1

**Status:** Pre-build competition specification  
**Owner:** Solo participant  
**Last updated:** 2026-08-16  
**Source of truth:** This document controls product scope. Specialized documents may add detail but must not contradict it.

## 1. Project definition

CoolAccess is a deterministic municipal decision-support prototype for dynamic cooling-resource allocation. It helps a city decide which existing eligible public facilities should receive limited activation or extended-service priority as hyperlocal heat shifts across neighborhoods.

Core question:

> Given limited public cooling resources, which existing facilities should a city activate or keep open longer as hyperlocal heat shifts across neighborhoods?

The decision is intentionally narrow: one city, approximately 6-10 real candidate facilities, and a maximum of three selected facilities.

## 2. Problem and user

A municipal heat-response, resilience, emergency-management, or public-facilities team may have many potentially useful facilities but only enough staff, funding, or authority to prioritize a few. A conventional heatmap shows where heat is located; it does not account for residents, facility geography, overlapping service areas, or a hard resource limit.

Exact user story:

> As a municipal heat-response planner, I need to prioritize a limited number of existing facilities as hyperlocal heat changes, so the same constrained resources cover as much heat-weighted population demand as possible.

CoolAccess is not for residents choosing a facility and is not a general smart-city platform.

## 3. Product thesis

The judged product must prove:

```text
Same city + same facilities + same population + same K
Different hyperlocal heat pattern
-> different evidence-backed allocation
```

FortyGuard is necessary because neighborhood-scale differences and short-horizon changes can alter which combination of facilities best covers heat-weighted demand. A citywide forecast or nearest-hotspot rule does not resolve overlapping catchments, population distribution, or the fixed facility constraint.

## 4. Confirmed competition facts

Confirmed by the official hackathon FAQ/page and supplied by the participant on 2026-08-16:

- Build period: August 18-30, 2026.
- Submission deadline: August 30, 2026 at 11:59 PM GST / 12:59 PM PT.
- FortyGuard data: 2-meter street-level ambient air temperature; real and near-real-time; history from January 1, 2021; approximately 20-meter resolution; hour-by-hour data; forecasts up to 12 hours; U.S.-only hackathon coverage.
- External data is allowed, its licenses must be respected, and FortyGuard data must remain essential and central.
- Tracks: Resilient Cities & Infrastructure; Future Buildings & Energy; Industrial & Enterprise; Government & Environment; Model Designing; Agentic (API + Agentic); Data Analysis & Correlation.
- Rubric: Impact & Relevance 40%; Technical Execution 35%; Innovation 15%; Communication 10%.
- Submission: public GitHub repository, live website/demo link, and `fortyguard` added as repository collaborator.
- Ownership: participant retains ownership; FortyGuard receives a license to showcase the project.
- Project expectation: solve a real heat-related problem with genuine value that an actual client could adopt and rely on.

The exact pre-build application-code rule remains unresolved. This task creates planning documentation only.

## 5. Product principles

1. FortyGuard supplies the essential thermal evidence.
2. Deterministic code owns thermal normalization, coverage, baselines, selection, metrics, and evidence.
3. An LLM is not a P0 dependency and may never alter the recommendation.
4. Population and facility data must be real, sourced, licensed, and provenance-preserved.
5. The thermal priority is a planning weight, not a medical risk score.
6. Proximity catchments are geographic accessibility proxies, not walking-time or walking-distance claims.
7. Missing, stale, cached, or prepared data must be labeled honestly.
8. The scenario must pass both a low-contrast gate and a decision-materiality gate.
9. Optional features cannot delay a deployed, repeatable P0.

## 6. Scope

### P0 Core

- One U.S. city selected only after Tasks 01A and 01B pass.
- One contiguous AOI and approximately 6-10 real eligible facilities selected by documented rules.
- Real licensed population data at a resolution justified for the chosen city.
- FortyGuard NOW and at least one future timestamp.
- One fixed thermal-normalization reference shared across evaluated timestamps.
- Low-thermal-contrast assessment and warning/failure behavior.
- Proximity catchments using a disclosed straight-line/geodesic method.
- Fixed constraint `maximum selected facilities = 3`.
- Deterministic maximum-coverage optimization for NOW and future independently.
- Baseline A: keep the NOW allocation at the future timestamp.
- Baseline B: choose `K` facilities by naive heat-only catchment ranking.
- Map showing selected and unselected facilities, demand, proximity coverage, and selected time.
- Evidence comparing one selected facility with one unselected alternative.
- Heat-weighted demand covered/uncovered, raw population covered, selected count, and improvement versus both baselines.
- Public deployed demo and reproducible 90-150 second presentation.

Reliable facility hours are optional evidence. If absent, P0 recommends activation or extended-service priority only and makes no claim about actual opening or closing.

### P0 Conditional

Multi-hour facility-hour optimization across several forecast samples is allowed only when authenticated access, credits, latency, range semantics, temporal resolution, facility-hour evidence, and implementation results justify it. It must not block P0 Core.

### P1

- One or two mobile cooling resources using valid candidate deployment points.
- Relocation constraints or penalties.
- Actual pedestrian-network catchments and network-derived access distance.
- Additional accessibility analysis.

### P2

- Richer operating-hour budgets.
- Capacity constraints only when credible capacity data exists.
- Facility accessibility attributes.
- Multiple scenario comparison.
- Optional schema-constrained AI explanation of already-computed results.

### Non-goals

- General smart-city platform or multi-city dashboard.
- Mobile cooling units in P0.
- Medical heat-risk score, triage, alert, or safety recommendation.
- Predictions of cooling effect, injury prevention, lives saved, or public-health outcomes.
- Demand forecasting from invented occupancy or vulnerability data.
- Route guidance or walking-time claims without a network model.
- Facility operations, staffing, dispatch, reservations, or public notifications.
- Custom temperature forecasting or ML training.
- Authentication, accounts, billing, microservices, or enterprise infrastructure.

## 7. Thermal demand and accessibility

For population unit `i` and time `t`:

```text
heat_weighted_demand(i,t) = population(i) * thermal_priority(i,t)
```

The exact `thermal_priority` formula remains provisional until real distributions are inspected. The selected method must use a fixed scenario-level or pooled spatiotemporal reference across the AOI and evaluated horizon. Per-timestamp percentile recalculation is rejected for P0 because it can exaggerate trivial contrast and weaken temporal comparability.

Task 01B must define the low-contrast/materiality criterion from observed data without inventing a threshold in advance. A low-contrast state may show diagnostic data but cannot be presented as a meaningful heat-driven allocation.

`A_i,j` represents whether population unit `i` falls within facility `j`'s disclosed proximity catchment. It is a geographic accessibility proxy only.

## 8. Optimization and baselines

P0 maximizes the union of covered heat-weighted demand subject to the facility limit. With at most ten candidates and `K=3`, deterministic enumeration is the preferred implementation; the equivalent binary formulation is specified in [OPTIMIZATION_MODEL.md](OPTIMIZATION_MODEL.md).

NOW and future are optimized independently. Ties resolve by greater objective, greater raw population coverage, then lexicographically stable facility IDs.

At the future comparison timestamp:

- **Baseline A - Static allocation:** retain the NOW-selected facilities.
- **Baseline B - Naive thermal allocation:** select the `K` facilities with the highest unweighted mean thermal priority inside their proximity catchments, ignoring population and overlap.

Every comparison holds facilities, population, timestamp, normalization reference, proximity rule, and `K` constant. The optimized result must materially outperform both baselines in the final demo scenario.

## 9. Metrics and evidence

Primary outputs:

- Total and percentage of heat-weighted demand covered.
- Heat-weighted demand left uncovered.
- Raw residential population within at least one selected proximity catchment.
- Number of selected facilities and budget remaining.
- Absolute and percentage objective improvement versus both baselines.
- When P0 Conditional is enabled, population-hours and heat-weighted population-hours covered/uncovered plus facility-hours consumed.

Raw population is residential population from the selected source, not real-time occupancy. Metrics are planning/accessibility proxies and not health outcomes.

Selected-versus-unselected evidence must show the selected facility's unique coverage, overlapping coverage, the unselected alternative's corresponding values, and the objective loss from replacing the selected facility while keeping `K` fixed.

## 10. Judging strategy and likely track

Do not lock a track until the final scenario is scored against the rubric. Compare Government & Environment with Resilient Cities & Infrastructure.

| P0 capability | Impact 40% | Technical 35% | Innovation 15% | Communication 10% |
|---|---:|---:|---:|---:|
| Real constrained municipal allocation | Strong | Medium | Medium | Strong |
| FortyGuard-driven temporal reallocation | Strong | Strong | Strong | Strong |
| Population and proximity maximum coverage | Strong | Strong | Strong | Medium |
| Static and naive baseline proof | Strong | Strong | Medium | Strong |
| Inspectable replacement evidence | Medium | Strong | Medium | Strong |
| Provenance and honest failure states | Medium | Strong | Low | Medium |

Every P0 item materially supports at least one weighted category. Network routing, mobile resources, an LLM, capacity modeling, and multi-hour optimization carry more delivery risk than P0 judging value and remain gated or optional.

## 11. Demo definition

The demo must show the same city, facilities, population, proximity method, and `K=3` at NOW and a future time. A real thermal pattern changes, at least one facility selection changes, and the future optimized allocation materially beats both retaining the NOW set and the naive heat-only set. One evidence comparison must explain why a selected facility beats an unselected alternative.

The demo is not about an LLM and may not rely on unsupported hours, medical claims, or fabricated provider values.

## 12. Definition of Done

P0 Core is complete only when:

- Both Tasks 01A and 01B have passed with retained evidence.
- A public deployed URL loads in a clean browser without exposing secrets.
- The chosen city, AOI, 6-10 facilities, population source, data vintages, licenses, and transformations are documented.
- Facility eligibility is reproducible and not selected after viewing optimizer winners.
- NOW and future FortyGuard-derived states use the same fixed normalization reference.
- Thermal contrast and scenario materiality pass the post-inspection criteria recorded in the decision log.
- The map shows demand, selected/unselected facilities, proximity coverage, time, units, source mode, and attribution.
- `K=3` is visible and enforced.
- NOW and future selections differ by at least one facility for an understandable reason.
- At the future timestamp, the optimized set materially improves the defined objective over both Baseline A and Baseline B under identical inputs.
- Evidence explains at least one selected-versus-unselected replacement comparison.
- Metrics distinguish heat-weighted demand from raw residential population and contain no health-outcome claim.
- Unverified hours are not presented as facts; missing hours do not block P0.
- Provider failure produces a clear unavailable state or permitted provenance-preserved cached/prepared state, never synthetic evidence.
- P0 works without an LLM.
- Automated tests cover normalization, low contrast, spatial joins, catchments, enumeration, ties, baselines, replacement evidence, missing data, provenance, and failure paths.
- The public repository, live demo link, and `fortyguard` collaborator requirement are satisfied before the confirmed deadline.
- The 90-150 second demo is repeatable and all relative documentation links work.

## 13. Open gates

- Participant credentials, credits, endpoint costs, rate/concurrency limits, AOI limits, schemas, range semantics, latency, caching, prepared-data permission, and attribution wording.
- Final city, population source, facility source, proximity method/radius, thermal formula, contrast/materiality criterion, track, and hosting provider.
- Multiple-submission and solo-plus-team eligibility.
- Pre-build application-code permission.
- Portal-specific, video, deck, and other still-unpublished submission details.

Do not begin application implementation under this pack until separately authorized.
