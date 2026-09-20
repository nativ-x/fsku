"""The headline dispersion must compare one product with itself."""

from fsku.core.database import FSKUDb
from fsku.core.pricing import PricingEngine


def _row(provider, gpu, per_gpu, tier, basis="On-demand"):
    return {"provider": provider, "gpu": gpu, "instance": "x", "perGpu": per_gpu, "total": per_gpu,
            "gpuCount": 1, "vram": 80, "source": provider.lower(), "tier": tier, "basis": basis,
            "topology": "HGX 8x Clustered" if "8x" in gpu else "1x Standalone Pod"}


def test_family_range_is_not_reported_as_the_dispersion():
    rows = [
        _row("RunPod", "H100 PCIe", 1.99, "Community"),
        _row("Azure", "H100 SXM (HGX 8x)", 12.29, "Hyperscaler"),
        _row("AWS", "H100 SXM (HGX 8x)", 12.29, "Hyperscaler"),
        _row("CoreWeave", "H100 SXM (HGX 8x)", 6.16, "Specialized cloud"),
        _row("Lambda Labs", "H100 SXM (HGX 8x)", 3.00, "Specialized cloud"),
    ]
    k = PricingEngine.calculate_kpis(rows)
    assert k["h100_family_range"] == k["h100_dispersion"] == round(12.29 / 1.99, 2)
    ref = k["reference"]
    assert ref["sku"] == "H100 SXM (HGX 8x)"
    assert ref["like_for_like"] is False
    assert ref["tiers"] == ["Hyperscaler", "Specialized cloud"]
    assert ref["dispersion"] == round(12.29 / 3.00, 2)
    # within one tier the widest spread is Specialized cloud 6.16/3.00
    assert ref["same_tier"] == "Specialized cloud"
    assert ref["same_tier_dispersion"] == round(6.16 / 3.00, 2)
    assert ref["by_tier"]["Hyperscaler"]["dispersion"] == 1.0
    assert ref["low"]["tier"] == "Specialized cloud" and ref["high"]["tier"] == "Hyperscaler"
    assert k["lowest_h100"]["sku"] == "H100 PCIe" and k["lowest_h100"]["tier"] == "Community"


def test_single_tier_sku_is_like_for_like():
    rows = [_row("A", "H100 SXM (HGX 8x)", 4.0, "Specialized cloud"), _row("B", "H100 SXM (HGX 8x)", 5.0, "Specialized cloud")]
    ref = PricingEngine.calculate_kpis(rows)["reference"]
    assert ref["like_for_like"] is True
    assert ref["dispersion"] == ref["same_tier_dispersion"] == 1.25


def test_reference_prefers_hgx_on_tie():
    rows = [_row("A", "H100 PCIe", 2.0, "Community"), _row("B", "H100 SXM (HGX 8x)", 8.0, "Hyperscaler")]
    assert PricingEngine.calculate_kpis(rows)["reference"]["sku"] == "H100 SXM (HGX 8x)"


def test_shipped_tape_headline_is_smaller_than_the_family_range():
    k = PricingEngine.calculate_kpis(FSKUDb().observations.find())
    ref = k["reference"]
    assert ref["sku"] == "H100 SXM (HGX 8x)"
    assert ref["same_tier_dispersion"] < ref["dispersion"] <= k["h100_family_range"]
    assert k["h100_family_range"] > 6.0  # the 6.2x the old headline reported


def test_new_snapshots_record_reference_figures(tmp_path):
    db = FSKUDb(storage_dir=tmp_path)
    snap = db.create_snapshot(label="t")
    assert snap["reference_sku"] == "H100 SXM (HGX 8x)"
    assert snap["reference_same_tier_dispersion"] <= snap["reference_dispersion"] <= snap["h100_dispersion"]
    assert db.verify_snapshot(snap["id"])["verified"] is True
