import React from 'react';
import { Shield, MapPin, Users, Flame, Clock } from 'lucide-react';
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
            Temperature AI Decision Platform for Municipal Heat Resilience & Dynamic Cooling Infrastructure
          </p>
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
            {scenario?.catchment_radius_meters ?? 750}m Thermal Catchment
          </div>
        </div>

        <div className="meta-card">
          <div className="meta-label">
            <Users size={13} className="meta-icon" />
            <span>Protected Population Base</span>
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

