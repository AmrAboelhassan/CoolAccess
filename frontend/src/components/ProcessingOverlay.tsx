import React, { useState, useEffect } from 'react';
import {
  Thermometer,
  Users,
  Grid,
  ShieldCheck,
  Sparkles,
  CheckCircle2,
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
  const [currentStageIdx, setCurrentStageIdx] = useState<number>(0);
  const [sequenceFinished, setSequenceFinished] = useState<boolean>(false);

  useEffect(() => {
    const stageDurationMs = 450;
    const interval = setInterval(() => {
      setCurrentStageIdx((prev) => {
        if (prev < STAGES.length - 1) {
          return prev + 1;
        } else {
          clearInterval(interval);
          setSequenceFinished(true);
          return prev;
        }
      });
    }, stageDurationMs);

    return () => clearInterval(interval);
  }, []);

  // When stage sequence finishes and real backend data is ready, transition smoothly
  useEffect(() => {
    if (sequenceFinished && isDataReady) {
      const timeout = setTimeout(() => {
        onComplete();
      }, 350);
      return () => clearTimeout(timeout);
    }
  }, [sequenceFinished, isDataReady, onComplete]);

  const activeStage = STAGES[currentStageIdx];
  const ActiveIcon = activeStage.icon;

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
              <span className="processing-tag">TEMPERATURE DECISION PIPELINE</span>
            </div>
            <span className="processing-sub">
              Municipal Heat Resilience & Spatial Decision Platform
            </span>
          </div>
        </div>

        {/* Step Indicator Bar */}
        <div className="processing-steps-tracker">
          {STAGES.map((s, idx) => {
            const isCompleted = idx < currentStageIdx;
            const isCurrent = idx === currentStageIdx;
            return (
              <div
                key={s.step}
                className={`tracker-step ${isCompleted ? 'completed' : ''} ${
                  isCurrent ? 'active' : ''
                }`}
              >
                <div className="tracker-node">
                  {isCompleted ? (
                    <CheckCircle2 size={13} className="node-icon-completed" />
                  ) : (
                    <span className="node-number">{s.step}</span>
                  )}
                </div>
                {idx < STAGES.length - 1 && <div className="tracker-line" />}
              </div>
            );
          })}
        </div>

        {/* Active Stage Callout */}
        <div className="processing-active-stage-box">
          <div className="active-stage-icon-wrap">
            <ActiveIcon size={24} className="active-icon" />
          </div>
          <div className="active-stage-content">
            <div className="active-stage-tag-row">
              <span className="stage-step-label">STAGE {activeStage.step} OF 5</span>
              <span className="stage-code-tag">{activeStage.tag}</span>
            </div>
            <h4 className="active-stage-title">{activeStage.title}</h4>
            <p className="active-stage-subtitle">{activeStage.subtitle}</p>
          </div>
        </div>

        {/* Progress Pipeline Indicator */}
        <div className="processing-footer-bar">
          <div className="pipeline-pulse-dot" />
          <span className="pipeline-status-text">
            {sequenceFinished && !isDataReady
              ? 'Waiting for prepared benchmark data...'
              : sequenceFinished && isDataReady
              ? 'Verification complete — rendering decision platform...'
              : 'Deterministic spatial analysis in progress...'}
          </span>
        </div>
      </div>
    </div>
  );
};
