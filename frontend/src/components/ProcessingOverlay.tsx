import React, { useEffect } from 'react';
import {
  Thermometer,
  Users,
  Grid,
  ShieldCheck,
  Sparkles,
  Cpu,
  LucideIcon,
} from 'lucide-react';

interface ProcessingOverlayProps {
  isDataReady: boolean;
  onComplete: () => void;
}

interface ProcessingStage {
  step: number;
  title: string;
  subtitle: string;
  tag: string;
  icon: LucideIcon;
}

const STAGES: ProcessingStage[] = [
  {
    step: 1,
    title: 'Synchronizing FortyGuard thermal evidence...',
    subtitle: 'Loading 100m thermal grid and AOI thermal context',
    tag: 'THERMAL_GRID_100M',
    icon: Thermometer,
  },
  {
    step: 2,
    title: 'Loading residential population evidence...',
    subtitle: 'Joining prepared thermal cells with 2020 Census population counts',
    tag: 'CENSUS_POPULATION',
    icon: Users,
  },
  {
    step: 3,
    title: 'Evaluating facility configurations...',
    subtitle: 'Testing feasible K=3 cooling allocation combinations',
    tag: 'COMBINATORIAL_SOLVER',
    icon: Grid,
  },
  {
    step: 4,
    title: 'Solving optimization objective...',
    subtitle: 'Maximizing covered heat-weighted demand',
    tag: 'DETERMINISTIC_OPTIMIZER',
    icon: ShieldCheck,
  },
  {
    step: 5,
    title: 'Preparing decision evidence...',
    subtitle: 'Formatting deterministic results; AI inquiry remains a separate user action',
    tag: 'EVIDENCE_INTERFACE',
    icon: Sparkles,
  },
];

export const ProcessingOverlay: React.FC<ProcessingOverlayProps> = ({
  isDataReady,
  onComplete,
}) => {
  // Dismiss only when the actual scenario request reports ready. The short visual
  // transition is not presented as backend progress telemetry.
  useEffect(() => {
    if (isDataReady) {
      const timeout = setTimeout(() => {
        onComplete();
      }, 350);
      return () => clearTimeout(timeout);
    }
  }, [isDataReady, onComplete]);

  return (
    <div className="processing-overlay-backdrop" role="status" aria-live="polite">
      <div className="processing-modal-card">
        {/* Brand Header */}
        <div className="processing-header">
          <div className="processing-brand-badge">
            <Cpu size={20} className="text-sky" />
          </div>
          <div className="processing-brand-text">
            <div className="processing-brand-title-row">
              <span className="processing-title">CoolAccess</span>
              <span className="processing-tag">DETERMINISTIC ALLOCATION PIPELINE</span>
            </div>
            <span className="processing-sub">
              Exact K-Constrained Municipal Cooling Allocation
            </span>
          </div>
        </div>

        {/* Step Indicator Bar */}
        <div className="processing-steps-tracker">
          {STAGES.map((s, idx) => {
            return (
              <div
                key={s.step}
                className="tracker-step"
                title={`${s.title} ${s.subtitle}`}
              >
                <div className="tracker-node">
                  <span className="node-number">{s.step}</span>
                </div>
                {idx < STAGES.length - 1 && <div className="tracker-line" />}
              </div>
            );
          })}
        </div>

        {/* Actual readiness state; the numbered phases above are conceptual only. */}
        <div className="processing-active-stage-box">
          <div className="active-stage-icon-wrap">
            {isDataReady ? (
              <ShieldCheck size={24} className="active-icon" />
            ) : (
              <Cpu size={24} className="active-icon" />
            )}
          </div>
          <div className="active-stage-content">
            <div className="active-stage-tag-row">
              <span className="stage-step-label">CONCEPTUAL 5-PHASE PIPELINE</span>
              <span className="stage-code-tag">EXACT LIVE STAGE NOT REPORTED</span>
            </div>
            <h4 className="active-stage-title">
              {isDataReady ? 'Authoritative scenario ready' : 'Preparing authoritative scenario...'}
            </h4>
            <p className="active-stage-subtitle">
              {isDataReady
                ? 'The server returned verified deterministic allocation evidence.'
                : 'Waiting for the server response; phase completion is not inferred from elapsed time.'}
            </p>
          </div>
        </div>

        {/* Progress Pipeline Indicator */}
        <div className="processing-footer-bar">
          <div className="pipeline-pulse-dot" />
          <span className="pipeline-status-text">
            {isDataReady
              ? 'Verified scenario received — rendering decision platform...'
              : 'Waiting for prepared benchmark data...'}
          </span>
        </div>
      </div>
    </div>
  );
};
