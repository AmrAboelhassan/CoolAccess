"""FortyGuard Expansion Benchmark Snapshot Acquisition Runner for Washington DC (July 16, 2024).

Acquires 5 diurnal historical 100m TCM snapshots for the Washington DC scenario:
Date: 2024-07-16
Granularity: 100m
Filter Type: 1 (single hour)
Analytic Type: tcm

Planned Acquisition Targets (N=5):
- 14:00Z (~10:00 EDT) -> dc_100m_20240716_1400Z.json
- 16:00Z (~12:00 EDT) -> dc_100m_20240716_1600Z.json
- 18:00Z (~14:00 EDT) -> dc_100m_20240716_1800Z.json
- 20:00Z (~16:00 EDT) -> dc_100m_20240716_2000Z.json
- 22:00Z (~18:00 EDT) -> dc_100m_20240716_2200Z.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

# -----------------------------------------------------------------------------
# Official SDK Discovery & Import (Fail-Closed)
# -----------------------------------------------------------------------------

_QUICKSTART_DIR: Final[Path] = Path(__file__).resolve().parents[2] / "FortyGuard-Quickstart"
if _QUICKSTART_DIR.exists() and str(_QUICKSTART_DIR) not in sys.path:
    sys.path.insert(0, str(_QUICKSTART_DIR))

try:
    from fortyguard import FortyGuardClient
except ImportError as err:
    raise ImportError(
        f"Failed to import FortyGuardClient from official FortyGuard SDK. "
        f"Ensure FortyGuard-Quickstart is available at {_QUICKSTART_DIR}: {err}"
    ) from err

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------

EXPANSION_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "data" / "expansion_20240716"
OUTPUT_DIR: Final[Path] = EXPANSION_DIR / "provider_raw"
MANIFEST_PATH: Final[Path] = EXPANSION_DIR / "acquisition_manifest.json"
THERMAL_SNAPSHOTS_PATH: Final[Path] = EXPANSION_DIR / "thermal_snapshots.json"
METADATA_PATH: Final[Path] = EXPANSION_DIR / "metadata.json"

AOI_GEOJSON_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "data" / "locked_dc_scenario" / "geojson" / "aoi.geojson"
)

EXPANSION_DATE: Final[str] = "2024-07-16"
EXPANSION_GRANULARITY: Final[int] = 100
EXPANSION_FILTER_TYPE: Final[int] = 1
EXPANSION_ANALYTIC_TYPE: Final[str] = "tcm"


@dataclass(frozen=True)
class AcquisitionTarget:
    """Specification for one discrete historical provider snapshot acquisition."""

    utc_hour: int
    utc_label: str
    local_label: str
    provider_start_date: str
    provider_start_time: str
    filename: str

    @property
    def output_path(self) -> Path:
        return OUTPUT_DIR / self.filename


PLANNED_ACQUISITIONS: Final[tuple[AcquisitionTarget, ...]] = (
    AcquisitionTarget(
        utc_hour=14,
        utc_label="14:00Z",
        local_label="10:00 EDT",
        provider_start_date=EXPANSION_DATE,
        provider_start_time="14:00",
        filename="dc_100m_20240716_1400Z.json",
    ),
    AcquisitionTarget(
        utc_hour=16,
        utc_label="16:00Z",
        local_label="12:00 EDT",
        provider_start_date=EXPANSION_DATE,
        provider_start_time="16:00",
        filename="dc_100m_20240716_1600Z.json",
    ),
    AcquisitionTarget(
        utc_hour=18,
        utc_label="18:00Z",
        local_label="14:00 EDT",
        provider_start_date=EXPANSION_DATE,
        provider_start_time="18:00",
        filename="dc_100m_20240716_1800Z.json",
    ),
    AcquisitionTarget(
        utc_hour=20,
        utc_label="20:00Z",
        local_label="16:00 EDT",
        provider_start_date=EXPANSION_DATE,
        provider_start_time="20:00",
        filename="dc_100m_20240716_2000Z.json",
    ),
    AcquisitionTarget(
        utc_hour=22,
        utc_label="22:00Z",
        local_label="18:00 EDT",
        provider_start_date=EXPANSION_DATE,
        provider_start_time="22:00",
        filename="dc_100m_20240716_2200Z.json",
    ),
)


# -----------------------------------------------------------------------------
# Validation & Sanitization Helpers
# -----------------------------------------------------------------------------


def _load_aoi_geojson() -> dict[str, Any]:
    with AOI_GEOJSON_PATH.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _sanitize_telemetry(data: Any) -> Any:
    """Recursively redact any raw API keys, tokens, or auth headers."""
    if isinstance(data, dict):
        return {
            k: "[REDACTED]"
            if any(sub in k.lower() for sub in ("key", "token", "secret", "auth"))
            else _sanitize_telemetry(v)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [_sanitize_telemetry(item) for item in data]
    return data


def validate_provider_payload(
    raw_json: dict[str, Any],
) -> tuple[bool, str, int, float, float, dict[str, float]]:
    """Validate provider payload against DC FeatureCollection contract."""
    raw_resp = raw_json.get("raw_response", {})
    map_data = raw_resp.get("map_data", {})

    if map_data.get("type") != "FeatureCollection":
        return False, f"Expected FeatureCollection, got {map_data.get('type')!r}", 0, 0.0, 0.0, {}

    features = map_data.get("features", [])
    if not features:
        return False, "FeatureCollection contains 0 features", 0, 0.0, 0.0, {}

    tile_count = len(features)
    temps: list[float] = []
    temps_by_tile: dict[str, float] = {}

    for idx, feat in enumerate(features):
        geom = feat.get("geometry", {})
        if geom.get("type") != "Polygon":
            return (
                False,
                f"Feature {idx} geometry type is {geom.get('type')!r}",
                tile_count,
                0.0,
                0.0,
                {},
            )

        coords = geom.get("coordinates", [])
        if not coords or len(coords[0]) < 4:
            return False, f"Feature {idx} invalid polygon ring", tile_count, 0.0, 0.0, {}

        props = feat.get("properties", {})
        avg_temp = props.get("average_temperature")
        tile_id = str(props.get("tile_id", idx))

        if avg_temp is None or not isinstance(avg_temp, (int, float)) or math.isnan(avg_temp):
            return (
                False,
                f"Feature {idx} invalid temperature: {avg_temp!r}",
                tile_count,
                0.0,
                0.0,
                {},
            )

        t_val = float(avg_temp)
        temps.append(t_val)
        temps_by_tile[tile_id] = t_val

    min_t, max_t = min(temps), max(temps)
    return (
        True,
        f"Valid DC FeatureCollection with {tile_count} tiles ({min_t:.2f}°C to {max_t:.2f}°C)",
        tile_count,
        min_t,
        max_t,
        temps_by_tile,
    )


def acquire_snapshot(
    client: FortyGuardClient,
    aoi_geojson: dict[str, Any],
    target: AcquisitionTarget,
    max_wait_s: float = 180.0,
    poll_interval_s: float = 3.0,
) -> dict[str, Any]:
    """Submit and poll a single historical snapshot for Washington DC."""
    t0 = time.perf_counter()
    resp = client.create_heatmap(
        polygon_aoi=aoi_geojson,
        start_date=target.provider_start_date,
        start_time=target.provider_start_time,
        filter_type=EXPANSION_FILTER_TYPE,
        granularity=EXPANSION_GRANULARITY,
        analytic_type=EXPANSION_ANALYTIC_TYPE,
        wait=False,
    )
    submit_latency = time.perf_counter() - t0

    if isinstance(resp, dict):
        activity_id = resp.get("activity_id") or resp.get("data", {}).get("activity_id")
    elif isinstance(resp, str):
        activity_id = resp
    else:
        activity_id = getattr(resp, "activity_id", None) or str(resp)

    if not activity_id:
        raise ValueError(f"Submission missing activity_id: {resp}")

    poll_start = time.perf_counter()
    iterations = 0
    raw_response_result: dict[str, Any] | None = None

    while True:
        iterations += 1
        elapsed = time.perf_counter() - poll_start
        if elapsed > max_wait_s:
            raise TimeoutError(f"Activity {activity_id} timed out after {elapsed:.1f}s")

        try:
            status_resp = client.get_status(str(activity_id))
        except Exception as err:
            err_str = str(err).lower()
            if "404" in err_str or "not ready" in err_str or "activitynotready" in err_str:
                time.sleep(poll_interval_s)
                continue
            raise

        if not isinstance(status_resp, dict):
            status_str = str(
                getattr(status_resp, "status", "") or getattr(status_resp, "activity_status", "")
            ).upper()
            data = getattr(status_resp, "data", status_resp)
        else:
            status_str = str(
                status_resp.get("status")
                or status_resp.get("data", {}).get("status")
                or status_resp.get("activity_status")
                or ""
            ).upper()
            data = status_resp.get("data", status_resp)

        if status_str in ("COMPLETED", "SUCCESS", "DONE", "SUCCEEDED"):
            result = data.get("result") if isinstance(data, dict) else None
            if not isinstance(result, dict):
                result = (
                    status_resp.get("result")
                    if isinstance(status_resp, dict) and isinstance(status_resp.get("result"), dict)
                    else (data if isinstance(data, dict) and "map_data" in data else status_resp)
                )
            raw_response_result = result if isinstance(result, dict) else {}
            break
        elif status_str in ("FAILED", "ERROR"):
            raise RuntimeError(f"Activity {activity_id} failed on server: {status_resp}")

        time.sleep(poll_interval_s)

    total_latency = time.perf_counter() - t0

    artifact = {
        "activity_id": str(activity_id),
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "request_parameters": {
            "polygon_aoi": aoi_geojson,
            "start_date": target.provider_start_date,
            "start_time": target.provider_start_time,
            "filter_type": EXPANSION_FILTER_TYPE,
            "granularity": EXPANSION_GRANULARITY,
            "analytic_type": EXPANSION_ANALYTIC_TYPE,
            "date_time": {
                "start_date": target.provider_start_date,
                "start_time": target.provider_start_time,
                "filter_type": EXPANSION_FILTER_TYPE,
            },
        },
        "raw_response": raw_response_result or {},
    }

    is_valid, msg, tile_count, min_t, max_t, _ = validate_provider_payload(artifact)
    if not is_valid:
        raise ValueError(f"Artifact validation failed for {target.filename}: {msg}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with target.output_path.open("w", encoding="utf-8") as fp:
        json.dump(artifact, fp, indent=2)

    return {
        "utc_label": target.utc_label,
        "local_label": target.local_label,
        "filename": target.filename,
        "activity_id": str(activity_id),
        "tile_count": tile_count,
        "min_temperature_c": min_t,
        "max_temperature_c": max_t,
        "spread_c": round(max_t - min_t, 4),
        "submit_latency_s": round(submit_latency, 3),
        "total_latency_s": round(total_latency, 3),
        "poll_iterations": iterations,
        "status": "ACQUIRED",
    }


def compile_thermal_snapshots_bundle(acquired: list[dict[str, Any]]) -> dict[str, Any]:
    """Compile individual raw snapshot artifacts into CoolAccess thermal_snapshots.json format."""
    all_temps_by_timestamp: dict[str, dict[str, float]] = {}
    pooled_temps: list[float] = []

    for target in PLANNED_ACQUISITIONS:
        if not target.output_path.exists():
            continue
        with target.output_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        _, _, _, _, _, tile_temps = validate_provider_payload(data)
        ts_key = target.provider_start_time.replace(":", "")  # e.g. "1400"
        all_temps_by_timestamp[ts_key] = tile_temps
        pooled_temps.extend(tile_temps.values())

    pooled_sorted = sorted(pooled_temps)
    n = len(pooled_sorted)
    p1_val = pooled_sorted[max(0, int(0.01 * n))] if n else 32.0
    p99_val = pooled_sorted[min(n - 1, int(0.99 * n))] if n else 38.0

    bundle = {
        "timestamps_utc": ["14:00", "16:00", "18:00", "20:00", "22:00"],
        "tile_count": len(next(iter(all_temps_by_timestamp.values())))
        if all_temps_by_timestamp
        else 1452,
        "normalization_anchors": {
            "p1_lower_anchor_c": round(p1_val, 3),
            "p99_upper_anchor_c": round(p99_val, 3),
            "min_temp_c": round(min(pooled_sorted), 3) if pooled_sorted else 0.0,
            "max_temp_c": round(max(pooled_sorted), 3) if pooled_sorted else 0.0,
        },
        "temperatures_by_timestamp": all_temps_by_timestamp,
    }

    with THERMAL_SNAPSHOTS_PATH.open("w", encoding="utf-8") as fp:
        json.dump(bundle, fp, indent=2)

    # Also generate metadata.json for the expansion
    meta = {
        "scenario_id": "dc_downtown_capitol_hill_750m_20240716",
        "city_name": "Washington, DC",
        "scenario_title": "DC Downtown / Capitol Hill Cooling (2024-07-16 Expansion)",
        "historical_date": EXPANSION_DATE,
        "timezone": "America/New_York",
        "resource_budget_k": 3,
        "primary_catchment_radius_meters": 750,
        "available_timestamps_utc": ["14:00", "16:00", "18:00", "20:00", "22:00"],
    }
    with METADATA_PATH.open("w", encoding="utf-8") as fp:
        json.dump(meta, fp, indent=2)

    return bundle


def run_expansion_acquisition(probe_only: bool = False) -> dict[str, Any]:
    print("=" * 80)
    print("COOLACCESS — FORTYGUARD HISTORICAL EXPANSION ACQUISITION (DC 2024-07-16)")
    print("=" * 80)

    client = FortyGuardClient()
    aoi_geojson = _load_aoi_geojson()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pre_telemetry_raw = client.fetch_api_key_usage()
    pre_telemetry = _sanitize_telemetry(pre_telemetry_raw)
    credits_before = pre_telemetry.get("credit_summary", {}).get("cycle_remaining_credits")
    print(f"Pre-Acquisition Remaining Credits: {credits_before}")

    targets_to_run = (PLANNED_ACQUISITIONS[0],) if probe_only else PLANNED_ACQUISITIONS

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for idx, target in enumerate(targets_to_run, start=1):
        if target.output_path.exists() and not probe_only:
            try:
                with target.output_path.open("r", encoding="utf-8") as fp:
                    cached_data = json.load(fp)
                is_valid, _msg, t_cnt, min_t, max_t, _ = validate_provider_payload(cached_data)
                if is_valid:
                    print(
                        f"[{idx}/{len(targets_to_run)}] Reusing valid snapshot: {target.filename}"
                    )
                    results.append(
                        {
                            "utc_label": target.utc_label,
                            "local_label": target.local_label,
                            "filename": target.filename,
                            "activity_id": cached_data.get("activity_id", "CACHED_PROBE"),
                            "tile_count": t_cnt,
                            "min_temperature_c": min_t,
                            "max_temperature_c": max_t,
                            "spread_c": round(max_t - min_t, 4),
                            "status": "REUSED_PROBE",
                        }
                    )
                    continue
            except Exception:
                pass

        print(
            f"[{idx}/{len(targets_to_run)}] Querying {target.utc_label} ({target.local_label})..."
        )
        try:
            res = acquire_snapshot(client, aoi_geojson, target)
            results.append(res)
            print(
                f"  -> SUCCESS: {res['activity_id']} ({res['tile_count']} tiles, "
                f"{res['spread_c']:.2f}°C spread, {res['total_latency_s']}s)"
            )
        except Exception as err:
            print(f"  -> FAILED: {err}")
            failures.append({"target": asdict(target), "error": str(err)})
            if probe_only:
                break

    post_telemetry_raw = client.fetch_api_key_usage()
    post_telemetry = _sanitize_telemetry(post_telemetry_raw)
    credits_after = post_telemetry.get("credit_summary", {}).get("cycle_remaining_credits")
    print(f"Post-Acquisition Remaining Credits: {credits_after}")

    if not probe_only and len(results) == len(PLANNED_ACQUISITIONS):
        compile_thermal_snapshots_bundle(results)
        print("  -> Compiled thermal_snapshots.json and metadata.json successfully.")

    manifest = {
        "manifest_version": "1.0",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "benchmark_date": EXPANSION_DATE,
        "planned_acquisitions_count": len(targets_to_run),
        "successful_acquisitions_count": len(results),
        "failed_acquisitions_count": len(failures),
        "pre_credit_telemetry": pre_telemetry,
        "post_credit_telemetry": post_telemetry,
        "acquired_snapshots": results,
        "failures": failures,
    }

    with MANIFEST_PATH.open("w", encoding="utf-8") as fp:
        json.dump(manifest, fp, indent=2)

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CoolAccess July 16 FortyGuard Acquisition Runner")
    parser.add_argument("--probe-only", action="store_true", help="Run only the 14:00Z probe")
    args = parser.parse_args()
    manifest_result = run_expansion_acquisition(probe_only=args.probe_only)
    if manifest_result["failed_acquisitions_count"] > 0:
        sys.exit(1)
