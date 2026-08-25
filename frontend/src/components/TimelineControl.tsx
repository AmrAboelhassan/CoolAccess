import React from 'react';
import { Sun, Sunset, ArrowRight, Activity } from 'lucide-react';

interface TimelineControlProps {
  currentTimestamp: string;
  onSelectTimestamp: (ts: string) => void;
  availableTimestamps: string[];
}

const TIMESTAMP_METADATA: Record<string, { label: string; edt: string; phase: string; desc: string }> = {
  '14:00': {
    label: '14:00 UTC',
    edt: '10:00 AM EDT',
    phase: '10 AM Local',
    desc: 'Prepared FortyGuard temperature snapshot for 14:00 UTC.',
  },
  '16:00': {
    label: '16:00 UTC (Reference)',
    edt: '12:00 PM EDT',
    phase: 'Reference State',
    desc: 'Static-baseline reference allocation: DC_089, DC_148, and DC_166.',
  },
  '18:00': {
    label: '18:00 UTC',
    edt: '02:00 PM EDT',
    phase: '2 PM Local',
    desc: 'Prepared FortyGuard temperature snapshot; the selected facility set remains unchanged.',
  },
  '20:00': {
    label: '20:00 UTC (Late Afternoon)',
    edt: '04:00 PM EDT',
    phase: 'Allocation Change',
    desc: 'The deterministic optimum removes DC_148 and adds DC_135 at this historical timestamp.',
  },
  '22:00': {
    label: '22:00 UTC',
    edt: '06:00 PM EDT',
    phase: '6 PM Local',
    desc: 'Prepared FortyGuard temperature snapshot; the 20:00 selected facility set is retained.',
  },
};

export const TimelineControl: React.FC<TimelineControlProps> = ({
  currentTimestamp,
  onSelectTimestamp,
  availableTimestamps,
}) => {
  const currentInfo = TIMESTAMP_METADATA[currentTimestamp] || {
    label: `${currentTimestamp} UTC`,
    edt: 'Local EDT',
    phase: 'Diurnal Step',
    desc: 'Hyperlocal heat distribution.',
  };

  const isTransitionTarget = currentTimestamp === '20:00';
  const isNowState = currentTimestamp === '16:00';

  return (
    <div className="timeline-section">
      <div className="timeline-header">
        <div className="timeline-title-row">
          <Activity size={16} className="text-sky" />
          <span className="timeline-heading">Diurnal Thermal Timeline & Scenario Control</span>
        </div>

        {/* Quick Demo Jump Controls */}
        <div className="demo-shortcuts">
          <span className="shortcuts-label">Demo Workflow:</span>
          <button
            type="button"
            className={`demo-btn ${isNowState ? 'active' : ''}`}
            aria-pressed={isNowState}
            onClick={() => onSelectTimestamp('16:00')}
          >
            <Sun size={14} />
            <span>1. Reference (16:00 UTC)</span>
          </button>
          <div className="shortcut-arrow">
            <ArrowRight size={14} />
          </div>
          <button
            type="button"
            className={`demo-btn highlight ${isTransitionTarget ? 'active' : ''}`}
            aria-pressed={isTransitionTarget}
            onClick={() => onSelectTimestamp('20:00')}
          >
            <Sunset size={14} />
            <span>2. Allocation Change (20:00 UTC)</span>
          </button>
        </div>
      </div>

      {/* 5-step Diurnal Button Bar */}
      <div className="timeline-bar">
        {availableTimestamps.map((ts) => {
          const info = TIMESTAMP_METADATA[ts] || {
            label: `${ts} UTC`,
            edt: 'EDT',
            phase: 'Step',
            desc: '',
          };
          const isSelected = ts === currentTimestamp;
          const isSpecial = ts === '16:00' || ts === '20:00';

          return (
            <button
              key={ts}
              type="button"
              className={`timeline-step-btn ${isSelected ? 'selected' : ''} ${
                isSpecial ? 'key-state' : ''
              }`}
              aria-pressed={isSelected}
              aria-label={`${info.phase}, ${ts} UTC, ${info.edt}`}
              onClick={() => onSelectTimestamp(ts)}
            >
              <div className="step-badge">{info.phase}</div>
              <div className="step-time">{ts} UTC</div>
              <div className="step-edt">{info.edt}</div>
            </button>
          );
        })}
      </div>

      {/* Active Phase Explanation Strip */}
      <div className="timeline-status-strip">
        <div className="status-phase-indicator">
          <span className="phase-pill">{currentInfo.phase}</span>
          <span className="phase-time">{currentInfo.label} ({currentInfo.edt})</span>
        </div>
        <p className="phase-description">{currentInfo.desc}</p>
      </div>
    </div>
  );
};
