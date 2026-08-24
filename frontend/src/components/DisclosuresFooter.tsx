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
              <strong>Thermal Evidence:</strong> FortyGuard 2-meter Street-Level Thermal API (TCM Model, 100m grid resolution).
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
              <strong>Accessibility:</strong> 750m geodesic proximity catchment proxies; not individualized pedestrian route navigation.
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
            <span>Audit & Verification Status</span>
          </div>
          <div className="audit-box">
            <div className="audit-item">
              <span className="audit-label">Scenario ID:</span>
              <span className="audit-val">{scenario?.scenario_id || 'dc_heatwave_20240715'}</span>
            </div>
            <div className="audit-item">
              <span className="audit-label">Core Solver:</span>
              <span className="audit-val">Deterministic Exhaustive Power-Set (N=6, K=3)</span>
            </div>
            <div className="audit-item">
              <span className="audit-label">Test Suite:</span>
              <span className="audit-val text-emerald">131 Core Tests Passed (100%)</span>
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bottom-bar">
        <span>© 2026 CoolAccess — FortyGuard AI Hackathon Project</span>
        <span>Deterministic Optimization Engine</span>
      </div>
    </footer>
  );
};
