import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Sparkles,
  ShieldCheck,
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

const INTENT_LABELS: Record<IntentCode, string> = {
  ALLOCATION_SUMMARY: 'Optimal Cooling Deployment',
  DIURNAL_HEAT_TRANSITION: 'Diurnal Heat Transition',
  HEAT_VULNERABILITY_EXPLANATION: 'Facility Thermal & Population Evidence',
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
    title: 'Planning Grounded Evidence',
    desc: 'The deterministic planner assembles mandatory claims; optional AI may organize them',
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
  if (claimId.includes(':profile')) return 'Facility Evidence';
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
  const briefControllerRef = useRef<AbortController | null>(null);

  const facilityMap = useMemo(
    () => Object.fromEntries(facilities.map((f) => [f.facility_id, f])),
    [facilities]
  );

  const unselectedFacilityIds = useMemo(
    () => facilities.map((facility) => facility.facility_id).filter(
      (facilityId) => !selectedFacilityIds.includes(facilityId)
    ),
    [facilities, selectedFacilityIds]
  );
  const comparisonSelectedId = selectedFacilityIds.includes('DC_135')
    ? 'DC_135'
    : selectedFacilityIds.includes('DC_148')
    ? 'DC_148'
    : selectedFacilityIds[0];
  const comparisonAlternativeId =
    comparisonSelectedId === 'DC_135' && unselectedFacilityIds.includes('DC_148')
      ? 'DC_148'
      : comparisonSelectedId === 'DC_148' && unselectedFacilityIds.includes('DC_135')
      ? 'DC_135'
      : unselectedFacilityIds[0];

  const primaryPrompts = useMemo(
    () => [
      {
        text: 'What changed in the prepared thermal pattern between 16:00 and 20:00 UTC?',
        icon: '🌡️',
        label: 'Diurnal Thermal Shift',
      },
      {
        text: 'Where does heat-weighted demand remain unmet?',
        icon: '📍',
        label: 'Unmet Demand',
      },
      {
        text:
          comparisonSelectedId && comparisonAlternativeId
            ? `Why was ${comparisonSelectedId} selected instead of ${comparisonAlternativeId} at ${currentTimestamp} UTC?`
            : 'Why were the current facilities selected?',
        icon: '⚖️',
        label: 'Facility Trade-off Rationale',
      },
      {
        text: 'Summarize the thermal-priority and population evidence for this allocation.',
        icon: '📋',
        label: 'Evidence-Based Heat Brief',
      },
    ],
    [comparisonAlternativeId, comparisonSelectedId, currentTimestamp]
  );

  const secondaryPrompts = useMemo(
    () => [
      comparisonSelectedId
        ? `Why is ${comparisonSelectedId} selected at ${currentTimestamp} UTC?`
        : 'Why are the current facilities selected?',
      'Compare dynamic allocation against the static baseline',
      'What does the K=3 constraint change?',
    ],
    [comparisonSelectedId, currentTimestamp]
  );

  useEffect(() => {
    briefControllerRef.current?.abort();
    setBrief(null);
    setError(null);
    setLoading(false);
    return () => briefControllerRef.current?.abort();
  }, [currentTimestamp]);

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

  const handleSubmit = async (queryText?: string) => {
    const textToSubmit = (queryText !== undefined ? queryText : question).trim();
    if (!textToSubmit || loading) return;

    // A prior answer belongs to a different question; remove it before exposing
    // the new request's progress state so stale evidence cannot be misread.
    setBrief(null);
    setLoading(true);
    setError(null);
    briefControllerRef.current?.abort();
    const controller = new AbortController();
    briefControllerRef.current = controller;

    try {
      const response = await fetchHeatBrief(
        {
          question: textToSubmit,
          timestamp: currentTimestamp,
          baseline_timestamp: '16:00',
          radius_meters: 750,
          k: selectedFacilityIds.length || 3,
        },
        controller.signal
      );
      if (controller.signal.aborted) return;
      setBrief(response);
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to generate heat intelligence brief. Please verify backend service.'
      );
    } finally {
      if (!controller.signal.aborted) setLoading(false);
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
            <span className="heat-intel-title">Allocation Evidence Q&amp;A</span>
          </div>

          {brief && (
            <div className="heat-intel-status-bar">
              {brief.status === 'AI_GENERATED' ? (
                <span className="badge-ai-mode mode-ai font-mono">
                  <Sparkles size={11} className="inline-icon" /> AI-Organized Evidence
                </span>
              ) : brief.status === 'UNSUPPORTED' ? (
                <span className="badge-ai-mode mode-fallback font-mono">
                  <ShieldCheck size={11} className="inline-icon" /> Scope Boundary
                </span>
              ) : (
                <span className="badge-ai-mode mode-fallback font-mono">
                  <ShieldCheck size={11} className="inline-icon" /> Verified Deterministic Brief
                </span>
              )}
              {brief.intent_code ? (
                <span className="badge-intent font-mono">
                  {INTENT_LABELS[brief.intent_code] || brief.intent_code}
                </span>
              ) : (
                <span className="badge-intent font-mono">OUT OF SCOPE</span>
              )}
            </div>
          )}
        </div>

        <p className="heat-intel-subhead">
          Optional AI routes questions and organizes server-validated claims from prepared
          FortyGuard and Census evidence. The deterministic optimizer remains the sole
          authoritative allocation engine.
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
            Prepared FortyGuard 100m cells provide observed physical temperature values.
          </span>
        </div>

        <div className="evidence-source-card">
          <div className="evidence-source-header">
            <Users size={14} className="text-sky" />
            <span className="evidence-source-label">RESIDENTIAL POPULATION</span>
          </div>
          <span className="evidence-source-value font-mono">
            {metrics
              ? `${metrics.covered_population.toLocaleString()} / ${metrics.total_population.toLocaleString()}`
              : '—'}
          </span>
          <span className="evidence-source-sub">
            2020 Census counts provide the population term in heat-weighted demand.
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
            Deterministic optimization selects the authoritative facility set.
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
            Baseline comparison quantifies differences under the same K constraint.
          </span>
        </div>
      </div>

      {/* Quick Inquiries Toolbar */}
      <div className="heat-inquiries-toolbar">
        <span className="toolbar-heading">Evidence Inquiries:</span>
        <div className="inquiry-chips-row">
          {primaryPrompts.map((item) => (
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
          {secondaryPrompts.map((promptText) => (
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
            placeholder="Ask about temperatures, population coverage, K=3, facilities, or baseline trade-offs..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={loading}
            aria-label="CoolAccess allocation evidence inquiry"
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

      {/* Conceptual server workflow with a real elapsed-request timer. */}
      {loading && (
        <div className="heat-intel-loading-stepper">
          <div className="stepper-header-row">
            <div className="stepper-title-group" role="status" aria-live="polite">
              <span className="stepper-pulse-dot" aria-hidden="true" />
              <span className="stepper-title">Preparing Grounded Temperature Brief</span>
            </div>
            <div className="stepper-timer-badge font-mono">
              <Clock size={12} aria-hidden="true" />
              <span>Elapsed: {elapsedSeconds.toFixed(1)}s</span>
            </div>
          </div>

          <div className="stepper-stages-list">
            <span className="stepper-context-label">
              Conceptual server workflow · exact live stage is not reported
            </span>
            {LOADING_STAGES.map((stage) => (
              <div key={stage.id} className="stepper-stage-item">
                <div className="stage-icon-col">
                  <div className="stage-icon dot" aria-hidden="true" />
                </div>
                <div className="stage-text-col">
                  <span className="stage-name">{stage.title}</span>
                  <span className="stage-desc">{stage.desc}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="stepper-safety-note">
            <span>
              🛡️ Factual claims are rendered from server-validated deterministic evidence. The
              timer reports elapsed request time, not backend stage completion.
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
          {/* Deterministic Fallback Authority Notice */}
          {brief.status === 'DETERMINISTIC_FALLBACK' && (
            <div className="heat-fallback-notice">
              <ShieldCheck size={20} className="fallback-shield-icon text-emerald" />
              <div className="fallback-text">
                <div className="fallback-headline">
                  <strong>Verified deterministic brief</strong>
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

          {/* Operational Scope Notice */}
          {brief.status === 'UNSUPPORTED' && (
            <div className="heat-fallback-notice">
              <ShieldCheck size={20} className="fallback-shield-icon text-amber" />
              <div className="fallback-text">
                <div className="fallback-headline">
                  <strong>Operational Scope Boundary</strong>
                </div>
                <div className="fallback-sub">
                  This inquiry is outside the operational scope of municipal cooling center spatial optimization.
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
                  {brief.status === 'AI_GENERATED'
                    ? 'AI-ORGANIZED GROUNDED EVIDENCE'
                    : brief.status === 'UNSUPPORTED'
                    ? 'SCOPE BOUNDARY'
                    : 'AUTHORITATIVE EVIDENCE BRIEF'}
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
