"""The Fix must never blend hyperscaler list into the neocloud headline."""

from fastapi.testclient import TestClient
from fsku.core.database import FSKUDb
from fsku.core.fix import FixEngine


def _row(i, provider, gpu, per_gpu, tier, basis="On-demand"):
    return {"id": f"o{i}", "provider": provider, "gpu": gpu, "instance": "x", "perGpu": per_gpu, "total": per_gpu,
            "gpuCount": 1, "vram": 80, "source": provider.lower(), "tier": tier, "basis": basis,
            "provenance": "catalog", "recorded_at": "2026-08-25"}


def test_segments_are_never_blended_and_universe_is_explicit():
    rows = [
        _row(1, "RunPod", "H100 SXM (1x)", 2.69, "Community"),
        _row(2, "Lambda Labs", "H100 SXM (HGX 8x)", 2.49, "Specialized cloud"),
        _row(3, "CoreWeave", "H100 SXM (HGX 8x)", 2.46, "Specialized cloud", basis="Spot"),
        _row(4, "CoreWeave", "H100 SXM (HGX 8x)", 6.16, "Specialized cloud"),
        _row(5, "Azure", "H100 SXM (HGX 8x)", 12.29, "Hyperscaler", basis="Retail API"),
        _row(6, "AWS", "H100 SXM (HGX 8x)", 12.29, "Hyperscaler"),
        _row(7, "AWS", "H100 SXM (1x)", 5.19, "Hyperscaler", basis="Capacity block"),  # term product: out
        _row(8, "RunPod", "H100 PCIe", 1.99, "Community"),                               # different product: out
        _row(9, "RunPod", "H100 NVL", 2.59, "Community"),                                # different product: out
        _row(10, "RunPod", "H200 SXM (1x)", 3.59, "Community"),                          # other family: out
    ]
    fx = FixEngine.compute(rows, "H100")
    neo, hyp = fx.segments["neocloud"], fx.segments["hyperscaler"]
    assert neo.n == 4 and sorted(c.id for c in neo.constituents) == ["o1", "o2", "o3", "o4"]
    assert hyp.n == 2 and sorted(c.id for c in hyp.constituents) == ["o5", "o6"]
    assert fx.headline == neo.value
    assert 2.46 <= fx.headline <= 2.69, "headline must sit in the neocloud cluster, not be pulled toward list"
    assert hyp.value == 12.29
    assert fx.excluded == {"other_family": 1, "pcie_or_nvl": 2, "term_basis": 1}
    assert fx.as_of == "2026-08-25"


def test_winsorized_median_clips_a_lone_outlier():
    vals = [2.4, 2.5, 2.5, 2.6, 2.7, 9.9]
    assert FixEngine.winsorized_median(vals) < 2.7


def test_empty_segment_is_null_not_zero():
    fx = FixEngine.compute([_row(1, "Azure", "H100 SXM (HGX 8x)", 12.29, "Hyperscaler")], "H100")
    assert fx.headline is None
    assert fx.segments["neocloud"].value is None and fx.segments["neocloud"].n == 0
    assert fx.segments["hyperscaler"].value == 12.29


def test_shipped_tape_headline_is_a_neocloud_number():
    fx = FixEngine.compute(FSKUDb().observations.find(), "H100")
    assert 2.0 < fx.headline < 3.5, fx.headline
    assert fx.segments["hyperscaler"].value > 10
    assert "Hyperscaler" not in fx.segments["neocloud"].tiers


def test_api_fix_endpoint():
    from fsku.api.app import create_app
    res = TestClient(create_app()).get("/api/fix?family=H100")
    assert res.status_code == 200
    d = res.json()
    assert d["family"] == "H100" and d["headline_segment"] == "neocloud"
    assert d["headline"] == d["segments"]["neocloud"]["value"]
    assert all(c["tier"] == "Hyperscaler" for c in d["segments"]["hyperscaler"]["constituents"])
