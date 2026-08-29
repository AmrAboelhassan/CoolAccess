import React from 'react';
import { ShieldCheck, Database, FileText } from 'lucide-react';
import { ScenarioResponse } from '../types';

interface DisclosuresFooterProps {
  scenario: ScenarioResponse | null;
}

export const DisclosuresFooter: React.FC<DisclosuresFooterProps> = ({ scenario }) => {
  return (
    <footer className="app-footer">
      <div className="footer-content">
        <div className="footer-column">
          <div className="footer-col-header">
            <Database size={14} className="text-sky" />
            <span>Data Provenance & Registry</span>
          </div>
          <ul className="footer-list">
            <li>
              <strong>Thermal Evidence:</strong> Prepared historical FortyGuard 2-meter ambient-temperature data (TCM, 100m grid preparation).
            </li>
            <li>
              <strong>Residential Population:</strong> U.S. Census Bureau 2020 Decennial Census (P.L. 94-171, Table P1).
            </li>
            <li>
              <strong>Facility Geometries:</strong> DC Open Data Public Libraries & DPR Recreation Centers.
            </li>
          </ul>
        </div>

        <div className="footer-column">
          <div className="footer-col-header">
            <FileText size={14} className="text-amber" />
            <span>Methodology & Disclosures</span>
          </div>
          <ul className="footer-list">
            <li>
              <strong>Accessibility:</strong> 750m geodesic facility-to-Census-block-centroid catchment proxy; not walking-network travel distance.
            </li>
            <li>
              <strong>Operational Eligibility:</strong> Benchmark scope: all six locked candidate facilities are treated as operationally eligible. Operating hours, current activation status, and facility service capacity are not modeled.
            </li>
            <li>
              <strong>Population Scope:</strong> Permanent Decennial Census residential population; does not model transient pedestrian occupancy.
            </li>
            <li>
              <strong>Decision Context:</strong> Constrained municipal facility prioritization tool; does not forecast individual medical outcomes.
            </li>
          </ul>
        </div>

        <div className="footer-column audit-col">
          <div className="footer-col-header">
            <ShieldCheck size={14} className="text-emerald" />
            <span>Temperature AI Verification & Audit</span>
          </div>
          <div className="audit-box">
            <div className="audit-item">
              <span className="audit-label">Scenario ID:</span>
              <span className="audit-val">{scenario?.scenario_id || 'dc_heatwave_20240715'}</span>
            </div>
            <div className="audit-item">
              <span className="audit-label">Core Solver:</span>
              <span className="audit-val">Deterministic exhaustive combination evaluation (N=6, K=3)</span>
            </div>
            <div className="audit-item">
              <span className="audit-label">Verification:</span>
              <span className="audit-val text-emerald">See repository test and release results</span>
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bottom-bar">
        <span>© 2026 CoolAccess — FortyGuard AI Hackathon Project</span>
        <span>Temperature Intelligence • Evidence-Grounded AI • Deterministic Optimization</span>
      </div>
    </footer>
  );
};
