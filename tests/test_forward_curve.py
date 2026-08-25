"""Tests for pricing normalization, benchmark indexing, and forward curve term structures."""

import pytest
from fsku.core.forward_curve import ForwardCurveEngine
from fsku.core.models import ForwardCurveRequest
from fsku.core.pricing import PricingEngine

def test_pricing_normalization():
    assert PricingEngine.normalize_rate(49.24, 8) == 6.155
    assert PricingEngine.normalize_rate(2.69, 1) == 2.69
    with pytest.raises(ValueError):
        PricingEngine.normalize_rate(10.0, 0)

def test_pricing_statistics():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert PricingEngine.median(vals) == 3.0
    assert PricingEngine.quantile(vals, 0.5) == 3.0
    assert PricingEngine.quantile(vals, 0.0) == 1.0
    assert PricingEngine.quantile(vals, 1.0) == 5.0

    even_vals = [2.0, 4.0, 6.0, 8.0]
    assert PricingEngine.median(even_vals) == 5.0
    assert PricingEngine.trimmed_mean(vals, trim_fraction=0.2) == 3.0

def test_index_methodologies():
    sample_obs = [
        {"provider": "RunPod", "gpu": "H100 SXM", "basis": "On-demand", "perGpu": 2.69, "gpuCount": 1, "total": 2.69},
        {"provider": "CoreWeave", "gpu": "H100 SXM", "basis": "On-demand", "perGpu": 6.155, "gpuCount": 8, "total": 49.24},
        {"provider": "CoreWeave", "gpu": "H100 SXM", "basis": "Spot", "perGpu": 2.46375, "gpuCount": 8, "total": 19.71},
        {"provider": "Azure", "gpu": "H100 SXM", "basis": "Retail API", "perGpu": 12.29, "gpuCount": 8, "total": 98.32},
    ]

    med = PricingEngine.calculate_index(sample_obs, method="median")
    assert 2.4 < med < 12.3

    t10 = PricingEngine.calculate_index(sample_obs, method="trimmed_10")
    assert t10 > 0

    bal = PricingEngine.calculate_index(sample_obs, method="provider_balanced")
    assert bal > 0

    mean = PricingEngine.calculate_index(sample_obs, method="simple_mean")
    assert mean > 0

def test_sensitivity_and_ablation():
    sample_obs = [
        {"provider": "RunPod", "gpu": "H100 SXM", "basis": "On-demand", "perGpu": 2.69, "gpuCount": 1, "total": 2.69},
        {"provider": "CoreWeave", "gpu": "H100 SXM", "basis": "On-demand", "perGpu": 6.155, "gpuCount": 8, "total": 49.24},
        {"provider": "Azure", "gpu": "H100 SXM", "basis": "Retail API", "perGpu": 12.29, "gpuCount": 8, "total": 98.32},
    ]

    sens = PricingEngine.calculate_sensitivity(sample_obs)
    assert len(sens) > 0
    assert sens[0].sku == "H100 SXM"
    assert sens[0].max_divergence_pct > 0

    abl = PricingEngine.calculate_ablation(sample_obs)
    assert len(abl) > 0
    assert any(a.provider_removed == "Azure" for a in abl)

def test_tech_decay_inference():
    observations = [
        {"provider": "RunPod", "gpu": "A100 SXM", "basis": "On-demand", "perGpu": 1.39},
        {"provider": "RunPod", "gpu": "H100 SXM", "basis": "On-demand", "perGpu": 2.69},
        {"provider": "RunPod", "gpu": "B200 SXM", "basis": "On-demand", "perGpu": 5.98},
        {"provider": "CoreWeave", "gpu": "A100 80GB", "basis": "On-demand", "perGpu": 2.70},
        {"provider": "CoreWeave", "gpu": "H100 SXM", "basis": "On-demand", "perGpu": 6.155},
        {"provider": "CoreWeave", "gpu": "B200", "basis": "On-demand", "perGpu": 8.60},
    ]

    summary = ForwardCurveEngine.infer_tech_decay(observations, cadence_months=24)
    assert 0.0 < summary.decay < 1.0
    assert len(summary.observations) > 0

def test_forward_curve_calculation():
    observations = [
        {"provider": "RunPod", "gpu": "H100 SXM", "basis": "On-demand", "perGpu": 2.69},
        {"provider": "CoreWeave", "gpu": "H100 SXM", "basis": "On-demand", "perGpu": 6.155},
        {"provider": "CoreWeave", "gpu": "H100 SXM", "basis": "Spot", "perGpu": 2.46375},
        {"provider": "AWS", "gpu": "H100", "basis": "Capacity block", "perGpu": 5.191},
        {"provider": "Azure", "gpu": "H100", "basis": "Retail API", "perGpu": 12.29},
        {"provider": "RunPod", "gpu": "A100 SXM", "basis": "On-demand", "perGpu": 1.39},
        {"provider": "RunPod", "gpu": "B200", "basis": "On-demand", "perGpu": 5.98},
    ]

    req = ForwardCurveRequest(
        family="H100",
        basis="firm",
        cadence=24,
        carry_rate=5.0,
        horizon=36,
    )

    res = ForwardCurveEngine.calculate_forward_curve(observations, req)
    assert res is not None
    assert res.family == "H100"
    assert res.S0 > 0.0
    assert len(res.points) == 37
    assert res.points[0].m == 0
    assert res.points[0].base == res.S0
    assert res.points[12].m == 12
    assert res.points[12].base < res.S0

def test_multi_curve_comparison():
    observations = [
        {"provider": "RunPod", "gpu": "H100 SXM", "basis": "On-demand", "perGpu": 2.69},
        {"provider": "RunPod", "gpu": "H200", "basis": "On-demand", "perGpu": 3.59},
        {"provider": "RunPod", "gpu": "B200", "basis": "On-demand", "perGpu": 5.98},
    ]
    res = ForwardCurveEngine.compare_forward_curves(
        observations=observations,
        families=["H100", "H200", "B200"],
        horizon=24,
    )
    assert "curves" in res
    assert "H100" in res["curves"]
    assert "B200" in res["curves"]
    assert "relative_ratios" in res

def test_per_card_differentiated_decay():
    observations = [
        {"provider": "RunPod", "gpu": "A100 SXM", "basis": "On-demand", "perGpu": 1.39},
        {"provider": "RunPod", "gpu": "H100 SXM", "basis": "On-demand", "perGpu": 2.69},
        {"provider": "RunPod", "gpu": "H200", "basis": "On-demand", "perGpu": 3.59},
        {"provider": "RunPod", "gpu": "B200", "basis": "On-demand", "perGpu": 5.98},
        {"provider": "RunPod", "gpu": "RTX 4090", "basis": "On-demand", "perGpu": 0.34},
    ]

    a100_res = ForwardCurveEngine.calculate_forward_curve(
        observations, ForwardCurveRequest(family="A100", carry_rate=5.0, horizon=12)
    )
    h100_res = ForwardCurveEngine.calculate_forward_curve(
        observations, ForwardCurveRequest(family="H100", carry_rate=5.0, horizon=12)
    )
    b200_res = ForwardCurveEngine.calculate_forward_curve(
        observations, ForwardCurveRequest(family="B200", carry_rate=5.0, horizon=12)
    )
    rtx_res = ForwardCurveEngine.calculate_forward_curve(
        observations, ForwardCurveRequest(family="RTX 4090", carry_rate=5.0, horizon=12)
    )

    assert a100_res is not None and h100_res is not None and b200_res is not None and rtx_res is not None

    assert a100_res.d > h100_res.d > b200_res.d
    assert rtx_res.d > b200_res.d

    assert a100_res.annual_factor != h100_res.annual_factor != b200_res.annual_factor
