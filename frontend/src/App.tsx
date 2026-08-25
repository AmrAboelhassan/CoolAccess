import { useState, useEffect, useCallback, useRef } from 'react';
import {
  ScenarioResponse,
  AllocationResponse,
  GeoJSONFeatureCollection,
  Facility,
} from './types';
import { fetchScenario, fetchAllocation, fetchGeoJSON } from './api/client';
import { Header } from './components/Header';
import { TimelineControl } from './components/TimelineControl';
import { MapView } from './components/MapView';
import { ThermalLegend } from './components/ThermalLegend';
import { MetricsSummary } from './components/MetricsSummary';
import { FacilityList } from './components/FacilityList';
import { HeatIntelligencePanel } from './components/HeatIntelligencePanel';
import { BaselineComparison } from './components/BaselineComparison';
import { ReplacementDrawer } from './components/ReplacementDrawer';
import { DisclosuresFooter } from './components/DisclosuresFooter';
import { ProcessingOverlay } from './components/ProcessingOverlay';
import { AllocationImpactStrip } from './components/AllocationImpactStrip';
import './App.css';

export function App() {
  const [scenario, setScenario] = useState<ScenarioResponse | null>(null);
  const [currentTimestamp, setCurrentTimestamp] = useState<string>('16:00');
  const [allocation, setAllocation] = useState<AllocationResponse | null>(null);
  const [thermalGeoJSON, setThermalGeoJSON] = useState<GeoJSONFeatureCollection | null>(null);
  const [aoiGeoJSON, setAoiGeoJSON] = useState<GeoJSONFeatureCollection | null>(null);
  const [facilities, setFacilities] = useState<Facility[]>([]);

  // Map layer controls
  const [showThermalGrid, setShowThermalGrid] = useState<boolean>(true);
  const [showCatchments, setShowCatchments] = useState<boolean>(true);
  const [showAOI, setShowAOI] = useState<boolean>(true);
  const [focusedFacilityId, setFocusedFacilityId] = useState<string | null>(null);

  // Loading & error state
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showProcessingOverlay, setShowProcessingOverlay] = useState<boolean>(true);
  const requestGenerationRef = useRef<number>(0);
  const activeRequestControllerRef = useRef<AbortController | null>(null);

  // Unified atomic data loader
  const loadData = useCallback(async (timestamp: string, isInitial: boolean = false) => {
    const requestGeneration = requestGenerationRef.current + 1;
    requestGenerationRef.current = requestGeneration;
    activeRequestControllerRef.current?.abort();
    const controller = new AbortController();
    activeRequestControllerRef.current = controller;

    try {
      setLoading(true);
      setError(null);
      if (!isInitial) {
        // Never label prior timestamp results as the newly requested timestamp.
        setAllocation(null);
        setThermalGeoJSON(null);
      }

      if (isInitial) {
        const [scenarioData, allocData, geoData] = await Promise.all([
          fetchScenario(controller.signal),
          fetchAllocation(timestamp, '16:00', 750, 3, controller.signal),
          fetchGeoJSON('all', timestamp, controller.signal),
        ]);

        if (requestGeneration !== requestGenerationRef.current) return;
        setScenario(scenarioData);
        setFacilities(scenarioData.candidate_facilities || []);
        setAllocation(allocData);

        const geoObj = geoData as Record<string, GeoJSONFeatureCollection>;
        if (geoObj.thermal) setThermalGeoJSON(geoObj.thermal);
        if (geoObj.aoi) setAoiGeoJSON(geoObj.aoi);
      } else {
        const [allocData, geoData] = await Promise.all([
          fetchAllocation(timestamp, '16:00', 750, 3, controller.signal),
          fetchGeoJSON('all', timestamp, controller.signal),
        ]);

        if (requestGeneration !== requestGenerationRef.current) return;
        setAllocation(allocData);

        const geoObj = geoData as Record<string, GeoJSONFeatureCollection>;
        if (geoObj.thermal) setThermalGeoJSON(geoObj.thermal);
        if (geoObj.aoi) setAoiGeoJSON(geoObj.aoi);
      }

    } catch (err: unknown) {
      if (controller.signal.aborted || requestGeneration !== requestGenerationRef.current) {
        return;
      }
      console.error('Failed to load CoolAccess dashboard data:', err);
      setError(err instanceof Error ? err.message : 'Error updating dashboard state');
      setShowProcessingOverlay(false);
    } finally {
      if (requestGeneration === requestGenerationRef.current) {
        setLoading(false);
      }
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadData('16:00', true);
    return () => activeRequestControllerRef.current?.abort();
  }, [loadData]);

  const handleSelectTimestamp = (ts: string) => {
    if (ts === currentTimestamp) return;
    setCurrentTimestamp(ts);
    loadData(ts, false);
  };

  const handleSelectFacility = (id: string) => {
    setFocusedFacilityId(id);
  };

  const displayedTimestamp = allocation?.timestamp || currentTimestamp;

  return (
    <div className="app-layout">
      {/* Header & Scenario Context */}
      <Header scenario={scenario} currentTimestamp={displayedTimestamp} />

      {/* Diurnal Timeline Switcher */}
      <TimelineControl
        currentTimestamp={currentTimestamp}
        onSelectTimestamp={handleSelectTimestamp}
        availableTimestamps={scenario?.available_timestamps_utc || ['14:00', '16:00', '18:00', '20:00', '22:00']}
      />

      <AllocationImpactStrip
        allocation={allocation}
        facilities={facilities}
        currentTimestamp={displayedTimestamp}
        onSelectTimestamp={handleSelectTimestamp}
        primaryTransition={scenario?.primary_transition}
      />

      {error && (
        <div className="app-error-banner">
          <span>⚠️ {error}</span>
          <button
            type="button"
            onClick={() => loadData(currentTimestamp, scenario === null)}
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* Main Operational Dashboard Grid */}
      <main className="dashboard-main-grid">
        {/* Left Column: Interactive GIS Map & Thermal Legend */}
        <section className="map-panel-column">
          <div className="map-panel-card">
            <div className="panel-inner-header">
              <span className="panel-indicator-pill">GEOSPATIAL DECISION CANVAS</span>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                {loading && <span className="system-pill" style={{ color: '#f59e0b', borderColor: '#f59e0b' }}>SYNCHRONIZING...</span>}
                <span className="map-active-badge">
                  {allocation
                    ? `Active Dataset: ${allocation.timestamp} UTC`
                    : `Loading Dataset: ${currentTimestamp} UTC`}
                </span>
              </div>
            </div>

            <MapView
              facilities={facilities}
              allocation={allocation}
              thermalGeoJSON={thermalGeoJSON}
              aoiGeoJSON={aoiGeoJSON}
              showThermalGrid={showThermalGrid}
              showCatchments={showCatchments}
              showAOI={showAOI}
              selectedFacilityId={focusedFacilityId}
              onSelectFacility={handleSelectFacility}
            />

            <ThermalLegend
              showThermalGrid={showThermalGrid}
              setShowThermalGrid={setShowThermalGrid}
              showCatchments={showCatchments}
              setShowCatchments={setShowCatchments}
              showAOI={showAOI}
              setShowAOI={setShowAOI}
            />
          </div>
        </section>

        {/* Right Column: Performance Metrics & Facility Allocation Cards */}
        <section className="decision-panel-column">
          <MetricsSummary
            metrics={allocation?.coverage_metrics || null}
            selectedCount={allocation?.selected_facility_ids.length || 0}
            budgetK={scenario?.resource_budget_k || 3}
            tieBreakCriterion={allocation?.tie_break.decisive_criterion}
            combinationsEvaluated={allocation?.tie_break.evaluated_combination_count}
          />

          <FacilityList
            facilities={facilities}
            selectedFacilityIds={allocation?.selected_facility_ids || []}
            selectedDetails={allocation?.selected_facilities || []}
            currentSelectedId={focusedFacilityId}
            onSelectFacility={handleSelectFacility}
          />
        </section>
      </main>

      {/* Temperature AI Decision Intelligence Layer & Municipal Heat Analyst */}
      <section className="dashboard-section">
        <HeatIntelligencePanel
          currentTimestamp={displayedTimestamp}
          facilities={facilities}
          metrics={allocation?.coverage_metrics || null}
          selectedFacilityIds={allocation?.selected_facility_ids || []}
          onSelectFacility={handleSelectFacility}
        />
      </section>

      {/* Bottom Proof Section: Baseline Comparison */}
      <section className="dashboard-section">
        <BaselineComparison
          dynamicObjective={allocation?.coverage_metrics.covered_heat_weighted_demand || 0}
          dynamicPopulation={allocation?.coverage_metrics.covered_population || 0}
          dynamicFacilities={allocation?.selected_facility_ids || []}
          staticBaseline={allocation?.static_baseline || null}
          naiveBaseline={allocation?.naive_baseline || null}
          currentTimestamp={displayedTimestamp}
        />
      </section>

      {/* Bottom Proof Section: 1-for-1 Replacement Evidence */}
      <section className="dashboard-section">
        <ReplacementDrawer
          currentTimestamp={displayedTimestamp}
          facilities={facilities}
          selectedFacilityIds={allocation?.selected_facility_ids || []}
        />
      </section>

      {/* Disclosures & Provenance Footer */}
      <DisclosuresFooter scenario={scenario} />

      {/* Staged Temperature AI Processing Experience for Demo */}
      {showProcessingOverlay && !error && (
        <ProcessingOverlay
          isDataReady={!loading && scenario !== null && allocation !== null}
          onComplete={() => setShowProcessingOverlay(false)}
        />
      )}
    </div>
  );
}

export default App;
