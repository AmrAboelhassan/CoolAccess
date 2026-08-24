# Decision Log

## Status definitions

- **Accepted:** controls the current specification and future implementation plan.
- **Provisional:** preferred or candidate approach pending Tasks 01A/01B or build evidence.
- **Rejected:** considered and deliberately excluded.
- **Unresolved:** cannot be decided without external facts or observed data.
- **Revisited:** replaced by a newer dated entry; preserve history and link the change.

When a decision changes, add a new dated row rather than rewriting history misleadingly.

## Decisions

| Date | Decision | Status | Reason/evidence | Revisit trigger |
|---|---|---|---|---|
| 2026-08-16 | Working name is CoolAccess; positioning is Dynamic Cooling Resource Allocation | Accepted | Participant brief | Material naming conflict or final branding decision |
| 2026-08-16 | Primary user is one municipal heat-response/resilience/emergency-management/public-facilities team | Accepted | One buyer protects product clarity and Impact score | Direct user evidence supports a narrower equivalent role |
| 2026-08-16 | Core decision is which eligible existing facilities receive limited activation or extended-service priority | Accepted | Converts heat evidence into a constrained municipal action | Never for competition P0 unless concept becomes infeasible |
| 2026-08-16 | P0 uses one U.S. city, approximately 6-10 candidates, and `K=3` | Accepted | Understandable and solo-safe | Task 01B shows a small justified candidate-count deviation is necessary |
| 2026-08-16 | No city is preferred before Tasks 01A/01B | Accepted | Full data intersection and scenario materiality control selection | A city passes the documented gate |
| 2026-08-16 | Initial unranked shortlist includes DC, Chicago, NYC, Phoenix, and Los Angeles/County | Provisional | Primary-source candidate evidence; not a ranking | Research adds/removes candidates with recorded evidence |
| 2026-08-16 | Population candidates include Census blocks, block groups, WorldPop, and other licensed sources | Provisional | Resolution, integration, license, size, and scenario usefulness require comparison | Task 01B selects a source |
| 2026-08-16 | AOI and eligibility rules must be fixed before viewing optimizer winners | Accepted | Prevents cherry-picking | Never; implementation may refine the audit mechanism |
| 2026-08-16 | Exact thermal-priority formula remains provisional through Tasks 01A/01B | Accepted | Real distributions must control calibration | Task 01B locks and versions the formula |
| 2026-08-16 | NOW/future must share one scenario-level or pooled spatiotemporal normalization reference | Accepted | Enables comparable temporal states | Verified evidence supports a more comparable documented method |
| 2026-08-16 | Independent per-timestamp percentile normalization is not the final P0 method | Rejected | Can exaggerate trivial differences and destabilize comparison | Only a fundamentally different use case with explicit limitations |
| 2026-08-16 | Raw Celsius is not an unexplained health-risk multiplier | Rejected | Unsupported medical interpretation | Never for this competition version |
| 2026-08-16 | Low-contrast and materiality criteria are set after observing real data, not invented now | Accepted | Avoids arbitrary thresholds and false significance | Task 01B records the criteria without erasing this decision |
| 2026-08-16 | P0 accessibility is a geodesic/straight-line proximity catchment | Provisional | Solo-safe geographic proxy | Task 01B selects radius/method; P1 may add a network model |
| 2026-08-16 | P0 must not call proximity walking time or walking distance | Accepted | No network model exists | A tested network model is implemented later |
| 2026-08-16 | Deterministic enumeration owns allocation | Accepted | At most 120 three-facility combinations for ten candidates; transparent and testable | Candidate scale expands beyond simple enumeration |
| 2026-08-16 | Optimize NOW and future independently for P0 | Accepted | Clearest solo-safe proof of dynamic allocation | P0 Conditional multi-hour gate passes |
| 2026-08-16 | Baseline A retains the NOW-selected set at future | Accepted | Measures value of adapting | Never for P0 comparison |
| 2026-08-16 | Baseline B selects top `K` by unweighted mean catchment thermal priority, ignoring population and overlap | Accepted | Transparent heat-only comparison | Evidence shows implementation ambiguity requiring a dated clarification |
| 2026-08-16 | Selected-versus-unselected evidence uses a fixed-`K` replacement test | Accepted | Directly explains marginal decision value | A clearer deterministic equivalent is proven |
| 2026-08-16 | Facility hours are useful but not a P0 dependency | Accepted | Source availability is uncertain; priority decision remains valid without schedule claims | Verified city data makes hours reliable and valuable without added risk |
| 2026-08-16 | Multi-hour facility-hour optimization is P0 Conditional | Accepted | Requires verified temporal/API/hour economics | Conditional gate result |
| 2026-08-16 | Mobile cooling resources and network routing are P1 | Accepted | They add data and optimization risk | Deployed repeatable P0 exists |
| 2026-08-16 | Capacity, richer hours, scenario comparison, and optional AI explanation are P2 | Accepted | They are not needed for the money shot | P0/P1 complete early with verified data |
| 2026-08-16 | LLM is absent from P0 and never owns recommendations | Accepted | Optimizer must remain deterministic and standalone | Never for recommendation ownership |
| 2026-08-16 | Metrics are planning/geographic-accessibility proxies, not medical outcomes | Accepted | Evidence does not validate health impact | Validated study and expanded product scope |
| 2026-08-16 | Likely tracks are Government & Environment and Resilient Cities & Infrastructure; final track is not locked | Provisional | Must compare final scenario against official rubric | Scenario and submission form are final |
| 2026-08-16 | Build period is August 18-30, 2026 | Accepted | Official hackathon page, confirmed by participant | Official correction |
| 2026-08-16 | Submission deadline is August 30, 2026 at 11:59 PM GST / 12:59 PM PT | Accepted | Official hackathon page, confirmed by participant | Official correction |
| 2026-08-16 | Public GitHub repository, live website/demo, and `fortyguard` collaborator are required | Accepted | Official FAQ supplied by participant | Official correction |
| 2026-08-16 | Participant retains ownership; FortyGuard receives a showcase license | Accepted | Official FAQ supplied by participant | Official correction |
| 2026-08-16 | External data is allowed with respected licenses and central FortyGuard use | Accepted | Official FAQ supplied by participant | Official correction |
| 2026-08-17 | Implement provider-independent deterministic portions of Tasks 06, 07, and 10 before Tasks 01A/01B | Accepted | Participant approved a bounded Phase 1 foundation that consumes injected normalized priorities and accessibility relations without locking real data decisions | Reconcile with the normal dependency path after Tasks 01A/01B; do not mark the full downstream tasks complete |
| 2026-08-17 | Participant authorization permits this Phase 1 implementation while organizer pre-build-rule compliance remains unresolved | Accepted | Explicit participant instruction authorizes repository work but cannot establish an external competition ruling | Organizer clarification |
| 2026-08-17 | Phase 1 uses Python 3.11, a `src` layout, Pydantic v2, setuptools, pytest, Ruff, and mypy; FastAPI is deferred | Accepted | Minimal typed deterministic core needs no HTTP runtime yet | Add an HTTP layer only when a concrete API task requires it |
| 2026-08-17 | The optimizer consumes finite normalized thermal priority in inclusive `[0,1]` and never derives it | Accepted | Keeps the allocation layer independent of the unresolved provider thermal model | Task 01B versions the upstream normalization/reference model without changing optimizer logic |
| 2026-08-17 | Authoritative demand, coverage, objectives, and comparator deltas use canonical finite `Decimal`; naive mean ranking compares exact sum/count ratios | Accepted | Prevents binary-float and ambient-context rounding from changing deterministic decisions | Candidate scale or input-number representation changes materially |
| 2026-08-17 | Canonical JSON and SHA-256 fingerprints identify deterministic inputs and outputs | Accepted | Stable ordering and normalized decimal/time serialization make repeatability auditable | Contract-version migration requires a versioned canonicalization change |
| 2026-08-17 | Missing and explicit-false accessibility relationships both mean `A[i,j] = false`; only validated true relationships cover demand | Accepted | Pure edge semantics avoid locking geometry, radius, routes, or coordinates | Task 01B/05 defines and versions the real proximity construction method |
| 2026-08-17 | `K` is an unchanged maximum budget; validate only `K > 0`, allow `K` above eligible count, and enumerate sizes `0..min(K, eligible_count)` | Accepted | Scenario quality and domain validity are separate; unused capacity must remain honest | Never for Phase 1 semantics |
| 2026-08-17 | Allocation comparator order is heat-weighted demand, covered residential population, fewer facilities, then lexicographically smaller canonical facility IDs | Accepted | Exact coverage ties must not consume resources with zero marginal value | Never unless the product objective itself changes through a dated decision |
| 2026-08-17 | Structural fingerprints exclude state/time, thermal priorities, derived demand, and thermal-state provenance; full-state fingerprints add them | Accepted | Static NOW selections must remain comparable at a legitimate FUTURE thermal state while invariant decision structure stays fixed | Version if invariant domain inputs change |
| 2026-08-17 | Static Baseline re-evaluates the prior canonical set at a structurally compatible target state and preserves source-state fingerprint/provenance | Accepted | Prevents reuse of stale coverage values and identifies the exact source allocation state | Never for P0 Static comparison |
| 2026-08-17 | Phase 1 Naive Thermal scoring averages accessible `PopulationCell.thermal_priority` values equally and records exact sum/count ranking evidence | Provisional | No separate real thermal-cell layer exists; unequal real population geometries may make equal-cell averaging unsuitable | Mandatory Task 01B review after population representation and thermal-to-population mapping are known |
| 2026-08-17 | Fixed-cardinality ReplacementEvidence answers why selected `S` wins over unselected `U` using objective, population, then stable IDs | Accepted | A replacement preferred by any applicable comparator criterion proves the purported optimum internally inconsistent | Revisit only if the allocation comparator changes |
| 2026-08-17 | MarginalAdditionEvidence separately explains every eligible unselected facility when budget remains | Accepted | Swap evidence cannot explain why a zero-marginal facility was not simply added; positive objective or population marginal value is an internal-consistency failure | Revisit only if maximum-budget semantics change |
| 2026-08-17 | Percentages use 0-100 units, 12 decimal places with half-even rounding, exact numerator/denominator fields, and explicit not-applicable zero denominators | Accepted | Avoids infinity, fabricated percentages, and selection effects from display rounding | Presentation requirements change without changing authoritative inputs |

## Unresolved decisions

Do not resolve without evidence:

- Whether one participant may submit two projects or participate in both solo and team submissions.
- Whether competition-specific application code/boilerplate may be created before August 18.
- Credentials, credits, endpoint costs, rate/concurrency/AOI limits, schemas, range semantics, latency, caching, prepared data, and attribution wording.
- Final city, AOI, facility/population/geographic sources, source licenses, and facility eligibility.
- Thermal formula/reference, contrast/materiality criterion, population-assignment method, proximity radius, and representative geometry rule.
- Final track, hosting provider, deployment topology, and remaining portal/media/deck requirements.
