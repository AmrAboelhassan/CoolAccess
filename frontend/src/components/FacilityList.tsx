import React from 'react';
import { ShieldCheck, ShieldAlert, MapPin, Eye } from 'lucide-react';
import { Facility, SelectedFacilityDetail } from '../types';

interface FacilityListProps {
  facilities: Facility[];
  selectedFacilityIds: string[];
  selectedDetails: SelectedFacilityDetail[];
  currentSelectedId: string | null;
  onSelectFacility: (id: string) => void;
}

export const FacilityList: React.FC<FacilityListProps> = ({
  facilities,
  selectedFacilityIds,
  selectedDetails,
  currentSelectedId,
  onSelectFacility,
}) => {
  const selectedSet = new Set(selectedFacilityIds);

  const activeFacilities = facilities.filter((f) => selectedSet.has(f.facility_id));
  const inactiveFacilities = facilities.filter((f) => !selectedSet.has(f.facility_id));

  if (facilities.length === 0 || selectedFacilityIds.length === 0) {
    return (
      <div className="facility-list-panel">
        <div className="facility-panel-header">
          <h3 className="section-title">Facility Allocation Status</h3>
          <span className="allocation-count-tag">Synchronizing...</span>
        </div>
        <div className="drawer-loading-box">
          Awaiting optimization results & facility allocation...
        </div>
      </div>
    );
  }

  return (
    <div className="facility-list-panel">
      <div className="facility-panel-header">
        <h3 className="section-title">Facility Allocation Status</h3>
        <span className="allocation-count-tag">
          {activeFacilities.length} Selected / {facilities.length} Candidates
        </span>
      </div>

      {/* Active K=3 Section */}
      <div className="facility-group">
        <div className="group-title active">
          <ShieldCheck size={14} className="text-emerald" />
          <span>Selected Priority Facilities (K = 3)</span>
        </div>

        <div className="facility-cards-list">
          {activeFacilities.map((facility) => {
            const detail = selectedDetails.find((d) => d.facility_id === facility.facility_id);
            const isFocused = currentSelectedId === facility.facility_id;

            return (
              <div
                key={facility.facility_id}
                className={`facility-card active ${isFocused ? 'focused' : ''}`}
                onClick={() => onSelectFacility(facility.facility_id)}
              >
                <div className="facility-card-header">
                  <div className="facility-card-id-block">
                    <span className="fac-id-badge active">{facility.facility_id}</span>
                    <span className="fac-name">{facility.name}</span>
                  </div>
                  <button
                    type="button"
                    className="focus-btn"
                    title="Focus on map"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectFacility(facility.facility_id);
                    }}
                  >
                    <Eye size={13} />
                  </button>
                </div>

                <div className="facility-card-address">
                  <MapPin size={12} />
                  <span>{facility.address}</span>
                </div>

                {detail && (
                  <div className="facility-card-metrics">
                    <div className="fac-stat">
                      <span className="stat-lbl">Catchment Pop:</span>
                      <span className="stat-num">{detail.direct_covered_population.toLocaleString()}</span>
                    </div>
                    <div className="fac-stat">
                      <span className="stat-lbl">Unique Demand:</span>
                      <span className="stat-num text-accent">
                        {detail.unique_heat_weighted_demand.toFixed(1)}
                      </span>
                    </div>
                    <div className="fac-stat">
                      <span className="stat-lbl">Direct Demand:</span>
                      <span className="stat-num">
                        {detail.direct_heat_weighted_demand.toFixed(1)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Standby / Inactive Section */}
      <div className="facility-group">
        <div className="group-title inactive">
          <ShieldAlert size={14} className="text-muted" />
          <span>Standby / Unallocated Facilities</span>
        </div>

        <div className="facility-cards-list">
          {inactiveFacilities.map((facility) => {
            const isFocused = currentSelectedId === facility.facility_id;

            return (
              <div
                key={facility.facility_id}
                className={`facility-card inactive ${isFocused ? 'focused' : ''}`}
                onClick={() => onSelectFacility(facility.facility_id)}
              >
                <div className="facility-card-header">
                  <div className="facility-card-id-block">
                    <span className="fac-id-badge inactive">{facility.facility_id}</span>
                    <span className="fac-name">{facility.name}</span>
                  </div>
                  <button
                    type="button"
                    className="focus-btn"
                    title="Focus on map"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectFacility(facility.facility_id);
                    }}
                  >
                    <Eye size={13} />
                  </button>
                </div>

                <div className="facility-card-address">
                  <MapPin size={12} />
                  <span>{facility.address}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
