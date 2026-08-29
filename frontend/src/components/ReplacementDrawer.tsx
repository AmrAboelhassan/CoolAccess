import React, { useState, useEffect } from 'react';
import { ArrowLeftRight, Info, ChevronDown } from 'lucide-react';
import { ReplacementResponse, Facility } from '../types';
import { fetchReplacement } from '../api/client';

interface ReplacementDrawerProps {
  currentTimestamp: string;
  facilities: Facility[];
  selectedFacilityIds: string[];
}

export const ReplacementDrawer: React.FC<ReplacementDrawerProps> = ({
  currentTimestamp,
  facilities,
  selectedFacilityIds,
}) => {
  const [replacementData, setReplacementData] = useState<ReplacementResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSet = React.useMemo(() => new Set(selectedFacilityIds), [selectedFacilityIds]);
  const unselectedFacilityIds = React.useMemo(
    () => facilities.map((f) => f.facility_id).filter((id) => !selectedSet.has(id)),
    [facilities, selectedSet]
  );

  const [selectedId, setSelectedId] = useState<string>('');
  const [unselectedId, setUnselectedId] = useState<string>('');

  // Sync valid selected and unselected IDs whenever allocation changes
  useEffect(() => {
    if (selectedFacilityIds.length > 0 && unselectedFacilityIds.length > 0) {
      let nextSel = selectedId;
      if (!nextSel || !selectedSet.has(nextSel)) {
        nextSel = selectedFacilityIds.includes('DC_135')
          ? 'DC_135'
          : selectedFacilityIds.includes('DC_148') && unselectedFacilityIds.includes('DC_135')
          ? 'DC_148'
          : selectedFacilityIds[0];
      }

      let nextUnsel = unselectedId;
      if (!nextUnsel || !unselectedFacilityIds.includes(nextUnsel)) {
        nextUnsel = unselectedFacilityIds.includes('DC_148')
          ? 'DC_148'
          : nextSel === 'DC_148' && unselectedFacilityIds.includes('DC_135')
          ? 'DC_135'
          : unselectedFacilityIds[0];
      }

      setSelectedId(nextSel);
      setUnselectedId(nextUnsel);
    }
  }, [selectedFacilityIds, unselectedFacilityIds, selectedSet]);

  // Fetch replacement ONLY when valid selected and unselected IDs exist
  useEffect(() => {
    if (
      !selectedId ||
      !unselectedId ||
      !selectedSet.has(selectedId) ||
      !unselectedFacilityIds.includes(unselectedId)
    ) {
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    fetchReplacement(currentTimestamp, selectedId, unselectedId, 750, 3, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setReplacementData(data);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : 'Failed to load replacement evidence');
          setLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [currentTimestamp, selectedId, unselectedId, selectedSet, unselectedFacilityIds]);

  const primary = replacementData?.primary_replacement;

  return (
    <div className="replacement-drawer-panel">
      <div className="drawer-header-row">
        <div className="drawer-title-group">
          <ArrowLeftRight size={18} className="text-sky" />
          <div>
            <h3 className="section-title">Deterministic Replacement Evidence</h3>
            <p className="section-subtitle">
              The optimizer computes each one-for-one substitution. The AI inquiry panel can organize these authoritative claims for natural-language questions.
            </p>
          </div>
        </div>
      </div>

      {/* Interactive Pair Selector */}
      <div className="replacement-controls-bar">
        <div className="select-group">
          <label className="select-label">Optimal Selected Facility:</label>
          <div className="custom-select-wrapper">
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="fac-dropdown selected"
            >
              {selectedFacilityIds.map((id) => {
                const fac = facilities.find((f) => f.facility_id === id);
                return (
                  <option key={id} value={id}>
                    {id} — {fac?.name || id}
                  </option>
                );
              })}
            </select>
            <ChevronDown size={14} className="select-chevron" />
          </div>
        </div>

        <div className="swap-indicator">
          <ArrowLeftRight size={16} className="text-muted" />
          <span className="swap-text">VS</span>
        </div>

        <div className="select-group">
          <label className="select-label">Unselected Alternative Facility:</label>
          <div className="custom-select-wrapper">
            <select
              value={unselectedId}
              onChange={(e) => setUnselectedId(e.target.value)}
              className="fac-dropdown unselected"
            >
              {unselectedFacilityIds.map((id) => {
                const fac = facilities.find((f) => f.facility_id === id);
                return (
                  <option key={id} value={id}>
                    {id} — {fac?.name || id}
                  </option>
                );
              })}
            </select>
            <ChevronDown size={14} className="select-chevron" />
          </div>
        </div>
      </div>

      {/* Replacement Analysis Result Cards */}
      {loading ? (
        <div className="drawer-loading-box">Loading deterministic replacement evidence...</div>
      ) : error ? (
        <div className="drawer-error-box">{error}</div>
      ) : primary ? (
        <div className="replacement-content-grid">
          {/* Metrics comparison */}
          <div className="rep-metrics-box">
            <div className="rep-metric-row highlight-loss">
              <span className="rep-metric-label">Primary Objective Loss:</span>
              <span className="rep-metric-val loss">
                -{primary.primary_objective_loss.toFixed(2)} Demand Units
              </span>
            </div>

            <div className="rep-metric-row">
              <span className="rep-metric-label">2020 Census Population Delta:</span>
              <span className="rep-metric-val">
                {primary.population_delta > 0
                  ? `+${primary.population_delta.toLocaleString()} Residents`
                  : primary.population_delta < 0
                  ? `-${Math.abs(primary.population_delta).toLocaleString()} Residents (${Math.abs(primary.population_delta).toLocaleString()} fewer)`
                  : '0 Residents Delta'}
              </span>
            </div>

            <div className="rep-metric-row">
              <span className="rep-metric-label">Optimal Set Objective:</span>
              <span className="rep-metric-val">{primary.original_objective.toFixed(2)}</span>
            </div>

            <div className="rep-metric-row">
              <span className="rep-metric-label">Substituted Set Objective:</span>
              <span className="rep-metric-val text-muted">{primary.replacement_objective.toFixed(2)}</span>
            </div>

            <div className="rep-metric-row">
              <span className="rep-metric-label">Decisive Reason Code:</span>
              <span className="rep-code-tag">{primary.reason_code}</span>
            </div>
          </div>

          {/* Authoritative deterministic explanation */}
          <div className="rep-explanation-box">
            <div className="explanation-header">
              <Info size={16} className="text-sky" />
              <span className="exp-heading">Authoritative Replacement Comparison</span>
            </div>

            <p className="exp-paragraph">{primary.explanation}</p>

            <div className="exp-takeaway">
              <strong>Objective definition:</strong> CoolAccess multiplies 2020 Census population by a normalized thermal-priority weight, then maximizes union coverage under the fixed K=3 facility-count budget and 750m geodesic centroid catchment rule (candidate facilities are treated as equally eligible; facility hours and service capacities are not modeled).
            </div>
          </div>
        </div>
      ) : (
        <div className="drawer-loading-box">Select a valid facility pair to load deterministic evidence.</div>
      )}
    </div>
  );
};
