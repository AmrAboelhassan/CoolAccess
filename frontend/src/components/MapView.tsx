import React, { useEffect } from 'react';
import { MapContainer, TileLayer, GeoJSON, Circle, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Facility, AllocationResponse, GeoJSONFeatureCollection } from '../types';

interface MapViewProps {
  facilities: Facility[];
  allocation: AllocationResponse | null;
  thermalGeoJSON: GeoJSONFeatureCollection | null;
  aoiGeoJSON: GeoJSONFeatureCollection | null;
  showThermalGrid: boolean;
  showCatchments: boolean;
  showAOI: boolean;
  selectedFacilityId: string | null;
  onSelectFacility: (facilityId: string) => void;
}

// Center of locked Washington DC AOI
const AOI_CENTER: [number, number] = [38.895, -77.011];
const DEFAULT_ZOOM = 14;

// Fixed thermal color interpolation matching Method A anchors: [32.022, 37.699]
function getThermalColor(tempC: number | null | undefined): string {
  if (typeof tempC !== 'number' || !Number.isFinite(tempC)) {
    return '#475569';
  }
  const minT = 32.022;
  const maxT = 37.699;
  const ratio = Math.max(0, Math.min(1, (tempC - minT) / (maxT - minT)));

  if (ratio < 0.25) {
    // 32.0 to 33.4: Deep Cyan / Blue
    return '#0284c7';
  } else if (ratio < 0.5) {
    // 33.4 to 34.8: Teal to Yellow
    return '#14b8a6';
  } else if (ratio < 0.75) {
    // 34.8 to 36.2: Amber / Orange
    return '#f59e0b';
  } else {
    // 36.2 to 37.7+: Crimson / Red
    return '#dc2626';
  }
}

// Controller component to center on selected facility and observe container size changes
const MapController: React.FC<{ targetCoords: [number, number] | null }> = ({ targetCoords }) => {
  const map = useMap();

  useEffect(() => {
    if (targetCoords) {
      map.flyTo(targetCoords, 15, { duration: 0.8 });
    }
  }, [targetCoords, map]);

  useEffect(() => {
    const container = map.getContainer();
    if (!container) return;

    const resizeObserver = new ResizeObserver(() => {
      map.invalidateSize();
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, [map]);

  return null;
};

export const MapView: React.FC<MapViewProps> = ({
  facilities,
  allocation,
  thermalGeoJSON,
  aoiGeoJSON,
  showThermalGrid,
  showCatchments,
  showAOI,
  selectedFacilityId,
  onSelectFacility,
}) => {
  const selectedFacilityIds = new Set(allocation?.selected_facility_ids || []);

  const targetFacility = facilities.find((f) => f.facility_id === selectedFacilityId);
  const targetCoords: [number, number] | null = targetFacility
    ? [targetFacility.latitude, targetFacility.longitude]
    : null;

  // Custom DivIcons for Active vs Inactive facilities
  const createFacilityIcon = (facility: Facility, isSelected: boolean) => {
    const isTarget = facility.facility_id === selectedFacilityId;
    const badgeClass = isSelected ? 'marker-badge-active' : 'marker-badge-inactive';
    const highlightRing = isTarget ? 'ring-active' : '';

    return L.divIcon({
      className: 'custom-facility-marker',
      html: `
        <div class="facility-pin-wrapper ${highlightRing}">
          <div class="facility-pin ${badgeClass}">
            <span class="pin-id">${facility.facility_id}</span>
          </div>
          ${isSelected ? '<div class="pin-pulse"></div>' : ''}
        </div>
      `,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
      popupAnchor: [0, -20],
    });
  };

  return (
    <div className="map-container-wrapper">
      <MapContainer
        center={AOI_CENTER}
        zoom={DEFAULT_ZOOM}
        minZoom={12}
        maxZoom={18}
        scrollWheelZoom={true}
        className="leaflet-map-canvas"
      >
        <MapController targetCoords={targetCoords} />

        {/* Clean Dark CartoDB Basemap */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a> | FortyGuard API'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {/* AOI Boundary Polygon */}
        {showAOI && aoiGeoJSON && (
          <GeoJSON
            key="aoi-layer"
            data={aoiGeoJSON as any}
            style={{
              color: '#38bdf8',
              weight: 2,
              dashArray: '6, 6',
              fillColor: '#38bdf8',
              fillOpacity: 0.04,
            }}
          />
        )}

        {/* FortyGuard 100m Thermal Grid GeoJSON Overlay */}
        {showThermalGrid && thermalGeoJSON && (
          <GeoJSON
            key={`thermal-grid-${allocation?.timestamp || 'default'}`}
            data={thermalGeoJSON as any}
            style={(feature) => {
              const temp = feature?.properties?.temperature_c;
              return {
                fillColor: getThermalColor(temp),
                fillOpacity: 0.52,
                color: 'rgba(255,255,255,0.06)',
                weight: 0.5,
              };
            }}
            onEachFeature={(feature, layer) => {
              const props = feature.properties;
              if (props) {
                const rawTemp = Number(props.temperature_c);
                const rawPriority = Number(props.thermal_priority);
                const temp = Number.isFinite(rawTemp) ? `${rawTemp.toFixed(2)}°C` : 'Unavailable';
                const priority = Number.isFinite(rawPriority)
                  ? rawPriority.toFixed(4)
                  : 'Unavailable';
                layer.bindTooltip(
                  `<div class="grid-tooltip">
                    <strong>100m Grid Cell</strong><br/>
                    Temperature: <span class="text-amber">${temp}</span><br/>
                    Thermal Priority Weight: <span>${priority}</span>
                  </div>`,
                  { sticky: true, className: 'custom-leaflet-tooltip' }
                );
              }
            }}
          />
        )}

        {/* Request-authoritative proximity catchment circles */}
        {showCatchments &&
          facilities.map((facility) => {
            const isSelected = selectedFacilityIds.has(facility.facility_id);
            return (
              <Circle
                key={`catchment-${facility.facility_id}-${isSelected}`}
                center={[facility.latitude, facility.longitude]}
                radius={allocation?.radius_meters ?? 750}
                pathOptions={{
                  color: isSelected ? '#10b981' : '#64748b',
                  weight: isSelected ? 2 : 1,
                  dashArray: isSelected ? '4, 4' : '2, 6',
                  fillColor: isSelected ? '#10b981' : '#64748b',
                  fillOpacity: isSelected ? 0.16 : 0.04,
                }}
              />
            );
          })}

        {/* 6 Facility Markers */}
        {facilities.map((facility) => {
          const isSelected = selectedFacilityIds.has(facility.facility_id);
          const facDetail = allocation?.selected_facilities.find(
            (f) => f.facility_id === facility.facility_id
          );

          return (
            <Marker
              key={`facility-${facility.facility_id}`}
              position={[facility.latitude, facility.longitude]}
              icon={createFacilityIcon(facility, isSelected)}
              eventHandlers={{
                click: () => onSelectFacility(facility.facility_id),
              }}
            >
              <Popup className="facility-map-popup">
                <div className="popup-card">
                  <div className="popup-header">
                    <span className="popup-id">{facility.facility_id}</span>
                    <span
                      className={`popup-status-pill ${
                        isSelected ? 'status-active' : 'status-inactive'
                      }`}
                    >
                      {isSelected
                        ? `SELECTED PRIORITY (K=${allocation?.k ?? 3})`
                        : 'ELIGIBLE / UNSELECTED'}
                    </span>
                  </div>
                  <h3 className="popup-name">{facility.name}</h3>
                  <p className="popup-address">{facility.address}</p>

                  <div className="popup-stats-grid">
                    <div className="popup-stat-item">
                      <span className="popup-stat-label">Catchment Pop (2020)</span>
                      <span className="popup-stat-val">
                        {facDetail
                          ? facDetail.direct_covered_population.toLocaleString()
                          : 'Available'}
                      </span>
                    </div>
                    {facDetail && (
                      <div className="popup-stat-item">
                        <span className="popup-stat-label">Unique Demand</span>
                        <span className="popup-stat-val text-accent">
                          {facDetail.unique_heat_weighted_demand.toFixed(1)}
                        </span>
                      </div>
                    )}
                    {facDetail && (
                      <div className="popup-stat-item">
                        <span className="popup-stat-label">Direct Demand</span>
                        <span className="popup-stat-val">
                          {facDetail.direct_heat_weighted_demand.toFixed(1)}
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="popup-footer">
                    <span className="popup-disclaimer">
                      {allocation?.radius_meters ?? 750}m geographic accessibility proxy • 2020 Census residential population
                    </span>
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
};
