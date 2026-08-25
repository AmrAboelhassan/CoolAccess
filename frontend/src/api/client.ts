import {
  ScenarioResponse,
  AllocationResponse,
  ReplacementResponse,
  GeoJSONFeatureCollection,
  HeatBriefRequest,
  HeatBriefResponse,
} from '../types';

const API_BASE = '/api';

export async function fetchScenario(signal?: AbortSignal): Promise<ScenarioResponse> {
  const res = await fetch(`${API_BASE}/scenario`, { signal });
  if (!res.ok) {
    throw new Error(`Failed to fetch scenario: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function fetchAllocation(
  timestamp: string = '16:00',
  baselineTimestamp: string = '16:00',
  radiusMeters: number = 750,
  k: number = 3,
  signal?: AbortSignal
): Promise<AllocationResponse> {
  const params = new URLSearchParams({
    timestamp,
    baseline_timestamp: baselineTimestamp,
    radius_meters: radiusMeters.toString(),
    k: k.toString(),
  });
  const res = await fetch(`${API_BASE}/allocate?${params.toString()}`, { signal });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail || `Allocation failed with status ${res.status}`);
  }
  return res.json();
}

export async function fetchReplacement(
  timestamp: string = '20:00',
  selectedId?: string,
  unselectedId?: string,
  radiusMeters: number = 750,
  k: number = 3,
  signal?: AbortSignal
): Promise<ReplacementResponse> {
  const params = new URLSearchParams({
    timestamp,
    radius_meters: radiusMeters.toString(),
    k: k.toString(),
  });
  if (selectedId) params.set('selected_id', selectedId);
  if (unselectedId) params.set('unselected_id', unselectedId);

  const res = await fetch(`${API_BASE}/replacement?${params.toString()}`, { signal });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail || `Replacement request failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchGeoJSON(
  layer: 'all' | 'thermal' | 'facilities' | 'demand' | 'aoi' = 'all',
  timestamp: string = '16:00',
  signal?: AbortSignal
): Promise<Record<string, GeoJSONFeatureCollection> | GeoJSONFeatureCollection> {
  const params = new URLSearchParams({ layer, timestamp });
  const res = await fetch(`${API_BASE}/geojson?${params.toString()}`, { signal });
  if (!res.ok) {
    throw new Error(`Failed to load GeoJSON layer '${layer}': ${res.status}`);
  }
  return res.json();
}

export async function fetchHeatBrief(
  request: HeatBriefRequest,
  signal?: AbortSignal
): Promise<HeatBriefResponse> {
  const res = await fetch(`${API_BASE}/heat-intelligence/brief`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail || `Heat intelligence brief request failed: ${res.status}`);
  }
  return res.json();
}
