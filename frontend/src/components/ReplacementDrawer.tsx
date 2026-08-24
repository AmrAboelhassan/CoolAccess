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

  const selectedSet = new Set(selectedFacilityIds);
  const unselectedFacilityIds = facilities
    .map((f) => f.facility_id)
    .filter((id) => !selectedSet.has(id));

  const [selectedId, setSelectedId] = useState<string>(
    selectedFacilityIds.includes('DC_135') ? 'DC_135' : (selectedFacilityIds[0] || 'DC_089')
  );
  const [unselectedId, setUnselectedId] = useState<string>(
    unselectedFacilityIds.includes('DC_148') ? 'DC_148' : (unselectedFacilityIds[0] || 'DC_148')
  );

  // Sync default facility ids when timestamp/allocation changes
  useEffect(() => {
    if (selectedFacilityIds.length > 0) {
      const defaultSel = selectedFacilityIds.includes('DC_135')
        ? 'DC_135'
        : selectedFacilityIds[0];
      const defaultUnsel = unselectedFacilityIds.includes('DC_148')
        ? 'DC_148'
        : unselectedFacilityIds[0] || '';

      setSelectedId(defaultSel);
      if (defaultUnsel) setUnselectedId(defaultUnsel);
    }
  }, [selectedFacilityIds.join(',')]);

  useEffect(() => {
    if (!selectedId || !unselectedId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    fetchReplacement(currentTimestamp, selectedId, unselectedId)
      .then((data) => {
        if (isMounted) {
          setReplacementData(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load replacement evidence');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [currentTimestamp, selectedId, unselectedId]);

  const primary = replacementData?.primary_replacement;

  return (
    <div className="replacement-drawer-panel">
      <div className="drawer-header-row">
        <div className="drawer-title-group">
          <ArrowLeftRight size={18} className="text-sky" />
          <div>
            <h3 className="section-title">1-for-1 Facility Replacement Evidence & Decision Logic</h3>
            <p className="section-subtitle">
              Inspect why replacing an optimally selected facility with an alternative reduces protected heat demand.
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
        <div className="drawer-loading-box">Computing 1-for-1 replacement evidence...</div>
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
              <span className="rep-metric-label">Raw 2020 Census Population Delta:</span>
              <span className="rep-metric-val">
                {primary.population_delta > 0 ? `+${primary.population_delta.toLocaleString()}` : primary.population_delta.toLocaleString()} Residents
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

          {/* Physical Mechanism & Explanation */}
          <div className="rep-explanation-box">
            <div className="explanation-header">
              <Info size={16} className="text-sky" />
              <span className="exp-heading">Empirical Physical Mechanism</span>
            </div>

            <p className="exp-paragraph">{primary.explanation}</p>

            <div className="exp-takeaway">
              <strong>Key Municipal Takeaway:</strong> High residential headcounts in tree-canopied zones (e.g. Northeast Library) cool down quickly in late afternoon ($w \approx 0.06$). Meanwhile, downtown commercial masonry retaining thermal mass ($w \approx 0.22$) generates over $3\times$ higher urgent heat protection demand per resident.
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};
