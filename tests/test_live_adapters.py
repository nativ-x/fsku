"""RunPod publishes both tiers live; Vast.ai publishes marketplace depth; outages are visible, not laundered."""

import shutil
import tempfile
import pytest
from fsku.core.database import FSKUDb
from fsku.sync.engine import SyncEngine
from fsku.sync.providers.runpod import RunPodAdapter
from fsku.sync.providers.vast import VastAdapter


@pytest.fixture
def temp_db():
    d = tempfile.mkdtemp()
    db = FSKUDb(storage_dir=d)
    db.observations.clear()
    yield db
    shutil.rmtree(d, ignore_errors=True)


RUNPOD_API = {"data": {"gpuTypes": [
    {"id": "NVIDIA H100 80GB HBM3", "displayName": "H100 SXM", "memoryInGb": 80, "securePrice": 3.49, "communityPrice": 2.69},
    {"id": "NVIDIA H100 PCIe", "displayName": "H100 PCIe", "memoryInGb": 80, "securePrice": 2.89, "communityPrice": 1.99},
    {"id": "NVIDIA H200 NVL", "displayName": "H200 NVL", "memoryInGb": 143, "securePrice": 3.79, "communityPrice": 0.5},
]}}


@pytest.mark.asyncio
async def test_runpod_publishes_secure_and_community_rows(monkeypatch):
    async def post(self, url, body):
        self.requests_attempted += 1; self.requests_succeeded += 1
        return RUNPOD_API
    monkeypatch.setattr(RunPodAdapter, "_safe_post_json", post)
    rows = await RunPodAdapter().fetch_observations()
    h100 = {(r.tier, r.perGpu) for r in rows if r.gpu == "H100 SXM (1x)"}
    assert h100 == {("Secure", 3.49), ("Community", 2.69)}
    assert all(r.provenance == "live" for r in rows if r.gpu in ("H100 SXM (1x)", "H100 PCIe"))
    assert {r.instance for r in rows if r.gpu == "H100 SXM (1x)"} == {"Secure Cloud", "Community Cloud"}
    # SKUs absent from the response fall back, visibly
    fb = [r for r in rows if r.provenance == "fallback"]
    assert {r.gpu for r in fb} >= {"H200 SXM (1x)", "B300 SXM (1x)"}
    assert all(r.tier == "Community" and r.recorded_at == RunPodAdapter.catalog_as_of for r in fb)


@pytest.mark.asyncio
async def test_runpod_outage_falls_back_to_community_constants(monkeypatch):
    async def post(self, url, body):
        self.requests_attempted += 1; self.notes.append("POST -> simulated outage"); return None
    monkeypatch.setattr(RunPodAdapter, "_safe_post_json", post)
    a = RunPodAdapter()
    rows = await a.fetch_observations()
    assert rows and all(r.provenance == "fallback" and r.tier == "Community" for r in rows)
    assert len(a.fallbacks) == len(rows)
    assert not any(r.tier == "Secure" for r in rows), "no constant exists for Secure; never invent one"


def test_vast_aggregation_reports_depth():
    offers = [
        {"gpu_name": "H100 SXM", "num_gpus": 8, "dph_total": 24.0, "verification": "verified"},
        {"gpu_name": "H100 SXM", "num_gpus": 1, "dph_total": 3.2, "verification": "unverified"},
        {"gpu_name": "H100 SXM", "num_gpus": 2, "dph_total": 7.0, "verification": "verified"},
        {"gpu_name": "RTX 3090", "num_gpus": 1, "dph_total": 0.2, "verification": "verified"},   # unmapped: ignored
        {"gpu_name": "H100 SXM", "num_gpus": 0, "dph_total": 9.9, "verification": "verified"},   # bad row: ignored
    ]
    agg = VastAdapter.aggregate(offers)
    assert set(agg) == {"H100 SXM"}
    a = agg["H100 SXM"]
    assert a["n"] == 3 and a["n_verified"] == 2
    assert a["median"] == 3.2 and a["min"] == 3.0 and a["gpus_per_offer"] == [1, 2, 8]


@pytest.mark.asyncio
async def test_vast_publishes_one_row_per_sku_with_depth(monkeypatch):
    async def get(self, url, params=None):
        self.requests_attempted += 1; self.requests_succeeded += 1
        return {"offers": [{"gpu_name": "H100 SXM", "num_gpus": 1, "dph_total": 3.1, "verification": "verified"},
                           {"gpu_name": "H100 SXM", "num_gpus": 1, "dph_total": 3.3, "verification": "verified"}]}
    monkeypatch.setattr(VastAdapter, "_safe_get_json", get)
    rows = await VastAdapter().fetch_observations()
    (r,) = rows
    assert r.provider == "Vast.ai" and r.gpu == "H100 SXM (1x)" and r.tier == "Community" and r.provenance == "live"
    assert r.perGpu == 3.2 and r.metadata["n"] == 2 and r.instance == "marketplace median ask"


@pytest.mark.asyncio
async def test_vast_outage_publishes_nothing_and_keeps_existing_rows(temp_db, monkeypatch):
    temp_db.observations.insert({"id": "obs_vast_h100_sxm_1x", "provider": "Vast.ai", "gpu": "H100 SXM (1x)",
                                 "instance": "marketplace median ask", "basis": "On-demand", "tier": "Community",
                                 "gpuCount": 1, "total": 3.0, "perGpu": 3.0, "vram": 80, "source": "vast",
                                 "recorded_at": "2026-09-19T00:00:00+00:00", "provenance": "live"})
    async def get(self, url, params=None):
        self.requests_attempted += 1; self.notes.append("GET -> HTTP 503"); return None
    monkeypatch.setattr(VastAdapter, "_safe_get_json", get)
    log = await SyncEngine(db=temp_db, adapters=[VastAdapter]).resync(create_snapshot=False)
    assert log.status == "failed"  # nothing fetched at all this run
    assert any("Vast.ai" in e for e in log.errors)
    kept = temp_db.observations.find_by_id("obs_vast_h100_sxm_1x")
    assert kept and kept["recorded_at"].startswith("2026-09-19"), "outage must not delete or re-date yesterday's row"


@pytest.mark.asyncio
async def test_engine_deprecates_only_for_providers_that_answered(temp_db, monkeypatch):
    temp_db.observations.insert({"id": "old_rp", "provider": "RunPod", "gpu": "H100 SXM (1x)", "instance": "GPU model",
                                 "basis": "On-demand", "tier": "Community", "gpuCount": 1, "total": 2.69, "perGpu": 2.69,
                                 "vram": 80, "source": "runpod", "recorded_at": "2026-08-25", "provenance": "catalog"})
    async def post(self, url, body):
        self.requests_attempted += 1; self.requests_succeeded += 1; return RUNPOD_API
    monkeypatch.setattr(RunPodAdapter, "_safe_post_json", post)
    log = await SyncEngine(db=temp_db, adapters=[RunPodAdapter]).resync(create_snapshot=False)
    assert temp_db.observations.find_by_id("old_rp") is None, "the pre-tier 'GPU model' row is superseded by tiered rows"
    assert log.added_count >= 2
