# Submission Checklist

Use authoritative published requirements and retain evidence beside completed items. A confirmed requirement is not checked until the project actually satisfies it.

## Confirmed competition facts

- [x] Build period recorded: August 18-30, 2026.
- [x] Submission deadline recorded: August 30, 2026 at 11:59 PM GST / 12:59 PM PT.
- [x] Judging rubric recorded: Impact & Relevance 40%, Technical Execution 35%, Innovation 15%, Communication 10%.
- [x] Seven official tracks recorded.
- [x] External datasets allowed with respected licenses and central FortyGuard use.
- [x] Participant ownership and FortyGuard showcase license recorded.
- [x] Required public repository, live website/demo link, and `fortyguard` collaborator recorded.

## Eligibility and unresolved rules

- [ ] Multiple-project eligibility confirmed.
- [ ] Solo-plus-team eligibility confirmed.
- [ ] Pre-build application-code rule confirmed without inference.
- [ ] AI-assistant use/disclosure rules satisfied.
- [ ] Repository creation/commit-history rules satisfied.
- [ ] Remaining portal, media, deck, license, and artifact requirements confirmed.

## Tasks 01A and 01B evidence

- [ ] Authenticated participant schemas, units, timestamps, range semantics, statuses, and errors recorded.
- [ ] Credits/costs, rate/concurrency, AOI/granularity, and latency recorded or explicitly unknown.
- [ ] Cache, retained-response, prepared-data, and attribution permissions confirmed.
- [ ] Candidate cities evaluated without a preferred city.
- [ ] Population alternatives compared for resolution, integration, license, size, and scenario usefulness.
- [ ] Final city/AOI passes the complete data/license gate.
- [ ] AOI and facility-eligibility rules were fixed before optimizer winners were inspected.
- [ ] Thermal formula/reference and proximity method/radius are versioned.
- [ ] Low-contrast and materiality criteria were recorded after real distribution inspection.

## Product P0 Core

- [ ] One selected city and timezone are visible.
- [ ] Approximately 6-10 real eligible facilities and source are visible.
- [ ] `Maximum selected facilities = 3` is visible and enforced.
- [ ] Licensed residential population source, vintage, and limitations are visible.
- [ ] NOW and at least one future FortyGuard sample are available.
- [ ] NOW/future use one fixed thermal-normalization reference.
- [ ] Thermal contrast passes the locked criterion; low contrast has an honest warning state.
- [ ] Proximity catchments use the locked geographic proxy and never claim walking time/distance.
- [ ] NOW and future are optimized independently and deterministically.
- [ ] At least one facility selection changes for an understandable real-data reason.
- [ ] Static baseline keeps the exact NOW-selected set at future.
- [ ] Naive baseline selects top `K` by unweighted mean catchment thermal priority and ignores population/overlap.
- [ ] All three allocations use identical facilities, population, timestamp, reference, proximity, and `K`.
- [ ] Optimized allocation materially improves the objective over both baselines.
- [ ] Replacement evidence compares a selected facility with an unselected alternative.
- [ ] Map distinguishes selected/unselected facilities without color alone.
- [ ] Heat-weighted demand covered/uncovered, raw residential population covered, selected count, and baseline gains are visible.
- [ ] Facility hours are displayed only when source-verified; missing hours do not block P0.
- [ ] P0 has no LLM dependency.

## P0 Conditional

- [ ] Multi-hour feature is absent unless credentials, credits, latency, range semantics, sample coverage, facility hours, and implementation evidence pass the gate.
- [ ] Facility-hour budget and consumed hours are deterministic and visible.
- [ ] Population-hours metrics and sampled limitations are explicit.
- [ ] Conditional work did not delay or destabilize P0 Core.

## Claims and evidence

- [ ] Thermal priority is labeled a planning weight, not health risk.
- [ ] Residential population is not called occupancy, vulnerability, attendance, or medical need.
- [ ] Proximity is not called walking access.
- [ ] No opening/closing/extended-hour claim lacks source support.
- [ ] No degrees-cooled, injuries-prevented, lives-saved, medical-safety, or guaranteed-outcome claim appears.
- [ ] Baseline B is described as deliberately simple, not as current municipal practice.
- [ ] Source facts, configured assumptions, and derived results are distinguishable.

## Data, licenses, and attribution

- [ ] FortyGuard attribution matches confirmed wording.
- [ ] Facility, population, boundary, map, and optional OSM licenses/terms are recorded.
- [ ] Every retained dataset has source URL, version/date, retrieval date, transformations, and limitations.
- [ ] Map/tile attribution is visible.
- [ ] Dependency, icon, font, image, logo, and media licenses are reviewed.
- [ ] Prepared provider data is absent unless retention is permitted.
- [ ] Any prepared data is real, redacted, checksummed, provenance-preserved, and persistently labeled.

## Reliability and tests

- [ ] Provider pending, failure, timeout, rate-limit, credit, malformed, and partial states are tested.
- [ ] Ambiguous units/timestamps block allocation.
- [ ] Missing temperature cannot become zero or synthetic.
- [ ] Fixed-reference, low-contrast, geometry, proximity, enumeration, tie, baseline, metric, and replacement tests pass.
- [ ] Union coverage never double counts population demand.
- [ ] Identical input returns identical results.
- [ ] Cache preserves source timestamp and mode.
- [ ] Live and permitted fallback paths are rehearsed.

## Code and repository

- [ ] Public GitHub repository is published.
- [ ] `fortyguard` is added as a repository collaborator.
- [ ] README includes problem, buyer, architecture, setup, deployment, demo, limitations, sources, licenses, and attribution.
- [ ] Relative documentation links work.
- [ ] Clean-clone install/run/build/test instructions pass.
- [ ] Required manifests and lockfiles are committed.
- [ ] No unused P1/P2 scaffolding obscures core.
- [ ] Secret scan passes current files and history.
- [ ] Raw provider credentials/responses are absent unless explicitly permitted and sanitized.

## Deployment

- [ ] Live website/demo link is public and works signed out.
- [ ] Hosting and required availability duration comply with confirmed rules.
- [ ] Health check, same-origin/API path, map assets, and outbound provider access work.
- [ ] Cold start and clean-browser behavior fit the demo.
- [ ] Secrets remain server-side and absent from assets, storage, logs, and responses.
- [ ] Honest provider-unavailable and permitted prepared-data states work in production.

## Demo and communication

- [ ] 90-150 second script fits any final official media limit.
- [ ] First 15 seconds establish user, candidates, and `K=3`.
- [ ] NOW and future use the same city, facilities, population, proximity, reference, and budget.
- [ ] A facility visibly changes because the real thermal pattern changes.
- [ ] Static and naive baselines are both shown at future.
- [ ] One replacement comparison is explained within 30 seconds.
- [ ] Source mode, timestamps, units, limitations, and attribution are legible.
- [ ] Claims are limited to scenario-specific planning/accessibility proxies.
- [ ] Final video/deck/screenshots meet any subsequently confirmed rules.

## Final smoke test and submission

- [ ] Run signed out with browser cache disabled.
- [ ] Verify city, time, mode, freshness, fixed legend, `K`, sources, and attribution.
- [ ] Verify every facility, timestamp, allocation, baseline, metric, and evidence link.
- [ ] Force low contrast and provider failure; verify honest states.
- [ ] Inspect console/network for errors and secrets.
- [ ] Verify public repository, collaborator, live URL, and every portal/media link.
- [ ] Submit before **August 30, 2026 at 11:59 PM GST / 12:59 PM PT**.
- [ ] Retain submission confirmation.
