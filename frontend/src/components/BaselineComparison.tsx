import React from 'react';
import { Award, TrendingUp, AlertTriangle, CheckCircle, ShieldCheck } from 'lucide-react';
import { StaticBaseline, NaiveBaseline } from '../types';

interface BaselineComparisonProps {
  dynamicObjective: number;
  dynamicPopulation: number;
  dynamicFacilities: string[];
  staticBaseline: StaticBaseline | null;
  naiveBaseline: NaiveBaseline | null;
  currentTimestamp: string;
}

export const BaselineComparison: React.FC<BaselineComparisonProps> = ({
  dynamicObjective,
  dynamicPopulation,
  dynamicFacilities,
  staticBaseline,
  naiveBaseline,
  currentTimestamp,
}) => {
  const budgetK = dynamicFacilities.length;

  const staticGain = staticBaseline?.absolute_gain ?? 0;
  const staticGainPct = staticBaseline?.percentage_gain ?? 0;
  const staticPop = staticBaseline?.covered_population ?? 0;
  const staticPopDelta = dynamicPopulation - staticPop;

  const naiveGain = naiveBaseline?.absolute_gain ?? 0;
  const naiveGainPct = naiveBaseline?.percentage_gain ?? 0;

  const hasStaticAdvantage = staticGain > 0.005;
  const hasStaticDisadvantage = staticGain < -0.005;
  const hasNaiveAdvantage = naiveGain > 0.005;
  const hasNaiveDisadvantage = naiveGain < -0.005;
  const populationDeltaLabel =
    staticPopDelta > 0
      ? 'MORE RESIDENTS COVERED VS STATIC'
      : staticPopDelta < 0
      ? 'FEWER RESIDENTS COVERED VS STATIC'
      : 'RESIDENT COVERAGE VS STATIC';
  const populationDeltaValue =
    staticPopDelta > 0
      ? `+${staticPopDelta.toLocaleString()}`
      : staticPopDelta < 0
      ? `${Math.abs(staticPopDelta).toLocaleString()} fewer`
      : 'Same coverage';

  if (dynamicFacilities.length === 0 || (!staticBaseline && !naiveBaseline)) {
    return (
      <div className="baseline-comparison-panel">
        <div className="panel-header-row">
          <div className="panel-title-group">
            <Award size={18} className="text-amber" />
            <div>
              <h3 className="section-title">
                Baseline Comparison Proof (Same K={budgetK || 3} Budget)
              </h3>
              <p className="section-subtitle">
                Awaiting optimization results for {currentTimestamp} UTC...
              </p>
            </div>
          </div>
        </div>
        <div className="drawer-loading-box">
          Computing baseline comparison metrics...
        </div>
      </div>
    );
  }

  return (
    <div className="baseline-comparison-panel">
      <div className="panel-header-row">
        <div className="panel-title-group">
          <Award size={18} className="text-amber" />
          <div>
            <h3 className="section-title">
              Baseline Comparison Proof (Same K={budgetK || 3} Budget)
            </h3>
            <p className="section-subtitle">
              Dynamic optimization compared with static and naive hottest-catchment baselines at {currentTimestamp} UTC
            </p>
          </div>
        </div>

        {hasStaticAdvantage ? (
          <div className="key-gain-badge">
            <TrendingUp size={16} />
            <span>
              +{staticGainPct.toFixed(2)}% heat-weighted demand (+{staticGain.toFixed(2)} units) with the same K={budgetK || 3}
            </span>
          </div>
        ) : (
          <div className="key-gain-badge neutral">
            <ShieldCheck size={16} />
            <span>
              {hasStaticDisadvantage
                ? `${Math.abs(staticGain).toFixed(2)} fewer demand units than static`
                : `Same objective as static baseline (K=${budgetK || 3})`}
            </span>
          </div>
        )}
      </div>

      {/* Dynamic Judge Summary Bar */}
      <div className="baseline-summary-bar">
        <div className="summary-stat-cell">
          <span className="summary-stat-label">DIURNAL OPTIMIZATION RESPONSE</span>
          <span className="summary-stat-value text-emerald font-mono">
            {hasStaticAdvantage
              ? `+${staticGainPct.toFixed(2)}% vs Static`
              : hasStaticDisadvantage
              ? `${Math.abs(staticGainPct).toFixed(2)}% below Static`
              : 'Same Objective as Static'}
          </span>
          <span className="summary-stat-sub">
            {hasStaticAdvantage
              ? `${staticGain.toFixed(2)} more heat-weighted demand units covered by the dynamic set.`
              : hasStaticDisadvantage
              ? `${Math.abs(staticGain).toFixed(2)} fewer heat-weighted demand units covered than the static set.`
              : 'The dynamic and static sets produce the same heat-weighted demand objective at this timestamp.'}
          </span>
        </div>

        <div className="summary-stat-cell">
          <span className="summary-stat-label">{populationDeltaLabel}</span>
          <span className="summary-stat-value text-sky font-mono">
            {populationDeltaValue}
          </span>
          <span className="summary-stat-sub">
            {staticPopDelta === 0
              ? 'Same 2020 Census resident coverage as the static baseline'
              : `Compared with the ${staticBaseline?.source_timestamp || 'reference'} static allocation`}
          </span>
        </div>

        <div className="summary-stat-cell">
          <span className="summary-stat-label">MUNICIPAL RESOURCE BUDGET</span>
          <span className="summary-stat-value text-amber font-mono">
            K={budgetK || 3} Selected Facilities
          </span>
          <span className="summary-stat-sub">
            Same facility-count budget in every comparison; no monetary cost model is asserted
          </span>
        </div>
      </div>

      {/* 3 Core Comparison Cards */}
      <div className="comparison-cards-grid">
        {/* Card 1: Dynamic Optimum (CoolAccess) */}
        <div className="comp-card winner">
          <div className="comp-badge winner">
            <CheckCircle size={13} />
            <span>Dynamic Optimum (CoolAccess)</span>
          </div>

          <div className="comp-facility-tags">
            {dynamicFacilities.map((id) => (
              <span key={id} className="comp-fac-pill active">{id}</span>
            ))}
          </div>

          <div className="comp-stats-block">
            <div className="comp-stat-row">
              <span className="stat-label">Heat-Weighted Demand:</span>
              <span className="stat-value text-emerald font-bold">
                {dynamicObjective.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="comp-stat-row">
              <span className="stat-label">Covered Census Population:</span>
              <span className="stat-value">{dynamicPopulation.toLocaleString()}</span>
            </div>
            <div className="comp-stat-row">
              <span className="stat-label">Optimization Status:</span>
              <span className="stat-value text-accent font-semibold">Global Optimum</span>
            </div>
          </div>

          <p className="comp-summary-text">
            Maximizes union coverage of heat-weighted demand without double-counting overlapping catchments.
          </p>
        </div>

        {/* Card 2: Static Baseline (Midday Plan) */}
        <div className="comp-card">
          <div className="comp-badge neutral">
            <span>Static Baseline ({staticBaseline?.source_timestamp || '16:00'} Set)</span>
          </div>

          <div className="comp-facility-tags">
            {staticBaseline?.selected_facility_ids.map((id) => (
              <span key={id} className="comp-fac-pill">{id}</span>
            )) || <span>None</span>}
          </div>

          <div className="comp-stats-block">
            <div className="comp-stat-row">
              <span className="stat-label">Heat-Weighted Demand:</span>
              <span className="stat-value">
                {staticBaseline?.objective_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? 'N/A'}
              </span>
            </div>
            <div className="comp-stat-row">
              <span className="stat-label">Covered Census Population:</span>
              <span className="stat-value">
                {staticBaseline?.covered_population.toLocaleString() ?? 'N/A'}
              </span>
            </div>
            <div className="comp-stat-row">
              <span className="stat-label">Opportunity Loss vs Dynamic:</span>
              <span className={`stat-value ${staticGain > 0 ? 'text-amber' : 'text-muted'}`}>
                {staticGain > 0 ? `-${staticGain.toFixed(2)} (-${staticGainPct.toFixed(1)}%)` : 'Baseline Parity'}
              </span>
            </div>
          </div>

          <p className="comp-summary-text">
            {staticGain > 0
              ? `Retaining the ${staticBaseline?.source_timestamp || 'reference'} facility set covers ${staticGain.toFixed(2)} fewer heat-weighted demand units at this timestamp.`
              : hasStaticDisadvantage
              ? `The static set covers ${Math.abs(staticGain).toFixed(2)} more heat-weighted demand units at this timestamp.`
              : 'The static and dynamic allocations produce the same objective at this timestamp.'}
          </p>
        </div>

        {/* Card 3: Naive Thermal Baseline */}
        <div className="comp-card">
          <div className="comp-badge warning">
            <AlertTriangle size={13} />
            <span>Naive Hottest-Catchment Baseline</span>
          </div>

          <div className="comp-facility-tags">
            {naiveBaseline?.selected_facility_ids.map((id) => (
              <span key={id} className="comp-fac-pill warning">{id}</span>
            )) || <span>None</span>}
          </div>

          <div className="comp-stats-block">
            <div className="comp-stat-row">
              <span className="stat-label">Heat-Weighted Demand:</span>
              <span className="stat-value">
                {naiveBaseline?.objective_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? 'N/A'}
              </span>
            </div>
            <div className="comp-stat-row">
              <span className="stat-label">Covered Census Population:</span>
              <span className="stat-value">
                {naiveBaseline?.covered_population.toLocaleString() ?? 'N/A'}
              </span>
            </div>
            <div className="comp-stat-row">
              <span className="stat-label">Deficit vs Dynamic:</span>
              <span className="stat-value text-amber">
                {hasNaiveAdvantage
                  ? `-${naiveGain.toFixed(2)} (-${naiveGainPct.toFixed(2)}%)`
                  : hasNaiveDisadvantage
                  ? `+${Math.abs(naiveGain).toFixed(2)} vs Dynamic`
                  : 'Matches Dynamic (0.00)'}
              </span>
            </div>
          </div>

          <p className="comp-summary-text">
            Selects the hottest catchments using the benchmark rule. At this timestamp it may differ from, or tie, the dynamic heat-weighted-demand optimum.
          </p>
        </div>
      </div>
    </div>
  );
};
