"""Tests that Phase 1 stays inside its approved provider-neutral boundary."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "coolaccess"
SYNTHETIC_NOTICE = "SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA"


CORE_MODULE_NAMES = {
    "analysis.py",
    "baselines.py",
    "canonical.py",
    "contracts.py",
    "coverage.py",
    "demand.py",
    "errors.py",
    "metrics.py",
    "optimizer.py",
    "replacement.py",
}


def _source_files() -> tuple[Path, ...]:
    return tuple(sorted(p for p in SOURCE_ROOT.glob("*.py") if p.name in CORE_MODULE_NAMES))


def test_source_has_no_forbidden_integrations_or_product_claims() -> None:
    forbidden_terms = (
        "fortyguard",
        "celsius",
        "percentile",
        "walking-time",
        "walking distance",
        "walking-distance",
        "routing engine",
        "geopandas",
        "osrm",
        "graphhopper",
        "openai",
        "anthropic",
        "gemini",
        "lives saved",
        "injury reduction",
        "mortality prediction",
        "medical risk",
        "real-time occupancy",
    )
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in _source_files())
    assert not {term for term in forbidden_terms if term in combined}


def test_source_imports_no_deferred_frameworks() -> None:
    forbidden_roots = {
        "anthropic",
        "celery",
        "fastapi",
        "geopandas",
        "google.generativeai",
        "openai",
        "ortools",
        "osmnx",
        "pulp",
        "redis",
        "sqlalchemy",
    }
    imported: set[str] = set()
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
    assert not {
        module
        for module in imported
        if any(module == root or module.startswith(f"{root}.") for root in forbidden_roots)
    }


def test_no_standalone_thermal_cell_contract_exists() -> None:
    class_names: set[str] = set()
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        class_names.update(node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
    assert "ThermalCell" not in class_names


def test_synthetic_fixture_is_confined_to_tests_and_clearly_labeled() -> None:
    fixture = PROJECT_ROOT / "tests" / "synthetic_fixtures.py"
    assert SYNTHETIC_NOTICE in fixture.read_text(encoding="utf-8")

    for path in _source_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        constructed_domain_inputs = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        } & {
            "AccessibilityRelationship",
            "AllocationRequest",
            "FacilityDefinition",
            "PopulationCell",
            "ProvenanceRecord",
        }
        assert not constructed_domain_inputs, path


def test_no_embedded_secret_shaped_assignments_in_source() -> None:
    suspicious_names = {"api_key", "password", "secret", "token"}
    findings: list[tuple[str, int, str]] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            value = node.value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id.lower() in suspicious_names:
                    findings.append((path.name, node.lineno, target.id))
    assert findings == []
