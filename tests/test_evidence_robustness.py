"""Regression test for CoolAccess offline allocation robustness evidence."""

from __future__ import annotations

from scripts.run_allocation_robustness_evidence import run_evidence


def test_allocation_robustness_evidence() -> None:
    results = run_evidence()

    # Ablation assertions
    ablation = results["ablation"]
    assert isinstance(ablation, dict)
    assert ablation["16:00"]["canonical_set"] == ("DC_089", "DC_148", "DC_166")
    assert ablation["16:00"]["pop_only_set"] == ("DC_089", "DC_148", "DC_166")
    assert ablation["20:00"]["canonical_set"] == ("DC_089", "DC_135", "DC_166")
    assert ablation["20:00"]["pop_only_set"] == ("DC_089", "DC_148", "DC_166")

    # Radius assertions (N=9)
    radius_res = results["radius_results"]
    assert isinstance(radius_res, list)
    assert len(radius_res) == 9
    # All 9 have positive dynamic-vs-static gain
    assert all(r["gain_pct"] > 0 for r in radius_res)
    # 8 of 9 retain DC_148 -> DC_135 transition
    trans_count = sum(1 for r in radius_res if r["is_148_135"])
    assert trans_count == 8

    # K assertions (N=6)
    k_res = results["k_results"]
    assert isinstance(k_res, list)
    assert len(k_res) == 6
    # Diurnal changes appear at K=1, 2, 3
    assert k_res[0]["temporal_change"] is True
    assert k_res[1]["temporal_change"] is True
    assert k_res[2]["temporal_change"] is True
    assert k_res[3]["temporal_change"] is False

    # Normalization set stability (all 3 schemes have identical sets)
    norm_res = results["norm_results"]
    assert isinstance(norm_res, list)
    assert len(norm_res) == 3
    for n in norm_res:
        assert n["set_16"] == ("DC_089", "DC_148", "DC_166")
        assert n["set_20"] == ("DC_089", "DC_135", "DC_166")
