import React from 'react';
import { Shield, MapPin, Users, Flame, Clock, Sparkles } from 'lucide-react';
import { ScenarioResponse } from '../types';

interface HeaderProps {
  scenario: ScenarioResponse | null;
  currentTimestamp: string;
}

export const Header: React.FC<HeaderProps> = ({ scenario, currentTimestamp }) => {
  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-badge">
          <Shield className="brand-icon" size={20} />
        </div>
        <div className="brand-text">
          <div className="brand-title-row">
            <h1 className="brand-title">CoolAccess</h1>
            <span className="system-pill">TEMPERATURE AI PLATFORM</span>
          </div>
          <p className="brand-subtitle">
            Which three municipal cooling facilities should be active as neighborhood temperatures shift?
          </p>
          <div className="brand-authority-line">
            <span>
              FortyGuard supplies prepared temperature evidence · deterministic optimizer allocates · AI explains validated claims
            </span>
            <button
              type="button"
              className="btn-header-ai-jump"
              onClick={() => {
                const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                document.querySelector('.heat-intelligence-module')?.scrollIntoView({
                  behavior: reduceMotion ? 'auto' : 'smooth',
                  block: 'start',
                });
              }}
            >
              <Sparkles size={12} />
              <span>Ask allocation question</span>
            </button>
          </div>
        </div>
      </div>

      <div className="header-meta-grid">
        <div className="meta-card">
          <div className="meta-label">
            <MapPin size={13} className="meta-icon" />
            <span>Target Jurisdiction</span>
          </div>
          <div className="meta-value">
            {scenario ? `${scenario.city} (${scenario.aoi?.name || 'Corridor'})` : 'Washington, DC'}
          </div>
          <div className="meta-sub">
            {scenario?.aoi?.area_km2 ? `${scenario.aoi.area_km2} km² Contiguous Thermal Corridor` : '14.61 km² AOI'}
          </div>
        </div>

        <div className="meta-card">
          <div className="meta-label">
            <Clock size={13} className="meta-icon" />
            <span>Scenario Horizon</span>
          </div>
          <div className="meta-value">
            {scenario?.historical_date || '2024-07-15'} (Heatwave)
          </div>
          <div className="meta-sub">Active Horizon: {currentTimestamp} UTC</div>
        </div>

        <div className="meta-card highlight">
          <div className="meta-label">
            <Flame size={13} className="meta-icon text-amber" />
            <span>Resource Constraint</span>
          </div>
          <div className="meta-value text-accent">
            K = {scenario?.resource_budget_k ?? 3} Active Facilities
          </div>
          <div className="meta-sub">
            {scenario?.catchment_radius_meters ?? 750}m Geographic Catchment
          </div>
        </div>

        <div className="meta-card">
          <div className="meta-label">
            <Users size={13} className="meta-icon" />
            <span>Residential Population Base</span>
          </div>
          <div className="meta-value">
            {scenario?.population_summary?.total_residential_population?.toLocaleString() ?? '100,389'}
          </div>
          <div className="meta-sub">2020 Decennial Census (Table P1)</div>
        </div>
      </div>
    </header>
  );
};
