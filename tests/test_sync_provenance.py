"""The sync report must say where each row came from, and must not call a
run 'success' when a live adapter substituted a constant."""

import shutil
import tempfile
import pytest
from fsku.core.database import FSKUDb
from fsku.sync.engine import SyncEngine
from fsku.sync.base import BaseProviderAdapter
from fsku.sync.providers.azure import AzureAdapter
from fsku.sync.providers.runpod import RunPodAdapter
from fsku.sync.providers.coreweave import CoreWeaveAdapter
from fsku.sync.providers.aws import AWSAdapter
from fsku.sync.providers.gcp import GCPAdapter
from fsku.sync.providers.lambda_cloud import LambdaCloudAdapter
from fsku.sync.providers.vast import VastAdapter

from fsku.sync.providers.nebius import NebiusAdapter
from fsku.sync.providers.together import TogetherAdapter

CATALOG_ADAPTERS = [CoreWeaveAdapter, AWSAdapter, GCPAdapter, LambdaCloudAdapter, NebiusAdapter, TogetherAdapter]
LIVE_ADAPTERS = [AzureAdapter, RunPodAdapter, VastAdapter]


@pytest.fixture
def temp_db():
    d = tempfile.mkdtemp()
    db = FSKUDb(storage_dir=d)
    db.observations.clear()
    yield db
    shutil.rmtree(d, ignore_errors=True)


def test_every_adapter_declares_its_mode():
    for cls in CATALOG_ADAPTERS:
        assert cls.mode == "catalog", cls.__name__
        assert cls.catalog_as_of, f"{cls.__name__} must say when its constants were captured"
    for cls in LIVE_ADAPTERS:
        assert cls.mode == "live", cls.__name__
    assert AzureAdapter.catalog_as_of and RunPodAdapter.catalog_as_of, "live adapters with fallbacks must date them"
    assert VastAdapter.catalog_as_of is None, "Vast has no fallback table and must not pretend to"


def test_user_agent_points_at_this_repo():
    ua = RunPodAdapter().get_headers()["User-Agent"]
    assert "github.com/nativ-x/fsku" in ua
    assert "sku-futures" not in ua


@pytest.mark.asyncio
async def test_catalog_rows_are_tagged_and_dated_not_restamped(temp_db):
    engine = SyncEngine(db=temp_db, adapters=CATALOG_ADAPTERS)
    log = await engine.resync(create_snapshot=False)

    assert log.providers_live == []
    assert sorted(log.providers_catalog) == sorted(c.provider_name for c in CATALOG_ADAPTERS)
    assert log.live_count == 0 and log.fallback_count == 0
    assert log.catalog_count == log.added_count > 0
    assert log.status == "success"  # catalog is declared, not a failure

    as_of = {c.provider_name: c.catalog_as_of for c in CATALOG_ADAPTERS}
    for row in temp_db.observations.find():
        assert row["provenance"] == "catalog", row["id"]
        assert row["recorded_at"] == as_of[row["provider"]], "catalog rows must carry their adapter's capture date, not the sync time"

    assert len(log.provider_reports) == len(CATALOG_ADAPTERS)
    for r in log.provider_reports:
        assert r.mode == "catalog"
        assert r.requests_attempted == 0
        assert r.catalog == r.observations > 0


@pytest.mark.asyncio
async def test_live_adapter_fallback_is_visible_and_downgrades_status(temp_db, monkeypatch):
    async def api_is_down(self, url, params=None):
        self.requests_attempted += 1
        self.notes.append(f"GET {url} -> simulated outage")
        return None

    monkeypatch.setattr(AzureAdapter, "_safe_get_json", api_is_down)
    engine = SyncEngine(db=temp_db, adapters=[AzureAdapter])
    log = await engine.resync(create_snapshot=False)

    assert log.providers_live == ["Azure"]
    assert log.live_count == 0
    assert log.fallback_count == log.added_count == 3
    assert log.status == "partial", "substituted constants are not a successful poll"

    (r,) = log.provider_reports
    assert r.mode == "live"
    assert r.requests_attempted == 3 and r.requests_succeeded == 0
    assert len(r.fallbacks) == 3
    assert all("substituted" in f for f in r.fallbacks)

    for row in temp_db.observations.find():
        assert row["provenance"] == "fallback"
        assert row["recorded_at"] == AzureAdapter.catalog_as_of


@pytest.mark.asyncio
async def test_live_adapter_success_is_tagged_live(temp_db, monkeypatch):
    async def api_answers(self, url, params=None):
        self.requests_attempted += 1
        self.requests_succeeded += 1
        return {"Items": [{"unitPrice": 42.0, "skuName": "ND96isrH100v5"}]}

    monkeypatch.setattr(AzureAdapter, "_safe_get_json", api_answers)
    engine = SyncEngine(db=temp_db, adapters=[AzureAdapter])
    log = await engine.resync(create_snapshot=False)

    assert log.status == "success"
    assert log.live_count == 3 and log.fallback_count == 0
    for row in temp_db.observations.find():
        assert row["provenance"] == "live"
        assert row["recorded_at"] != AzureAdapter.catalog_as_of


@pytest.mark.asyncio
async def test_untagged_row_from_live_adapter_is_refused(temp_db):
    from fsku.core.models import Observation

    class SloppyLive(BaseProviderAdapter):
        provider_id = "sloppy"
        provider_name = "Sloppy"
        source_url = "https://example.invalid"
        mode = "live"

        async def fetch_observations(self):
            return [Observation(provider="Sloppy", gpu="H100 PCIe", instance="x", total=1.0, perGpu=1.0, vram=80, source="sloppy")]

    with pytest.raises(RuntimeError, match="must tag every row"):
        await SyncEngine(db=temp_db, adapters=[SloppyLive]).resync(create_snapshot=False)


@pytest.mark.asyncio
async def test_catalog_adapter_without_as_of_is_refused(temp_db):
    from fsku.core.models import Observation

    class UndatedCatalog(BaseProviderAdapter):
        provider_id = "undated"
        provider_name = "Undated"
        source_url = "https://example.invalid"
        mode = "catalog"

        async def fetch_observations(self):
            return [Observation(provider="Undated", gpu="H100 PCIe", instance="x", total=1.0, perGpu=1.0, vram=80, source="undated")]

    with pytest.raises(RuntimeError, match="catalog_as_of"):
        await SyncEngine(db=temp_db, adapters=[UndatedCatalog]).resync(create_snapshot=False)
