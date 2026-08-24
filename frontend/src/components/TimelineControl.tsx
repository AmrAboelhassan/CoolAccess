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
    phase: 'Morning Warmup',
    desc: 'Solar irradiance rises; residential and commercial thermal profiles begin diverging.',
  },
  '16:00': {
    label: '16:00 UTC (Midday Peak)',
    edt: '12:00 PM EDT',
    phase: 'NOW State',
    desc: 'Peak midday radiation. High uniform heat across AOI favors dense residential population.',
  },
  '18:00': {
    label: '18:00 UTC',
    edt: '02:00 PM EDT',
    phase: 'Early Afternoon',
    desc: 'Peak ambient air heat; localized urban geometry begins accumulating thermal lag.',
  },
  '20:00': {
    label: '20:00 UTC (Late Afternoon)',
    edt: '04:00 PM EDT',
    phase: 'Target Future Shift',
    desc: 'Differential cooling: residential tree canopies cool fast while downtown masonry retains heat.',
  },
  '22:00': {
    label: '22:00 UTC',
    edt: '06:00 PM EDT',
    phase: 'Evening Residual',
    desc: 'Evening heat release from asphalt canyons sustains downtown cooling demand.',
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
            onClick={() => onSelectTimestamp('16:00')}
          >
            <Sun size={14} />
            <span>1. Midday (16:00 UTC)</span>
          </button>
          <div className="shortcut-arrow">
            <ArrowRight size={14} />
          </div>
          <button
            type="button"
            className={`demo-btn highlight ${isTransitionTarget ? 'active' : ''}`}
            onClick={() => onSelectTimestamp('20:00')}
          >
            <Sunset size={14} />
            <span>2. Late Afternoon Shift (20:00 UTC)</span>
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
