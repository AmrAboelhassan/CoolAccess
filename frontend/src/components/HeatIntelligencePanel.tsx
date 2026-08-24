import React, { useMemo, useRef, useState } from 'react';
import { fetchHeatBrief } from '../api/client';
import {
  HeatBriefResponse,
  BriefItem,
  IntentCode,
  Facility,
  CoverageMetrics,
} from '../types';

interface HeatIntelligencePanelProps {
  currentTimestamp: string;
  facilities: Facility[];
  metrics: CoverageMetrics | null;
  selectedFacilityIds: string[];
  onSelectFacility?: (facilityId: string) => void;
}

const PRIMARY_PROMPTS = [
  {
    text: 'What changed in thermal exposure between 16:00 and 20:00 UTC?',
    icon: '🌡️',
    label: 'Diurnal Thermal Shift',
  },
  {
    text: 'Which areas combine high heat exposure and population density?',
    icon: '📍',
    label: 'Vulnerability Hotspots',
  },
  {
    text: 'Why was DC_148 rejected in favor of DC_135?',
    icon: '⚖️',
    label: 'Facility Trade-off Rationale',
  },
  {
    text: 'Summarize the heat vulnerability of this scenario.',
    icon: '📋',
    label: 'Evidence-Based Heat Brief',
  },
];

const SECONDARY_PROMPTS = [
  'Why is this facility important from a thermal perspective?',
  'Compare dynamic allocation against static 16:00 baseline',
  'Explain tie-breaking criterion for current optimal selection',
];

const INTENT_LABELS: Record<IntentCode, string> = {
  ALLOCATION_SUMMARY: 'Optimal Cooling Deployment',
  DIURNAL_HEAT_TRANSITION: 'Diurnal Heat Transition',
  HEAT_VULNERABILITY_EXPLANATION: 'Heat Vulnerability Explanation',
  REPLACEMENT_RATIONALE: 'Facility Trade-off Rationale',
  BASELINE_COMPARISON: 'Baseline Comparison Analysis',
};

export const HeatIntelligencePanel: React.FC<HeatIntelligencePanelProps> = ({
  currentTimestamp,
  facilities,
  metrics,
  selectedFacilityIds,
  onSelectFacility,
}) => {
  const [question, setQuestion] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [brief, setBrief] = useState<HeatBriefResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSecondaryPrompts, setShowSecondaryPrompts] = useState<boolean>(false);
  const [auditOpen, setAuditOpen] = useState<boolean>(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const facilityMap = useMemo(
    () => Object.fromEntries(facilities.map((f) => [f.facility_id, f])),
    [facilities]
  );

  const handleSubmit = async (queryText?: string) => {
    const textToSubmit = (queryText !== undefined ? queryText : question).trim();
    if (!textToSubmit || loading) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetchHeatBrief({
        question: textToSubmit,
        timestamp: currentTimestamp,
        baseline_timestamp: '16:00',
        radius_meters: 750,
        k: selectedFacilityIds.length || 3,
      });
      setBrief(response);
    } catch (err: any) {
      setError(
        err.message || 'Failed to generate heat intelligence brief. Please verify backend service.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handlePromptClick = (promptText: string) => {
    setQuestion(promptText);
    handleSubmit(promptText);
  };

  // Group and categorize brief items
  const { leadItem, detailItems, identifiedFacilityId } = useMemo(() => {
    if (!brief || brief.brief_items.length === 0) {
      return { leadItem: null, detailItems: [], identifiedFacilityId: null };
    }

    let lead: BriefItem | null = null;
    const details: BriefItem[] = [];
    let facId: string | null = null;

    for (const item of brief.brief_items) {
      const cid = item.claim_id;
      if (
        !lead &&
        (cid.includes(':loss') ||
          cid.includes(':transition') ||
          cid.includes(':summary') ||
          cid.includes(':profile') ||
          cid.includes(':gain'))
      ) {
        lead = item;
      } else {
        details.push(item);
      }

      if (item.facility_id && !facId) {
        facId = item.facility_id;
      }
    }

    if (!lead && brief.brief_items.length > 0) {
      lead = brief.brief_items[0];
    }

    if (!facId && brief.requested_highlights.length === 1) {
      facId = brief.requested_highlights[0];
    }

    return { leadItem: lead, detailItems: details, identifiedFacilityId: facId };
  }, [brief]);

  const focusedFacility = identifiedFacilityId ? facilityMap[identifiedFacilityId] : null;

  return (
    <div className="heat-intelligence-module">
      {/* Module Header Bar */}
      <div className="heat-intel-header">
        <div className="heat-intel-brand">
          <span className="heat-intel-pulse-dot" aria-hidden="true">●</span>
          <span className="heat-intel-title">Temperature AI Intelligence Layer</span>
        </div>

        <p className="heat-intel-subhead">
          Evidence-grounded thermal vulnerability insights & municipal decision support.
          Read-only projection over deterministic optimizer.
        </p>

        {brief && (
          <div className="heat-intel-status-bar">
            {brief.status === 'AI_GENERATED' ? (
              <span className="badge-ai-mode mode-ai font-mono">AI_GENERATED</span>
            ) : (
              <span className="badge-ai-mode mode-fallback font-mono">DETERMINISTIC_FALLBACK</span>
            )}
            <span className="badge-intent font-mono">
              {INTENT_LABELS[brief.intent_code] || brief.intent_code}
            </span>
          </div>
        )}
      </div>

      {/* Top 3 Scenario Thermal & Vulnerability Summary Badges */}
      <div className="heat-summary-cards-grid">
        <div className="heat-metric-pill">
          <span className="pill-label">SCENARIO THERMAL EXPOSURE</span>
          <span className="pill-value font-mono">
            {currentTimestamp === '16:00'
              ? 'Peak Heat (37.7°C max)'
              : currentTimestamp === '20:00'
              ? 'Evening Heat (35.1°C max)'
              : `${currentTimestamp} UTC Snapshot`}
          </span>
          <span className="pill-subtext">FortyGuard 100m TCM Grid</span>
        </div>

        <div className="heat-metric-pill">
          <span className="pill-label">POPULATION VULNERABILITY</span>
          <span className="pill-value font-mono">
            {metrics ? `${metrics.covered_population.toLocaleString()} / ${metrics.total_population.toLocaleString()}` : '—'}
          </span>
          <span className="pill-subtext">Residents in High-Heat Blocks</span>
        </div>

        <div className="heat-metric-pill">
          <span className="pill-label">COOLING COVERAGE</span>
          <span className="pill-value font-mono">
            {metrics ? `${metrics.coverage_percentage.toFixed(1)}% Demand` : '—'}
          </span>
          <span className="pill-subtext">k={selectedFacilityIds.length || 3} Optimal Shelters</span>
        </div>
      </div>

      {/* Quick Inquiries Toolbar */}
      <div className="heat-inquiries-toolbar">
        <span className="toolbar-heading">Temperature AI Inquiries:</span>
        <div className="inquiry-chips-row">
          {PRIMARY_PROMPTS.map((item) => (
            <button
              key={item.text}
              type="button"
              className="btn-inquiry-chip"
              disabled={loading}
              onClick={() => handlePromptClick(item.text)}
            >
              <span className="chip-icon">{item.icon}</span>
              <span className="chip-label">{item.label}</span>
            </button>
          ))}

          <button
            type="button"
            className="btn-more-chips"
            onClick={() => setShowSecondaryPrompts(!showSecondaryPrompts)}
            aria-expanded={showSecondaryPrompts}
          >
            <span>{showSecondaryPrompts ? 'Less' : 'More Inquiries'}</span>
            <span className="toggle-arrow">{showSecondaryPrompts ? '▲' : '▼'}</span>
          </button>
        </div>
      </div>

      {/* Secondary Inquiries Expansion */}
      {showSecondaryPrompts && (
        <div className="secondary-inquiries-drawer">
          {SECONDARY_PROMPTS.map((promptText) => (
            <button
              key={promptText}
              type="button"
              className="btn-secondary-chip"
              disabled={loading}
              onClick={() => handlePromptClick(promptText)}
            >
              {promptText}
            </button>
          ))}
        </div>
      )}

      {/* Command Input Form */}
      <form
        className="heat-intel-form"
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit();
        }}
      >
        <div className="heat-input-dock">
          <span className="dock-prefix font-mono">❯</span>
          <input
            ref={inputRef}
            type="text"
            className="heat-intel-input"
            placeholder="Ask about thermal exposure changes, facility vulnerability, or allocation trade-offs..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={loading}
            aria-label="Temperature AI Municipal Inquiry"
          />
          <button
            type="submit"
            className="btn-submit-intel"
            disabled={loading || !question.trim()}
          >
            {loading ? (
              <>
                <span className="intel-spinner" aria-hidden="true" />
                <span>Analyzing Heat Intelligence…</span>
              </>
            ) : (
              <span>Analyze Heat</span>
            )}
          </button>
        </div>
      </form>

      {/* Dynamic Processing Status Banner */}
      {loading && (
        <div className="heat-intel-loading-status" role="status" aria-live="polite">
          <div className="loading-pulse-ring">
            <span className="loading-pulse-core" />
          </div>
          <div className="loading-text-stack">
            <span className="loading-primary-msg">
              Temperature AI analysis may take 10-40s. Verified deterministic fallback remains available.
            </span>
            <span className="loading-secondary-msg">
              Querying FortyGuard thermal state & synthesizing evidence-grounded response…
            </span>
          </div>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="heat-intel-error" role="alert">
          <span>⚠️ {error}</span>
          <button type="button" onClick={() => handleSubmit()}>
            Retry
          </button>
        </div>
      )}

      {/* Structured Brief Response */}
      {brief && (
        <div className="heat-brief-container">
          {/* Fallback Mode Banner */}
          {brief.status === 'DETERMINISTIC_FALLBACK' && (
            <div className="heat-fallback-notice">
              <span className="fallback-shield-icon">🛡️</span>
              <div className="fallback-text">
                <strong>Deterministic mode active.</strong> Response rendered from verified
                authoritative engine facts without live AI inference; the optimizer selection and
                metrics remain unchanged.
              </div>
            </div>
          )}

          {/* AI Heat Insight Card (The 5-Second Temperature Answer) */}
          <div className="ai-heat-insight-card">
            <div className="insight-card-header">
              <div className="insight-title-group">
                <span className="insight-pill-tag">TEMPERATURE AI INSIGHT</span>
                <h4 className="insight-title">{brief.title}</h4>
              </div>

              {focusedFacility && onSelectFacility && (
                <button
                  type="button"
                  className="btn-focus-facility"
                  onClick={() => onSelectFacility(focusedFacility.facility_id)}
                >
                  <span>📍 Focus {focusedFacility.name}</span>
                </button>
              )}
            </div>

            {leadItem && <p className="insight-lead-text">{leadItem.server_rendered_text}</p>}

            {/* Additional Evidence Findings */}
            {detailItems.length > 0 && (
              <div className="insight-findings-list">
                {detailItems.map((item) => (
                  <div key={item.claim_id} className="finding-row">
                    <span className="finding-bullet">▸</span>
                    <span className="finding-text">{item.server_rendered_text}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Action Bar */}
            <div className="insight-footer-bar">
              <span className="fingerprint-tag font-mono">
                Fingerprint: {brief.plan_fingerprint.substring(0, 12)}…
              </span>

              <button
                type="button"
                className="btn-toggle-audit"
                onClick={() => setAuditOpen(!auditOpen)}
                aria-expanded={auditOpen}
              >
                <span>{auditOpen ? 'Hide Evidence Audit' : 'Inspect Evidence Audit'}</span>
                <span>{auditOpen ? '▲' : '▼'}</span>
              </button>
            </div>
          </div>

          {/* Collapsible Evidence Audit & Provenance Drawer */}
          {auditOpen && (
            <div className="evidence-audit-drawer">
              <div className="audit-section">
                <h5 className="audit-subtitle">Executed Read-Only Tools Trace</h5>
                <div className="tools-trace-tags">
                  {brief.tools_used.map((t, idx) => (
                    <span key={idx} className="tool-trace-pill font-mono">
                      {t}
                    </span>
                  ))}
                </div>
              </div>

              <div className="audit-section">
                <h5 className="audit-subtitle">Mandatory Caveats & Data Provenance</h5>
                <ul className="caveats-list">
                  {brief.mandatory_caveats.map((c, idx) => (
                    <li key={idx}>{c}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
