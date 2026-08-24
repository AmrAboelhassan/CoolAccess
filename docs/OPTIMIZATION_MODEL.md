# Optimization Model

## 1. Purpose and boundary

CoolAccess uses deterministic maximum coverage to select existing eligible facilities under a fixed resource limit. The model is a transparent planning prototype. It is not a medical heat-risk model, emergency order, operating-hours system, or prediction of cooling effectiveness.

P0 independently optimizes NOW and at least one future timestamp. A multi-hour facility-hours formulation is P0 Conditional only.

## 2. Sets, inputs, and variables

For population units `i`, candidate facilities `j`, and timestamps `t`:

| Symbol | Meaning | Source |
|---|---|---|
| `P_i` | Residential population assigned to unit `i` | Selected licensed population source |
| `T_i,t` | FortyGuard-derived temperature assigned to unit `i` at `t` | Validated provider observation |
| `H_i,t` | Fixed-reference thermal planning priority | Deterministic normalization |
| `W_i,t` | Heat-weighted demand, `P_i * H_i,t` | Deterministic calculation |
| `A_i,j` | 1 when unit `i` is in facility `j`'s proximity catchment | Deterministic geographic calculation |
| `K` | Maximum selected facilities; P0 default 3 | Scenario constraint |
| `x_j,t` | 1 when facility `j` is selected at `t` | Decision variable |
| `z_i,t` | 1 when unit `i` is covered by at least one selected facility | Covered-demand variable |

Facility hours, capacity, medical vulnerability, and real-time occupancy are not implicit model inputs.

## 3. Thermal-priority alternatives

The formula is intentionally provisional until real FortyGuard distributions are inspected in Tasks 01A/01B. The final P0 method must create one reference from the selected AOI and evaluated horizon and reuse it at every timestamp.

Candidate formulations:

### Robust fixed anchors

Derive lower and upper anchors from the pooled valid temperatures across all evaluated AOI/timestamp samples, then apply:

```text
H_i,t = clamp((T_i,t - lower_anchor) / (upper_anchor - lower_anchor), 0, 1)
```

Robust quantiles may reduce outlier sensitivity, but the chosen quantiles require inspection and disclosure.

### Pooled empirical distribution

Build one empirical distribution from all valid temperatures across the AOI and evaluated horizon, then map every `T_i,t` through that same distribution. This is robust and comparable across time but expresses relative scenario position rather than absolute thermal severity.

### Rejected final approach: independent timestamp percentile

Recalculating a percentile separately at every timestamp guarantees apparent differentiation even when spatial differences are trivial and makes NOW/future weights less stable. It may be inspected during analysis but cannot become P0's final method.

### Rejected approach: raw Celsius multiplier

Using temperature directly as a linear health or harm multiplier has no documented meaning and risks unsupported health interpretation.

The selected formula, anchors/reference sample, source timestamps, exclusions, and version must appear in evidence and [DECISIONS.md](DECISIONS.md).

## 4. Low-contrast and materiality gates

Task 01B must inspect real distributions before defining the gate. It records:

- Spatial spread within each candidate timestamp.
- Temporal change in neighborhood pattern, not only citywide warming.
- Stability under reasonable normalization choices.
- Whether the resulting facility change is understandable.
- Objective improvement over both baselines.

No threshold is invented before inspection. Once recorded, it is applied consistently to the locked scenario and tests.

When contrast is below the recorded criterion:

- Mark `thermal_contrast = low`.
- Show temperatures and diagnostic allocation only if useful.
- Do not claim a meaningful heat-driven optimization improvement.
- Do not use the sample as the competition demo state.

## 5. Proximity relationship

P0 defines `A_i,j` from a disclosed straight-line/geodesic radius around facility `j`. Population units use a documented representative geometry rule such as an internal point or intersected area method chosen during Task 01B.

This is a **proximity catchment / geographic accessibility proxy**. It is not a walking-time, walking-distance, route, service-capacity, or attendance model.

The final radius and assignment method remain provisional until facility spacing, population geometry, AOI scale, data size, and edge effects are inspected.

## 6. Maximum-coverage formulation

For each timestamp `t`:

```text
maximize sum_i W_i,t * z_i,t
```

Subject to:

```text
sum_j x_j,t <= K

z_i,t <= sum_j A_i,j * x_j,t    for every i

x_j,t in {0,1}
z_i,t in {0,1}
```

Because all weights are nonnegative, selected facilities will normally reach `K` when eligible facilities add coverage. If fewer are selected, the evidence must state that remaining candidates add no positive covered demand or are ineligible.

## 7. P0 solution method

For 6-10 facilities and `K=3`, enumerate every eligible combination of size up to `K`, calculate union coverage, and select deterministically. At 10 choose 3, only 120 three-facility combinations exist.

Comparison order:

1. Higher union-covered heat-weighted demand.
2. Higher union-covered residential population.
3. Fewer selected facilities (lower-cardinality preference applies only when both objective and population are exactly tied, avoiding the consumption of zero-marginal resource capacity while preserving `selected_count <= K` semantics).
4. Lexicographically smaller sorted canonical facility-ID tuple.

Floating-point comparison must use a documented tolerance without rounding away meaningful differences. Display rounding cannot affect selection.

Enumeration is preferred over adding a solver because it is auditable, easily tested, and sufficient for P0 scale. The binary formulation remains the conceptual contract.

## 8. Baseline A - Static allocation

1. Optimize at NOW to obtain `S_now`.
2. Hold `S_now` unchanged at future timestamp `t_future`.
3. Recalculate its coverage using future `H_i,t` and `W_i,t`.
4. Compare against the independently optimized `S_future`.

This measures the value of adapting allocation when the heat pattern changes.

## 9. Baseline B - Naive thermal allocation

For each facility and timestamp:

```text
naive_heat_score(j,t) = unweighted mean H over valid thermal cells
                        within facility j's proximity catchment
```

Select the top `K` facilities by descending naive heat score, breaking ties by stable facility ID. The baseline deliberately ignores population, duplicate/overlapping coverage, and the union objective.

If a facility has no valid thermal cells in its catchment, its naive score is unavailable rather than zero. A baseline requiring unavailable candidates cannot be presented as complete.

This is a deliberately simple comparison, not a straw-man claim that a named municipality currently uses the method.

## 10. Comparable metrics

For optimized and baseline allocations at the same timestamp:

```text
covered_weight = sum_i W_i,t where unit i is covered
uncovered_weight = total_weight - covered_weight
coverage_rate = covered_weight / total_weight
raw_population_covered = sum_i P_i where unit i is covered
absolute_gain = optimized_covered_weight - baseline_covered_weight
percentage_gain = absolute_gain / baseline_covered_weight
```

When total or baseline covered weight is zero, return `not_applicable` for the corresponding ratio and explain why.

The final scenario must satisfy the post-inspection materiality criterion against both baselines. An infinitesimal floating-point advantage is not demo evidence.

## 11. Selected-versus-unselected evidence

For selected facility `b` in optimal set `S*` and unselected facility `a`:

```text
replacement_set = (S* - {b}) union {a}
replacement_loss = objective(S*) - objective(replacement_set)
```

Evidence includes:

- Each facility's proximity catchment and source facts.
- Unique heat-weighted demand added to its set.
- Demand overlapping other selected facilities.
- Raw residential population in unique and overlapping coverage.
- Optimal and replacement objectives.
- Replacement loss and deterministic tie reason.
- Timestamp, fixed thermal reference, population source, proximity method, and warnings.

If replacement loss is zero, the facilities are objective-equivalent and the UI must explain the tie-break rather than claim one is substantively better.

## 12. Missing-data policy

- Missing mandatory temperature: exclude the affected population unit/time; if coverage falls below the Task 01B standard, block the allocation.
- Ambiguous units or timestamps: block normalization and optimization.
- Missing population: exclude only under a documented coverage rule; never substitute invented residents.
- Missing facility hours: retain a facility only when it otherwise meets eligibility; avoid schedule claims.
- Missing geometry: isolate or reject the affected record and disclose it.
- Partial proximity-edge coverage: report completeness and apply the locked gate.
- Provider failure: use only permitted labeled real cached/prepared data; otherwise unavailable.

## 13. P0 Conditional multi-hour formulation

Only after the conditional gate passes, index activation by time and replace the simple facility count with a verified facility-hour budget. Candidate additions include `x_j,t`, total facility-hours, valid hour eligibility, and population-hours covered. Do not add capacity, relocation, or inferred schedules without real supporting data.

Discrete samples must be labeled sampled. Missing hours/timestamps are not interpolated silently.

## 14. Required tests

- Fixed reference is identical for NOW and every future timestamp.
- Normalization clamps, ties, degenerate anchors, missing cells, and outliers.
- Low-contrast gate and warning behavior.
- Population assignment and proximity boundary cases.
- Union coverage avoids double counting.
- `K=0`, `K=3`, fewer than `K` eligible facilities, and duplicated catchments.
- Exact enumeration against hand-calculated examples.
- Deterministic objective, population, and facility-ID ties.
- Static baseline uses the NOW set at the future timestamp.
- Naive baseline ignores population and overlap as specified.
- Optimized objective never falls below either valid baseline under identical inputs.
- Replacement loss, equivalent replacements, and unique/overlap evidence.
- Zero-denominator metric behavior.
- Missing temperature, population, geometry, and hours.
- Identical structured input always returns identical output.

## 15. Limitations

- Residential population is not real-time occupancy or need.
- Proximity does not model routes, barriers, capacity, willingness, eligibility of residents, or attendance.
- Thermal priority is scenario-relative and not a health-risk measure.
- Candidate facilities are pre-screened planning options, not operational commitments.
- P0 independent timestamps do not optimize continuity or staffing across hours.
- A selected facility does not imply that opening it produces a quantified health outcome.
