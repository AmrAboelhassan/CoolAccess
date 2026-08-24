import React from 'react';
import { Layers, Thermometer } from 'lucide-react';

interface ThermalLegendProps {
  showThermalGrid: boolean;
  setShowThermalGrid: (val: boolean) => void;
  showCatchments: boolean;
  setShowCatchments: (val: boolean) => void;
  showAOI: boolean;
  setShowAOI: (val: boolean) => void;
}

export const ThermalLegend: React.FC<ThermalLegendProps> = ({
  showThermalGrid,
  setShowThermalGrid,
  showCatchments,
  setShowCatchments,
  showAOI,
  setShowAOI,
}) => {
  return (
    <div className="thermal-legend-panel">
      <div className="legend-header">
        <Thermometer size={14} className="text-amber" />
        <span className="legend-title">FortyGuard 100m Thermal Grid Scale</span>
      </div>

      <div className="legend-gradient-bar">
        <div className="gradient-visual" />
        <div className="gradient-ticks">
          <div className="tick-item">
            <span className="tick-val">32.0°C</span>
            <span className="tick-label">Min Reference (w=0.0)</span>
          </div>
          <div className="tick-item center">
            <span className="tick-val">34.8°C</span>
            <span className="tick-label">Moderate (w=0.5)</span>
          </div>
          <div className="tick-item end">
            <span className="tick-val">37.7°C</span>
            <span className="tick-label">Max Reference (w=1.0)</span>
          </div>
        </div>
      </div>

      <div className="legend-layer-controls">
        <div className="layer-control-title">
          <Layers size={13} />
          <span>GIS Map Layers:</span>
        </div>
        <label className="layer-checkbox-label">
          <input
            type="checkbox"
            checked={showThermalGrid}
            onChange={(e) => setShowThermalGrid(e.target.checked)}
          />
          <span>100m Thermal Grid</span>
        </label>
        <label className="layer-checkbox-label">
          <input
            type="checkbox"
            checked={showCatchments}
            onChange={(e) => setShowCatchments(e.target.checked)}
          />
          <span>750m Catchments</span>
        </label>
        <label className="layer-checkbox-label">
          <input
            type="checkbox"
            checked={showAOI}
            onChange={(e) => setShowAOI(e.target.checked)}
          />
          <span>AOI Boundary</span>
        </label>
      </div>
    </div>
  );
};
