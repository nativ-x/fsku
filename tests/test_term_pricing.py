"""Term pricing must be built from published prices only, one vote per seller,
never blending segments, and must say which cells are estimated."""

import collections
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient

from fsku.api.app import create_app
from fsku.core.term_pricing import TermPricingEngine
from fsku.sync.term_catalog import TERM_QUOTES, TERM_REFERENCES, quote, per_gpu_hour, per_instance_hour, whole_term, discount_off


def _q(provider, family, days, price, segment="neocloud", min_gpus=None):
    return quote(provider, segment, family, f"{family} node", "x", days, per_gpu_hour(price), "https://example.com/pricing",
                 min_gpus=min_gpus)


def test_catalog_rows_are_sourced_dated_and_unique():
    ids = [q["id"] for q in TERM_QUOTES]
    assert not [k for k, v in collections.Counter(ids).items() if v > 1], "quote ids must be unique"
    for q in TERM_QUOTES:
        assert q["source"].startswith("https://"), q["id"]
        assert q["captured"] and q["published"] and q["math"], q["id"]
        assert q["segment"] in ("neocloud", "hyperscaler"), q["id"]
        assert 0 <= q["min_days"] <= q["max_days"], q["id"]
        assert q["per_gpu"] > 0, q["id"]
    for r in TERM_REFERENCES:
        assert r["low"] < r["high"] and r["source"].startswith("https://")


def test_unit_math_matches_the_published_figure():
    # Azure quotes a reservation as the whole term per VM.
    azure_h100_1y = next(q for q in TERM_QUOTES if q["id"] == "azure_h100_365-365")
    assert azure_h100_1y["per_gpu"] == round(551221.0 / 8760 / 8, 4)
    assert whole_term(1722566.0, 1825, 8)["per_gpu"] == pytest.approx(1722566.0 / 43800 / 8)
    # AWS and GCP quote an instance-hour.
    assert per_instance_hour(55.04, 8)["per_gpu"] == pytest.approx(6.88)
    # Verda and Hyperbolic publish a discount off their own on-demand.
    assert discount_off(3.555, 8)["per_gpu"] == pytest.approx(3.555 * 0.92)


def test_one_vote_per_seller_median_across_sellers():
    quotes = [
        _q("A", "H100", (365, 365), 3.00),
        _q("A", "H100", (300, 400), 2.50),   # same seller, lower price: this one votes
        _q("B", "H100", (365, 365), 4.00),
        _q("C", "H100", (365, 365), 2.00),
    ]
    res = TermPricingEngine.compute("neocloud", families=["H100"], quotes=quotes, references=[])
    cell = next(c for c in res.cells if c.term == "1Y")
    assert cell.status == "observed" and cell.n_sellers == 3
    assert cell.value == 2.50 and (cell.low, cell.high) == (2.00, 4.00)
    assert "a_h100_300-400" in cell.quote_ids and "a_h100_365-365" not in cell.quote_ids


def test_a_range_quote_prices_every_term_inside_it():
    # An AWS Capacity Block is sold for any length from 1 to 182 days.
    quotes = [_q("AWS", "H100", (1, 182), 5.19, segment="hyperscaler"), _q("AWS", "H100", (0, 0), 6.88, segment="hyperscaler")]
    res = TermPricingEngine.compute("hyperscaler", families=["H100"], quotes=quotes, references=[])
    priced = {c.term for c in res.cells if c.status == "observed"}
    assert priced == {"OD", "1M", "3M", "6M"}
    assert set(res.empty_terms) == {"1Y", "2Y", "3Y", "5Y"}, "terms no seller publishes are dropped and named"


def test_segments_are_never_blended():
    for seg in ("neocloud", "hyperscaler"):
        res = TermPricingEngine.compute(seg)
        by_id = {q["id"]: q for q in TERM_QUOTES}
        for c in res.cells:
            assert all(by_id[i]["segment"] == seg for i in c.quote_ids), (seg, c.family, c.term)


def test_cluster_products_are_excluded_not_averaged():
    quotes = [_q("Lambda", "H100", (14, 365), 5.54, min_gpus=256), _q("Civo", "H100", (365, 365), 2.69)]
    res = TermPricingEngine.compute("neocloud", families=["H100"], quotes=quotes, references=[])
    assert [e["id"] for e in res.excluded] == ["lambda_h100_14-365_256g"]
    cell = next(c for c in res.cells if c.term == "1Y")
    assert cell.value == 2.69 and cell.sellers == ["Civo"]


def test_fill_marks_estimates_and_matches_ratios_by_seller():
    quotes = [
        _q("Azure", "H100", (1095, 1095), 5.40, segment="hyperscaler"),
        _q("Azure", "H100", (1825, 1825), 4.92, segment="hyperscaler"),
        _q("GCP", "H100", (1095, 1095), 4.86, segment="hyperscaler"),   # has 3Y, no 5Y: must not enter the ratio
        _q("GCP", "A100", (1095, 1095), 3.50, segment="hyperscaler"),
    ]
    kw = dict(families=["A100", "H100"], quotes=quotes, references=[])
    plain = TermPricingEngine.compute("hyperscaler", fill=False, **kw)
    assert not [c for c in plain.cells if c.status == "estimated"]
    a5 = next(c for c in plain.cells if c.family == "A100" and c.term == "5Y")
    assert a5.status == "none" and a5.value is None

    filled = TermPricingEngine.compute("hyperscaler", fill=True, **kw)
    a5 = next(c for c in filled.cells if c.family == "A100" and c.term == "5Y")
    assert a5.status == "estimated" and a5.n_sellers == 0 and a5.quote_ids == []
    assert a5.value == pytest.approx(3.50 * (4.92 / 5.40), abs=1e-4), "Azure's own 3Y->5Y ratio, not GCP 3Y vs Azure 5Y"
    assert "Azure H100" in a5.estimate
    observed = {(c.family, c.term): c.value for c in plain.cells if c.status == "observed"}
    assert all(c.value == observed[(c.family, c.term)] for c in filled.cells if c.status == "observed")


def test_shipped_catalog_readings():
    hyp = TermPricingEngine.compute("hyperscaler")
    neo = TermPricingEngine.compute("neocloud")
    assert "2Y" in hyp.empty_terms, "no hyperscaler publishes a 2-year term"
    assert "5Y" in neo.empty_terms, "no neocloud in the catalog publishes a 5-year term"
    cell = lambda res, f, t: next(c for c in res.cells if c.family == f and c.term == t)
    # Commitment is cheaper than on-demand at the long end, in both segments.
    for res in (hyp, neo):
        assert cell(res, "H100", "3Y").value < cell(res, "H100", "OD").value
    # Hyperscaler list sits above the neocloud market at every H100 term both publish.
    for t in ("OD", "1Y", "3Y"):
        assert cell(hyp, "H100", t).value > cell(neo, "H100", t).value


@pytest.fixture
def client():
    temp_dir = tempfile.mkdtemp()
    yield TestClient(create_app(db_storage_dir=temp_dir))
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_api_term_pricing(client):
    res = client.get("/api/term-pricing?segment=hyperscaler&fill=true")
    assert res.status_code == 200
    data = res.json()
    assert data["segment"] == "hyperscaler" and data["fill"] is True
    assert len(data["cells"]) == len(data["families"]) * len(data["terms"])
    assert data["coverage"]["estimated"] > 0
    assert all(q["segment"] == "hyperscaler" for q in data["quotes"])


def test_api_term_pricing_rejects_unknown_segment(client):
    assert client.get("/api/term-pricing?segment=everyone").status_code == 422
