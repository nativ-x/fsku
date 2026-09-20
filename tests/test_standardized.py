"""One vote per seller, its best term; median across sellers; needs three sellers."""

from fsku.core.database import FSKUDb
from fsku.core.fix import FixEngine


def _row(i, provider, gpu, per_gpu, tier, basis="On-demand"):
    return {"id": f"o{i}", "provider": provider, "gpu": gpu, "instance": "x", "perGpu": per_gpu, "total": per_gpu,
            "gpuCount": 1, "vram": 80, "source": provider.lower(), "tier": tier, "basis": basis,
            "provenance": "catalog", "recorded_at": "2026-09-20"}


def test_one_vote_per_seller_on_its_best_term():
    rows = [
        _row(1, "A", "H100 SXM (HGX 8x)", 4.00, "Specialized cloud"),
        _row(2, "A", "H100 SXM (HGX 8x)", 2.00, "Specialized cloud", basis="Spot"),      # A's vote
        _row(3, "B", "H100 SXM (1x)", 3.50, "Community"),                                # B's vote
        _row(4, "C", "H100 SXM (HGX 8x)", 3.80, "Specialized cloud"),
        _row(5, "C", "H100 SXM (HGX 8x)", 3.00, "Specialized cloud", basis="Reserved"),  # C's vote: reserved counts here
        _row(6, "Azure", "H100 SXM (HGX 8x)", 12.29, "Hyperscaler"),                    # not neocloud: no vote
        _row(7, "A", "H100 PCIe", 1.00, "Community"),                                     # different product: no vote
    ]
    sr = FixEngine.compute(rows, "H100").standardized
    assert sr.n_sellers == 3 and sr.sellers == ["A", "B", "C"]
    assert [q.id for q in sr.quotes] == ["o2", "o5", "o3"]
    assert sr.value == 3.0 and sr.low == 2.0 and sr.high == 3.5


def test_fewer_than_three_sellers_is_null_not_a_number():
    rows = [_row(1, "A", "H100 SXM (1x)", 2.0, "Community"), _row(2, "B", "H100 SXM (1x)", 3.0, "Community")]
    sr = FixEngine.compute(rows, "H100").standardized
    assert sr.value is None and sr.n_sellers == 2


def test_shipped_tape_standardized_sits_below_listed_and_has_breadth():
    for fam in ("H100", "H200", "B200"):
        fx = FixEngine.compute(FSKUDb().observations.find(), fam)
        assert fx.standardized.value is not None, fam
        assert fx.standardized.n_sellers >= 3, fam
        assert fx.standardized.value <= fx.headline, f"{fam}: best-term across sellers cannot exceed the on-demand ask median"


def test_settlement_records_standardized(tmp_path):
    import asyncio
    from fsku.core.settle import SettlementEngine
    db = FSKUDb(storage_dir=tmp_path)
    res = asyncio.run(SettlementEngine(db).settle(do_sync=False))
    h100 = next(r for r in res.rows if r.family == "H100")
    assert h100.standardized is not None and h100.standardized_n >= 3 and len(h100.standardized_ids) == h100.standardized_n
