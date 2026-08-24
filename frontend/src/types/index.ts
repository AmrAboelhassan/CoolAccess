// TypeScript definitions for CoolAccess API contracts

export interface Facility {
  facility_id: string;
  name: string;
  facility_type: string;
  address: string;
  latitude: number;
  longitude: number;
  eligibility_status: string;
  verified_source: string;
}

export interface ScenarioResponse {
  city: string;
  scenario_id: string;
  scenario_title: string;
  historical_date: string;
  timezone: string;
  aoi: {
    name: string;
    description: string;
    bounding_box: {
      min_lon: number;
      max_lon: number;
      min_lat: number;
      max_lat: number;
    };
    area_km2: number;
  };
  resource_budget_k: number;
  catchment_radius_meters: number;
  available_timestamps_utc: string[];
  candidate_facilities: Facility[];
  population_summary?: {
    total_residential_population?: number;
    total_census_blocks?: number;
    table_id?: string;
    license?: string;
  };
  primary_transition?: {
    now_timestamp_utc: string;
    future_timestamp_utc: string;
    replaced_facility: string;
    activated_facility: string;
  };
  provenance_registry?: Array<{
    provenance_id: string;
    scope: string;
    source_kind: string;
    source_name: string;
    dataset_title: string;
    license_reference: string;
    source_vintage: string;
  }>;
}

export interface SelectedFacilityDetail {
  facility_id: string;
  name: string;
  address: string;
  direct_covered_population: number;
  direct_heat_weighted_demand: number;
  unique_heat_weighted_demand: number;
  overlapping_heat_weighted_demand: number;
}

export interface CoverageMetrics {
  covered_heat_weighted_demand: number;
  total_heat_weighted_demand: number;
  uncovered_heat_weighted_demand: number;
  coverage_percentage: number;
  covered_population: number;
  total_population: number;
  uncovered_population: number;
}

export interface StaticBaseline {
  source_timestamp: string;
  selected_facility_ids: string[];
  objective_value: number;
  covered_population: number;
  absolute_gain: number;
  percentage_gain: number;
}

export interface NaiveBaseline {
  algorithm: string;
  selected_facility_ids: string[];
  objective_value: number;
  covered_population: number;
  absolute_gain: number;
  percentage_gain: number;
}

export interface ReplacementSummaryItem {
  selected_facility_id: string;
  alternative_facility_id: string;
  objective_delta: number;
  primary_objective_loss: number;
  population_delta: number;
  reason_code: string;
}

export interface AllocationResponse {
  timestamp: string;
  baseline_timestamp: string;
  k: number;
  resource_count: number;
  selected_facility_ids: string[];
  selected_facilities: SelectedFacilityDetail[];
  coverage_metrics: CoverageMetrics;
  static_baseline: StaticBaseline;
  naive_baseline: NaiveBaseline;
  replacement_summary: ReplacementSummaryItem[];
  tie_break: {
    decisive_criterion: string;
    evaluated_combination_count: number;
    primary_tied_count: number;
    population_tied_count: number;
  };
  fingerprints: {
    structural: string;
    full_state: string;
  };
}

export interface PrimaryReplacement {
  selected_facility: {
    facility_id: string;
    name: string;
    direct_covered_population: number;
    direct_heat_weighted_demand: number;
  };
  alternative_facility: {
    facility_id: string;
    name: string;
    direct_covered_population: number;
    direct_heat_weighted_demand: number;
  };
  original_objective: number;
  replacement_objective: number;
  objective_delta: number;
  primary_objective_loss: number;
  population_delta: number;
  lost_population: number;
  gained_population: number;
  lost_demand: number;
  gained_demand: number;
  comparator_outcome: string;
  decisive_criterion: string | null;
  reason_code: string;
  explanation: string;
}

export interface ReplacementMatrixItem {
  selected_id: string;
  unselected_id: string;
  objective_delta: number;
  primary_objective_loss: number;
  population_delta: number;
  reason_code: string;
}

export interface ReplacementResponse {
  timestamp: string;
  optimal_selected_facilities: string[];
  primary_replacement: PrimaryReplacement;
  replacement_matrix: ReplacementMatrixItem[];
}

export interface GeoJSONFeature {
  type: 'Feature';
  geometry: {
    type: string;
    coordinates: any;
  };
  properties: Record<string, any>;
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
  metadata?: Record<string, any>;
}

export type IntentCode =
  | 'ALLOCATION_SUMMARY'
  | 'DIURNAL_HEAT_TRANSITION'
  | 'HEAT_VULNERABILITY_EXPLANATION'
  | 'REPLACEMENT_RATIONALE'
  | 'BASELINE_COMPARISON';

export type CopilotStatus = 'AI_GENERATED' | 'DETERMINISTIC_FALLBACK';

export interface BriefItem {
  claim_id: string;
  server_rendered_text: string;
  facility_id?: string;
  alternative_id?: string;
}

export interface HeatBriefRequest {
  question: string;
  timestamp?: string;
  baseline_timestamp?: string;
  radius_meters?: number;
  k?: number;
}

export interface HeatBriefResponse {
  status: CopilotStatus;
  intent_code: IntentCode;
  scenario_id: string;
  plan_fingerprint: string;
  title: string;
  brief_items: BriefItem[];
  tools_used: string[];
  requested_highlights: string[];
  mandatory_caveats: string[];
  fallback_reason?: string;
}
