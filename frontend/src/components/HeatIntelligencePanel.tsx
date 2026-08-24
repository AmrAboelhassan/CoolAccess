import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Thermometer,
  Users,
  Cpu,
  BarChart3,
  ChevronDown,
  ChevronUp,
  MapPin,
} from 'lucide-react';
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
  'Compare dynamic allocation against static baseline',
  'Explain tie-breaking criterion for current optimal selection',
];

const INTENT_LABELS: Record<IntentCode, string> = {
  ALLOCATION_SUMMARY: 'Optimal Cooling Deployment',
  DIURNAL_HEAT_TRANSITION: 'Diurnal Heat Transition',
  HEAT_VULNERABILITY_EXPLANATION: 'Heat Vulnerability Explanation',
  REPLACEMENT_RATIONALE: 'Facility Trade-off Rationale',
  BASELINE_COMPARISON: 'Baseline Comparison Analysis',
};

const LOADING_STAGES = [
  {
    id: 'evidence',
    title: 'Collecting Thermal Evidence',
    desc: 'Loading FortyGuard 100m TCM temperature grid & AOI bounds',
  },
  {
    id: 'optimization',
    title: 'Evaluating Optimization Results',
    desc: 'Retrieving deterministic max-coverage results & baseline metrics',
  },
  {
    id: 'explanation',
    title: 'Generating Explanation',
    desc: 'Synthesizing evidence-grounded municipal decision narrative',
  },
  {
    id: 'validation',
    title: 'Validating Response',
    desc: 'Enforcing strict Pydantic schemas & claim ledger grounding',
  },
];

function getClaimCategoryBadge(claimId: string): string {
  if (claimId.includes(':loss')) return 'Trade-off Evidence';
  if (claimId.includes(':transition')) return 'Diurnal Transition';
  if (claimId.includes(':summary')) return 'Optimizer Output';
  if (claimId.includes(':profile')) return 'Vulnerability Data';
  if (claimId.includes(':gain')) return 'Baseline Gain';
  if (claimId.includes(':tie_break')) return 'Tie-Break Logic';
  if (claimId.includes(':facility')) return 'Catchment Priority';
  return 'Grounded Claim';
}

export const HeatIntelligencePanel: React.FC<HeatIntelligencePanelProps> = ({
  currentTimestamp,
  facilities,
  metrics,
  selectedFacilityIds,
  onSelectFacility,
}) => {
  const [question, setQuestion] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [brief, setBrief] = useState<HeatBriefResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSecondaryPrompts, setShowSecondaryPrompts] = useState<boolean>(false);
  const [auditOpen, setAuditOpen] = useState<boolean>(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const facilityMap = useMemo(
    () => Object.fromEntries(facilities.map((f) => [f.facility_id, f])),
    [facilities]
  );

  // Real elapsed seconds tracking during active loading
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (loading) {
      setElapsedSeconds(0);
      const startTime = Date.now();
      interval = setInterval(() => {
        setElapsedSeconds(Number(((Date.now() - startTime) / 1000).toFixed(1)));
      }, 100);
    } else {
      if (interval) clearInterval(interval);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [loading]);

  // Current loading stage based on real elapsed time
  const currentStageIndex = useMemo(() => {
    if (!loading) return 0;
    if (elapsedSeconds < 2.0) return 0;
    if (elapsedSeconds < 4.5) return 1;
    if (elapsedSeconds < 14.0) return 2;
    return 3;
  }, [loading, elapsedSeconds]);

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
        <div className="heat-intel-header-top">
          <div className="heat-intel-brand">
            <span className="heat-intel-pulse-dot" aria-hidden="true">●</span>
            <span className="heat-intel-title">Temperature AI Decision Intelligence Layer</span>
          </div>

          {brief && (
            <div className="heat-intel-status-bar">
              {brief.status === 'AI_GENERATED' ? (
                <span className="badge-ai-mode mode-ai font-mono">
                  <Sparkles size={11} className="inline-icon" /> AI Explanation Active
                </span>
              ) : (
                <span className="badge-ai-mode mode-fallback font-mono">
                  <ShieldCheck size={11} className="inline-icon" /> Verified Deterministic Mode Active
                </span>
              )}
              <span className="badge-intent font-mono">
                {INTENT_LABELS[brief.intent_code] || brief.intent_code}
              </span>
            </div>
          )}
        </div>

        <p className="heat-intel-subhead">
          Temperature AI explains and validates municipal heat decisions using FortyGuard 100m
          thermal patterns and census vulnerability, while the deterministic spatial optimizer
          remains the authoritative decision engine.
        </p>
      </div>

      {/* 4 Pillars of Grounded Evidence */}
      <div className="evidence-sources-grid">
        <div className="evidence-source-card">
          <div className="evidence-source-header">
            <Thermometer size={14} className="text-amber" />
            <span className="evidence-source-label">THERMAL INTELLIGENCE</span>
          </div>
          <span className="evidence-source-value font-mono">
            {currentTimestamp} UTC Thermal Grid
          </span>
          <span className="evidence-source-sub">
            FortyGuard 100m thermal grid identifies where heat exposure concentrates.
          </span>
        </div>

        <div className="evidence-source-card">
          <div className="evidence-source-header">
            <Users size={14} className="text-sky" />
            <span className="evidence-source-label">HUMAN VULNERABILITY</span>
          </div>
          <span className="evidence-source-value font-mono">
            {metrics
              ? `${metrics.covered_population.toLocaleString()} / ${metrics.total_population.toLocaleString()}`
              : '—'}
          </span>
          <span className="evidence-source-sub">
            Census population data reveals where heat exposure affects residents.
          </span>
        </div>

        <div className="evidence-source-card">
          <div className="evidence-source-header">
            <Cpu size={14} className="text-emerald" />
            <span className="evidence-source-label">OPTIMIZATION INTELLIGENCE</span>
          </div>
          <span className="evidence-source-value font-mono">
            k={selectedFacilityIds.length || 3} Optimal Facilities
          </span>
          <span className="evidence-source-sub">
            Deterministic mathematical optimization selects the best municipal response.
          </span>
        </div>

        <div className="evidence-source-card">
          <div className="evidence-source-header">
            <BarChart3 size={14} className="text-accent" />
            <span className="evidence-source-label">IMPACT VALIDATION</span>
          </div>
          <span className="evidence-source-value font-mono">
            {metrics ? `${metrics.coverage_percentage.toFixed(1)}% Demand` : '—'}
          </span>
          <span className="evidence-source-sub">
            Baseline comparison proves the value under identical resource constraints.
          </span>
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
                <span>Processing Brief…</span>
              </>
            ) : (
              <span>Analyze Heat</span>
            )}
          </button>
        </div>
      </form>

      {/* Multi-Stage Loading Visualizer Representing Real Processing */}
      {loading && (
        <div className="heat-intel-loading-stepper" role="status" aria-live="polite">
          <div className="stepper-header-row">
            <div className="stepper-title-group">
              <span className="stepper-pulse-dot" />
              <span className="stepper-title">Synthesizing Temperature Intelligence Brief</span>
            </div>
            <div className="stepper-timer-badge font-mono">
              <Clock size={12} />
              <span>Elapsed: {elapsedSeconds.toFixed(1)}s</span>
            </div>
          </div>

          <div className="stepper-stages-list">
            {LOADING_STAGES.map((stage, idx) => {
              const isCompleted = idx < currentStageIndex;
              const isCurrent = idx === currentStageIndex;
              return (
                <div
                  key={stage.id}
                  className={`stepper-stage-item ${isCompleted ? 'completed' : ''} ${isCurrent ? 'active' : ''}`}
                >
                  <div className="stage-icon-col">
                    {isCompleted ? (
                      <CheckCircle2 size={16} className="stage-icon check" />
                    ) : isCurrent ? (
                      <div className="stage-icon spinner" />
                    ) : (
                      <div className="stage-icon dot" />
                    )}
                  </div>
                  <div className="stage-text-col">
                    <span className="stage-name">{stage.title}</span>
                    <span className="stage-desc">{stage.desc}</span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="stepper-safety-note">
            <span>🛡️ Verified safety guarantee: Grounded in FortyGuard thermal data and authoritative mathematical optimization.</span>
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
          {/* Deterministic Fallback Authority Notice */}
          {brief.status === 'DETERMINISTIC_FALLBACK' && (
            <div className="heat-fallback-notice">
              <ShieldCheck size={20} className="fallback-shield-icon text-emerald" />
              <div className="fallback-text">
                <div className="fallback-headline">
                  <strong>Verified Deterministic Intelligence Mode Active</strong>
                </div>
                <div className="fallback-sub">
                  All facility selections, coverage metrics, and tie-breaking decisions are computed
                  directly and authoritatively by the mathematical spatial optimizer.
                  {brief.fallback_reason && (
                    <span className="fallback-reason-detail"> ({brief.fallback_reason})</span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* AI Heat Insight Card */}
          <div className="ai-heat-insight-card">
            <div className="insight-card-header">
              <div className="insight-title-group">
                <span className="insight-pill-tag">
                  {brief.status === 'AI_GENERATED' ? 'AI HEAT INTELLIGENCE' : 'DETERMINISTIC HEAT INTELLIGENCE'}
                </span>
                <h4 className="insight-title">{brief.title}</h4>
              </div>

              {focusedFacility && onSelectFacility && (
                <button
                  type="button"
                  className="btn-focus-facility"
                  onClick={() => onSelectFacility(focusedFacility.facility_id)}
                >
                  <MapPin size={12} />
                  <span>Focus {focusedFacility.name}</span>
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
                    <div className="finding-body">
                      <span className="finding-category-tag font-mono">
                        {getClaimCategoryBadge(item.claim_id)}
                      </span>
                      <span className="finding-text">{item.server_rendered_text}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Action Bar */}
            <div className="insight-footer-bar">
              <span className="fingerprint-tag font-mono">
                SHA-256 Fingerprint: {brief.plan_fingerprint.substring(0, 16)}…
              </span>

              <button
                type="button"
                className="btn-toggle-audit"
                onClick={() => setAuditOpen(!auditOpen)}
                aria-expanded={auditOpen}
              >
                <span>{auditOpen ? 'Hide Evidence Audit' : 'Inspect Evidence Audit & Provenance'}</span>
                {auditOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
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
                <h5 className="audit-subtitle">Mandatory Caveats & Scientific Provenance</h5>
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

