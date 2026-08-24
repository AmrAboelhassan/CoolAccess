# Data and City Selection

## 1. Purpose

CoolAccess succeeds only when FortyGuard, facilities, population, geography, licensing, and scenario clarity intersect cleanly. A city is not selected because it is famous for heat or has a cooling-center webpage. Tasks 01A and 01B must pass the combined gate before the scenario, sources, thermal formula, or proximity radius are locked.

There is no preferred city in this document.

## 2. Confirmed provider boundary

For the hackathon, FortyGuard provides U.S.-only coverage, 2-meter street-level ambient air temperature, real and near-real-time data, history from January 1, 2021, approximately 20-meter resolution, hour-by-hour data, and forecasts up to 12 hours.

Authenticated participant behavior remains to be verified: credentials, entitlements, credits, per-call costs, rate/concurrency limits, AOI limits, exact schemas, spatial geometry, practical timestamps, range semantics, processing latency, caching, retained responses, and attribution.

## 3. Unranked city shortlist

The initial shortlist is deliberately unranked. Primary-source starting points must be rechecked during Task 01B for current fields, downloads/APIs, licensing, and update dates.

| Candidate | Facility-source starting evidence | Questions for the gate |
|---|---|---|
| Washington, DC | DC GIS Cooling Centers layer | Are current facilities, eligibility, and useful source fields clean inside an AOI with 6-10 candidates? |
| Chicago | City of Chicago Cooling Centers dataset/map | Is the underlying downloadable dataset current and functioning, and can a coherent subset be defined without cherry-picking? |
| New York City | NYC Cool Options/Cooling Center Finder and official reports | Is a stable reusable facility feed available with acceptable terms and manageable scope? |
| Phoenix/Maricopa County | MAG Heat Relief Network and City of Phoenix heat-response material | Can official facility records be downloaded/reused with clear licensing and constrained to a coherent Phoenix AOI? |
| Los Angeles/Los Angeles County | LA County GIS Cooling Centers layer and municipal open-data portals | Are records current, licensed, and operationally coherent for one city/AOI? |
| Additional U.S. candidate | Primary municipal/state facility source required | Does it outperform the initial shortlist on the full matrix rather than one dataset alone? |

Useful starting links:

- [DC GIS Cooling Centers layer](https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Public_Safety_WebMercator/MapServer/17)
- [DC data terms](https://dc.gov/page/terms-and-conditions-use-district-data)
- [Chicago Cooling Centers](https://data.cityofchicago.org/Health-Human-Services/Cooling-Centers-Map/cj7n-sh49)
- [NYC Cool Options](https://finder.nyc.gov/coolingcenters/locations?mView=map)
- [Maricopa Association of Governments Heat Relief Network](https://azmag.gov/Programs/Community-Initiatives/Heat-Relief-Network/dnn_contentPane)
- [Los Angeles County GIS Cooling Centers layer](https://public.gis.lacounty.gov/public/rest/services/LACounty_Dynamic/LMS_Data_Public/MapServer/55)

A link is evidence of a candidate, not evidence that the data gate has passed.

## 4. City scorecard

For every tested candidate, record evidence and a status of `pass`, `fail`, or `not yet verified` for:

| Gate | Required evidence |
|---|---|
| Authenticated FortyGuard coverage | Successful participant-credential request for the AOI |
| Thermal divergence | Understandable spatial/temporal pattern using real values and a fixed reference |
| Facility quality | Stable IDs, coordinates, types, source dates, and objective eligibility fields |
| Population quality | Appropriate resolution, coverage, vintage, manageable size, and reproducible join |
| Geographic/accessibility data | Valid geometry and feasible proximity calculation; network data only if later used |
| Licensing | Explicit terms compatible with public repository/demo and required attribution recorded |
| Scenario clarity | A judge can understand why selected facilities change |
| Allocation materiality | Visible change and non-trivial gain over static and naive baselines under the locked criterion |
| Solo feasibility | Data preparation and runtime are practical without fragile manual work |

Do not collapse the scorecard into an unsupported numeric ranking. Record qualitative evidence and rejection reasons.

## 5. Population-source candidates

No source is the default before Task 01B.

| Candidate | Potential advantage | Risk/question |
|---|---|---|
| 2020 Census blocks | Fine geography and official counts | Older vintage, many zero-population/irregular geometries, data volume, API/download workflow |
| Census block groups, including ACS alternatives | Smaller and may support newer estimates/attributes | Coarser geography and ACS estimate uncertainty |
| WorldPop | High-resolution raster may integrate directly with heat cells | Exact product year, methodology, license, U.S. fitness, resolution, and file size require verification |
| Other licensed source | May offer newer/local detail | Must document authority, method, license, reproducibility, and public-demo compatibility |

Selection criteria:

- Actual spatial resolution useful within candidate catchments.
- Vintage and what `population` represents.
- Geometry/raster alignment with FortyGuard and facility catchments.
- License and attribution.
- Download/API reliability and reproducibility.
- File size, preprocessing burden, and browser/backend runtime.
- Coverage gaps and uncertainty.

Residential population must never be described as current occupancy, visitors, vulnerability, or medical need.

Starting official sources include [Census data APIs](https://www.census.gov/data/developers/data-sets.html), [2020 TIGER/Line files](https://www.census.gov/cgi-bin/geo/shapefiles/index.php), and [WorldPop](https://www.worldpop.org/). Exact datasets and terms must be recorded when evaluated.

## 6. Geographic-data candidates

- Facility/source geometry from the chosen municipal dataset.
- Census or municipal boundaries for AOI and population joins.
- A geodesic library calculation for P0 proximity catchments.
- OpenStreetMap only when legitimate base mapping or later network analysis requires it; preserve [OpenStreetMap attribution and ODbL obligations](https://www.openstreetmap.org/copyright).

P0 does not claim walking access. If a true network model is later implemented, record graph source/date, mode rules, edge restrictions, routing engine, disconnected areas, and attribution.

## 7. Facility eligibility and anti-cherry-picking

Before viewing optimizer winners for a candidate AOI, define:

- Geographic boundary.
- Eligible facility types.
- Public-access requirement supported by source evidence.
- Exclusions such as restricted-age/member-only facilities when known.
- Required valid point geometry.
- Whether source status/activation fields are trustworthy enough to filter.
- Source date and duplicate-resolution rule.

Then include every qualifying facility in the AOI. Adjust or reject the AOI for operational coherence before optimization, not to force desired winners. Target approximately 6-10 candidates; record any justified deviation.

Hours are optional. If source hours are verified, preserve them as evidence and apply only documented eligibility logic. If they are absent or unreliable, do not claim actual opening, closing, or extension.

## 8. Data normalization and provenance ledger

For each source record:

- Dataset title and publishing authority.
- Canonical URL or API endpoint.
- Access/retrieval date and published/updated vintage.
- License/terms URL and attribution wording.
- Raw spatial reference and normalized spatial reference.
- Fields used and fields deliberately ignored.
- Filters, deduplication, geometry repair, aggregation, or representative-point method.
- Checksum/version for permitted retained inputs.
- Known quality limitations.

FortyGuard provenance additionally records requested AOI/time, valid time, observed/forecast status, temperature unit, retrieval time, adapter version, activity reference when permitted, and live/cache/prepared mode.

## 9. Thermal contrast and materiality spike

For every candidate city/AOI:

1. Retrieve bounded real NOW/future samples with authenticated access.
2. Inspect missing coverage, values, distribution, spatial pattern, and temporal changes.
3. Test reasonable fixed-reference thermal formulations without tuning to force winners.
4. Build candidate population and facility joins.
5. Test reasonable proximity configurations justified by AOI scale.
6. Run optimized, static, and naive baseline allocations.
7. Decide whether differences are visible, non-trivial, stable, and explainable.
8. Record the chosen contrast/materiality criterion before locking the demo scenario.

The criterion may combine distribution evidence, allocation stability, objective gain, and presentation clarity. Do not invent a numeric threshold before observing data, and do not relax it merely to pass a preferred city.

## 10. Gate outcomes

- **Pass:** every data class and license is usable; contrast is meaningful; allocation changes; improvement over both baselines is non-trivial; explanation is clear; solo implementation is practical.
- **Fail:** any essential data/license is unusable, thermal contrast is trivial, selection does not change materially, or the story depends on unsupported assumptions.
- **Not yet verified:** evidence is incomplete; the city cannot be selected.

If no candidate passes, expand the U.S. shortlist and repeat. Do not invent data, substitute a generic forecast, manipulate facility eligibility after optimization, or hide a failed gate.

## 11. Source-selection acceptance criteria

- Final city decision cites a completed scorecard and authenticated FortyGuard evidence.
- Population and facility choices include source, version, license, transformation, and rejection rationale for alternatives.
- Final AOI and eligibility rules predate optimizer-result selection.
- Thermal normalization uses one fixed reference and passes recorded contrast checks.
- Proximity wording and UI match the implemented geographic method.
- Both baselines run under identical inputs and `K`.
- The locked scenario is reproducible without secret or manual data manipulation.
