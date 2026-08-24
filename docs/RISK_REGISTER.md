# Risk Register

## Scale

- **Probability:** Low / Medium / High.
- **Impact:** Low / Medium / High / Critical.
- **Threat:** `Core demo`, `Submission`, `Judging`, or `Conditional/optional`.
- Reassess after Tasks 01A and 01B, after first deployed P0, and before submission.

## Risks

| ID | Risk | Probability | Impact | Mitigation | Fallback | Threat |
|---|---|---|---|---|---|---|
| R01 | Participant credentials, entitlements, credits, limits, or schemas prevent practical use of confirmed capabilities | Medium | Critical | Make authenticated behavior Task 01A; bound AOIs/timestamps; record sanitized evidence | Narrow to verified participant behavior; reject concept if essential NOW/future evidence is unavailable | Core demo |
| R02 | Provider processing latency or variability disrupts analysis/demo | High | High | Bounded polling, runtime cache, rehearsal, telemetry | Permitted labeled real prepared data or an allowed recording; otherwise unavailable | Core demo |
| R03 | No candidate city has a clean intersection of heat, facilities, population, geography, and licenses | Medium | Critical | Unranked shortlist, source matrix, early license checks, repeatable Task 01B | Expand U.S. shortlist; do not fabricate or force a city | Core demo |
| R04 | Thermal differences are too small and normalization makes trivial contrast appear meaningful | Medium | High | Fixed cross-time reference; post-inspection contrast criterion; sensitivity review | Reject timestamp/AOI/city and test another real combination | Core demo / Judging |
| R05 | Selection changes mathematically but improvement is negligible or hard to explain | Medium | High | Record materiality criterion after real inspection; compare both baselines; replacement evidence | Reject scenario and test another combination | Core demo / Judging |
| R06 | Facility source is stale, unstable, incomplete, or not reusable | Medium | High | Prefer primary sources; record update time, terms, fields, and download/API behavior | Test another official source or candidate city | Core demo / Submission |
| R07 | Population source resolution, vintage, uncertainty, or size makes results misleading or impractical | Medium | High | Compare blocks, block groups, WorldPop, and alternatives on explicit criteria | Choose the best passing source; reduce AOI without cherry-picking | Core demo / Judging |
| R08 | Facility eligibility or AOI is tuned after viewing winners | Low | High | Lock contiguous AOI and eligibility rules before optimization; retain rejection history | Re-run from a predeclared rule or reject scenario | Judging |
| R09 | Proximity proxy is mistaken for walking access or actual service reach | Medium | High | Consistent proximity/geographic-proxy language; disclose radius and limitations | Remove access wording and show pure geometric coverage | Core demo / Submission |
| R10 | Missing hours leads to unsupported opening/extension claims | Medium | High | Hours optional; separate source fields from configured eligibility; copy review | Use activation/extended-service priority wording only | Submission / Judging |
| R11 | Fixed-reference choice is unstable or overfit to the desired allocation | Medium | High | Compare reasonable formulations before locking; version formula and sensitivity evidence | Choose simpler defensible method or reject scenario | Core demo / Judging |
| R12 | Spatial joins, representative points, CRS, or AOI edges distort demand coverage | Medium | High | Validate CRS/geometry; hand tests; completeness reports; sensitivity checks | Simplify method, exclude invalid records transparently, or reject source | Core demo |
| R13 | Overlapping catchments double count demand | Low | Critical | Set-union coverage and unit tests against hand examples | Block result and fix before demo | Core demo |
| R14 | Naive baseline becomes an unfair straw man or uses inconsistent inputs | Medium | Medium | Publish exact algorithm; call it deliberately simple, not current municipal practice; enforce same inputs | Show static baseline only until comparison is corrected; scenario cannot meet DoD without both | Judging |
| R15 | Replacement evidence implies superiority when alternatives tie | Medium | Medium | Calculate replacement loss and surface deterministic tie reasons | State objective equivalence; avoid better/worse claim | Judging / Communication |
| R16 | Cached/prepared response retention or redistribution is prohibited | Medium | High | Ask before capture/commit; preserve provenance/redaction | Disable prepared mode; use live path and allowed video | Core demo / Submission |
| R17 | FortyGuard units, timestamps, range semantics, or coverage are misread | Medium | Critical | Authenticated validation; UTC normalization; preserve local metadata; block ambiguity | Exclude sample and show unavailable | Core demo |
| R18 | External-data licenses or attribution are incomplete | Medium | Critical | Source/license ledger; primary terms; pre-submission audit | Replace source or remove affected layer/claim | Submission |
| R19 | Residential population is presented as real-time occupancy, vulnerability, or medical need | Medium | High | Label source/vintage and residential limitation throughout UI/pitch | Remove interpretation and show only source-defined count | Submission / Judging |
| R20 | Product makes medical, safety, cooling-effectiveness, injuries-prevented, or lives-saved claims | Medium | Critical | Claim scan across UI/docs/video; use planning proxies only | Remove unsupported claim and re-record affected media | Submission |
| R21 | Optional network routing, mobile units, capacities, LLM, or facility-hours work delays P0 | Medium | High | Enforce scope tiers and post-deployment stop rule | Delete/disable optional path and ship P0 | Conditional/optional |
| R22 | Hosting cold start, network, tiles, DNS, or same-origin configuration breaks judging | Medium | High | Simple deployment; health checks; clean-browser/cold-start rehearsal | Permitted prepared mode or allowed recording | Core demo / Submission |
| R23 | Secrets or restricted provider data enter repository, browser, logs, screenshots, or video | Low | Critical | Server-only keys, redaction, secret scan, media review | Revoke key, remove artifact/history as permitted, rebuild | Submission |
| R24 | Remaining portal, media, deck, attribution, or pre-build rules arrive late | Medium | High | Maintain organizer questions and evidence; check official sources before build/submission | Adjust deliverables promptly without changing core | Submission |
| R25 | Solo participant cannot complete integration and deployment cleanly | Medium | High | Enumeration, one screen, one city, no LLM/network/capacity; dependency stop rules | Remove conditional/optional work and simplify presentation | Core demo |

## Five risks to review every work session

1. R01 - participant API behavior and economics.
2. R03 - complete city/data/license intersection.
3. R04 - meaningful thermal contrast under a fixed reference.
4. R05 - material and explainable gain over both baselines.
5. R25 - solo delivery and deployed-demo reliability.

## Escalation triggers

- **Stop provider implementation:** authenticated schema, units, time, or coverage remain ambiguous.
- **Stop city selection:** any essential source or license is not verified.
- **Stop scenario polish:** contrast, facility change, or material improvement fails.
- **Stop public claims:** population/access/hours meaning exceeds source evidence.
- **Stop prepared mode:** caching/retention permission is not confirmed.
- **Stop optional work:** P0 is not deployed and repeatable.
- **Stop submission:** confirmed public repository, live link, collaborator, deadline, or remaining published requirements are unsatisfied.

