import React from 'react';
import { Flame, Users, CheckCircle2, Cpu } from 'lucide-react';
import { CoverageMetrics } from '../types';

interface MetricsSummaryProps {
  metrics: CoverageMetrics | null;
  selectedCount: number;
  budgetK: number;
  tieBreakCriterion?: string;
  combinationsEvaluated?: number;
}

export const MetricsSummary: React.FC<MetricsSummaryProps> = ({
  metrics,
  selectedCount,
  budgetK,
  tieBreakCriterion,
  combinationsEvaluated,
}) => {
  if (!metrics) {
    return (
      <div className="metrics-loading-card">
        <span>Computing optimal coverage metrics...</span>
      </div>
    );
  }

  const popPct = ((metrics.covered_population / (metrics.total_population || 1)) * 100).toFixed(1);

  return (
    <div className="metrics-summary-container">
      <div className="section-title-row">
        <h3 className="section-title">Coverage & Demand Performance</h3>
        <span className="section-badge">Deterministic Optimum</span>
      </div>

      <div className="metrics-cards-grid">
        {/* Heat-Weighted Demand Card */}
        <div className="metric-metric-card primary">
          <div className="metric-top">
            <div className="metric-title-group">
              <Flame size={16} className="text-amber" />
              <span className="metric-name">Heat-Weighted Demand Covered</span>
            </div>
            <span className="metric-pct-tag">{metrics.coverage_percentage.toFixed(1)}%</span>
          </div>

          <div className="metric-big-num">
            {metrics.covered_heat_weighted_demand.toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </div>

          <div className="metric-progress-bar-bg">
            <div
              className="metric-progress-bar-fill demand"
              style={{ width: `${Math.min(100, metrics.coverage_percentage)}%` }}
            />
          </div>

          <div className="metric-sub-stats">
            <span>Total AOI Demand: {metrics.total_heat_weighted_demand.toLocaleString(undefined, { maximumFractionDigits: 1 })}</span>
            <span>Uncovered: {metrics.uncovered_heat_weighted_demand.toLocaleString(undefined, { maximumFractionDigits: 1 })}</span>
          </div>
        </div>

        {/* 2020 Census Residential Population Card */}
        <div className="metric-metric-card">
          <div className="metric-top">
            <div className="metric-title-group">
              <Users size={16} className="text-sky" />
              <span className="metric-name">2020 Census Residents Covered</span>
            </div>
            <span className="metric-pct-tag">{popPct}%</span>
          </div>

          <div className="metric-big-num">
            {metrics.covered_population.toLocaleString()}
          </div>

          <div className="metric-progress-bar-bg">
            <div
              className="metric-progress-bar-fill population"
              style={{ width: `${popPct}%` }}
            />
          </div>

          <div className="metric-sub-stats">
            <span>Total AOI Residents: {metrics.total_population.toLocaleString()}</span>
            <span>Uncovered: {metrics.uncovered_population.toLocaleString()}</span>
          </div>
        </div>

        {/* Constrained Municipal Budget Card */}
        <div className="metric-metric-card">
          <div className="metric-top">
            <div className="metric-title-group">
              <CheckCircle2 size={16} className="text-emerald" />
              <span className="metric-name">Budget Constraint Utilization</span>
            </div>
            <span className="budget-pill">K = {budgetK}</span>
          </div>

          <div className="metric-big-num">
            {selectedCount} / {budgetK} <span className="text-sm font-normal">Active Sites</span>
          </div>

          <div className="metric-detail-row">
            <div className="solver-meta">
              <Cpu size={12} className="text-muted" />
              <span>
                {combinationsEvaluated !== undefined
                  ? `Optimization Engine: Exhaustive evaluation of ${combinationsEvaluated} candidate subsets (up to K=${budgetK})`
                  : 'Optimization Engine: Candidate-subset count not provided'}
              </span>
            </div>
            <div className="tiebreak-meta">
              <span>Objective: Maximize heat-weighted demand coverage ({tieBreakCriterion || 'heat_weighted_demand'})</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
