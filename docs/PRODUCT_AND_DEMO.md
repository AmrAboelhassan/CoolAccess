# Product and Demo

> **Archived planning guide:** Current UI wording, benchmark values, and behavior are defined by
> the running application and `README.md`. “Future” below means a later prepared historical
> timestamp, not forecast weather. At 20:00 the naive hottest-catchment baseline ties the dynamic
> optimum; only the static retained-set comparison has a positive gain.

## Product objective

CoolAccess helps a municipal heat-response team prioritize a maximum of three existing eligible facilities as hyperlocal heat changes, maximizing covered heat-weighted population demand without adding resources.

Exact user story:

> As a municipal heat-response planner, I need to prioritize a limited number of existing facilities as hyperlocal heat shifts, so the same constrained resources cover as much heat-weighted population demand as possible.

The central visual is not another heatmap. It is a changed municipal allocation with a defensible comparison against doing nothing and following heat alone.

## Scenario contract

The final scenario is locked only after Tasks 01A and 01B pass. It must contain:

- One U.S. city and one contiguous AOI.
- Approximately 6-10 real facilities meeting predefined eligibility rules.
- Real licensed residential population data.
- FortyGuard NOW and at least one future sample.
- One fixed thermal-normalization reference shared across the evaluated horizon.
- A maximum of three selected facilities.
- One disclosed proximity catchment method and radius.
- A passed low-contrast and materiality gate.
- A visible, understandable selection change and material improvement over both baselines.

The scenario does not require verified operating hours. When hours or activation fields are unavailable, copy says `activation or extended-service priority`, not `open`, `close`, or `extend until`.

## Core comparisons

At the future timestamp, the interface compares three allocations under identical inputs:

1. **Optimized:** maximum union coverage of population-weighted thermal priority.
2. **Static baseline:** keep the NOW-selected facilities unchanged.
3. **Naive thermal baseline:** choose the three facilities with the hottest mean proximity catchments, ignoring population and overlapping coverage.

This directly answers two objections:

- `Why not keep the existing plan?` Because the heat distribution changed and the new allocation covers materially more heat-weighted demand.
- `Why not open the center nearest the hottest place?` Because residents, catchment overlap, and the hard facility limit change the best combination.

## Single-screen flow

### State 1 - Municipal decision

Visible:

- CoolAccess name and Dynamic Cooling Resource Allocation positioning.
- City, local timezone, selected timestamp, source mode, and freshness.
- Fixed resource badge: `Maximum selected facilities: 3`.
- Candidate count and eligibility statement.
- Map with all candidate facilities and demand geography.

Judge takeaway: this is a resource-allocation decision for one municipal team.

### State 2 - NOW allocation

- NOW thermal pattern and fixed normalization legend.
- Selected facilities are visually distinct from unselected facilities by icon, label, and color.
- Coverage cards show heat-weighted demand covered/uncovered and raw residential population within selected proximity catchments.
- The selected set is saved as Baseline A for the future comparison.

Judge takeaway: the city has a defensible allocation under current conditions.

### State 3 - Future shift

- Select a verified future timestamp.
- Map, demand weights, allocation, metrics, and evidence update atomically.
- At least one facility changes while city, facilities, population, proximity rule, and `K` remain fixed.
- The fixed thermal reference remains visible so NOW and future are comparable.

Judge takeaway: hyperlocal heat changed differently across neighborhoods, changing the best constrained allocation.

### State 4 - Baseline proof

- Show optimized, static, and naive thermal allocations side by side in a compact comparison panel.
- Display the same future timestamp and `K=3` for all three.
- Show objective covered, objective uncovered, and absolute/percentage improvement.
- Include a plain-language explanation of why heat-only selection loses value through population mismatch or overlapping catchments.

Judge takeaway: the optimizer adds decision value beyond a heatmap and beyond keeping the old plan.

### State 5 - Replacement evidence

- Open a selected facility.
- Compare it with one unselected alternative.
- Show unique heat-weighted demand covered, overlapping coverage, total set objective, replacement-set objective, and objective loss.
- Show population source, temperature source time, fixed normalization reference, proximity method, facility source, and warnings.

Judge takeaway: the recommendation is deterministic, inspectable, and not an LLM opinion.

## Recommended layout

```text
+---------------------------------------------------------------------+
| CoolAccess | City | LIVE/PREPARED | timestamp | K = 3               |
+-------------------------------------------+-------------------------+
|                                           | Selected allocation     |
| Interactive map                           | 1. Facility             |
| - fixed-scale thermal layer               | 2. Facility             |
| - population/demand geography             | 3. Facility             |
| - selected/unselected facilities          |                         |
| - proximity coverage                      | Coverage metrics        |
+-------------------------------------------+-------------------------+
| NOW [selected] ---- future timestamp                                 |
+---------------------------------------------------------------------+
| Optimized vs Static vs Naive thermal baseline                        |
+---------------------------------------------------------------------+
| Selected-vs-unselected evidence drawer                               |
+---------------------------------------------------------------------+
```

Desktop is the judged experience. Common laptop sizes must remain usable, and color cannot be the only state indicator.

## Map and temporal behavior

- NOW is explicitly labeled.
- Future controls show local time and observed/forecast status.
- One atomic response drives the map, facility list, metrics, baselines, and evidence.
- The legend uses the same fixed thermal reference at every timestamp.
- Low contrast shows a prominent warning and disables claims of meaningful heat-driven reallocation.
- A stale cached result retains its original timestamp and is never relabeled NOW.
- Facility popovers distinguish source facts from configured prototype eligibility.
- The map says `proximity catchment`; it never says walking time or walking distance in P0.
- FortyGuard, population, facility, and map attribution remain visible.

## Metrics panel

For each allocation show:

- Selected facilities used out of `K`.
- Heat-weighted demand covered and uncovered.
- Percentage of total heat-weighted demand covered.
- Raw residential population inside at least one selected proximity catchment.
- Absolute and percentage objective difference from the optimized set.

When a comparison denominator is zero, percentage improvement is `not applicable`; do not divide by zero or imply infinite improvement. Do not describe population as people currently present.

## Timed demo script

### 0-15 seconds - establish the constraint

“This city has several existing public facilities but resources to prioritize only three. CoolAccess decides which three should receive activation or extended-service priority.”

Show the city, candidates, data mode, and `K=3`.

### 15-35 seconds - show NOW

“FortyGuard supplies hyperlocal temperature evidence. We combine it with licensed residential population and a disclosed proximity model, using one thermal scale across this scenario.”

Show NOW allocation and coverage.

### 35-60 seconds - move forward

“The facilities, population, and budget do not change. Only the future hyperlocal heat pattern changes.”

Select the future timestamp and point to the changed facility.

### 60-90 seconds - prove improvement

“Keeping the original three covers this much heat-weighted demand. A simple hottest-area rule also misses residents and duplicates coverage. The optimized combination covers materially more under the same constraint.”

Show all three comparison cards.

### 90-120 seconds - explain one decision

“This selected facility beats that alternative because it adds more unique heat-weighted demand after accounting for overlap. Replacing it would reduce the objective by this amount.”

Open replacement evidence and provenance.

### 120-140 seconds - close

“The city did not receive more resources. The heat distribution changed, so CoolAccess changed how existing resources should be prioritized.”

State that outputs are planning/accessibility proxies, not health outcomes.

## Demo failure rules

- If thermal contrast is low, show the warning and do not use that timestamp as the competition money shot.
- If no candidate city produces a material, explainable selection change, Task 01B fails and another combination is tested.
- If FortyGuard is unavailable, use only a permitted provenance-preserved cached/prepared response with visible labeling; otherwise show unavailable.
- If hours are missing, do not improvise an operating schedule.
- If an LLM is absent or fails, nothing changes because it is not in P0.
- Never alter real environmental values to force a selection change.

## Red-team answers

1. **Why FortyGuard?** Neighborhood-scale, time-specific thermal patterns drive the allocation; a citywide forecast cannot provide the same spatial evidence.
2. **Why not nearest hottest?** Maximum union coverage accounts for population, facility reach, overlap, and `K`; the naive baseline demonstrates the difference.
3. **Is population real?** It must come from a licensed named source with vintage and transformation disclosure.
4. **Are facilities real?** Candidate coordinates come from a named public source. Eligibility assumptions are separated from source facts.
5. **What is maximized?** Covered population multiplied by a fixed-reference thermal planning priority.
6. **Does it imply health outcomes?** No. It is a resource-planning and geographic-accessibility proxy.
7. **Why would a city use it?** It turns changing heat evidence into a bounded facility-prioritization decision.
8. **What changes?** At least one selected facility and the coverage objective change materially under future heat.
9. **What if FortyGuard fails?** Honest unavailable state or a permitted, labeled real-data fallback.
10. **What if no data intersection works?** Reject the scenario and test another city; do not fabricate one.
11. **Is complexity justified?** Enumeration, two baselines, and replacement evidence directly support the 40/35/15/10 rubric without solver or LLM overhead.
12. **Can one person finish?** Yes, if network routing, mobile resources, capacities, multi-hour budgeting, and AI narration remain outside core.

## What not to build before P0 is deployed

- Mobile-resource dispatch.
- Pedestrian routing or isochrones.
- Facility capacity modeling.
- Editable citywide planning platform.
- Chat or long generated reports.
- Multi-hour facility-hour solver.
- Multiple cities or scenarios.
