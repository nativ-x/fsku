"""Every row on the tape says which capacity tier it prices."""

import json
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from fsku.core.database import FSKUDb
from fsku.core.pricing import PricingEngine
from fsku.sync.engine import SyncEngine
from fsku.sync.base import BaseProviderAdapter
from fsku.sync.providers.azure import AzureAdapter
from fsku.sync.providers.runpod import RunPodAdapter
from fsku.sync.providers.coreweave import CoreWeaveAdapter
from fsku.sync.providers.aws import AWSAdapter
from fsku.sync.providers.gcp import GCPAdapter
from fsku.sync.providers.lambda_cloud import LambdaCloudAdapter

VALID = {"Community", "Secure", "Specialized cloud", "Hyperscaler"}


@pytest.fixture
def temp_db():
    d = tempfile.mkdtemp()
    db = FSKUDb(storage_dir=d)
    db.observations.clear()
    yield db
    shutil.rmtree(d, ignore_errors=True)


def test_every_adapter_declares_a_tier():
    for cls in (AzureAdapter, RunPodAdapter, CoreWeaveAdapter, AWSAdapter, GCPAdapter, LambdaCloudAdapter):
        assert cls.tier in VALID, cls.__name__
    assert RunPodAdapter.tier == "Community", "RUNPOD_CATALOG holds communityPrice, not securePrice"


def test_shipped_tape_is_fully_labelled():
    for path in ("data/fsku_db/observations.json", "fsku/data/seeds/observations.json"):
        rows = json.loads(Path(path).read_text())
        assert rows, path
        for r in rows:
            assert r.get("tier") in VALID, f"{path}: {r['id']} has tier {r.get('tier')!r}"


@pytest.mark.asyncio
async def test_sync_stamps_tier_on_every_row(temp_db):
    engine = SyncEngine(db=temp_db, adapters=[RunPodAdapter, CoreWeaveAdapter, AWSAdapter, GCPAdapter, LambdaCloudAdapter])
    await engine.resync(create_snapshot=False)
    rows = temp_db.observations.find()
    assert rows
    for r in rows:
        assert r["tier"] in VALID, r["id"]
    assert all(r["tier"] == "Community" for r in rows if r["provider"] == "RunPod")
    assert all(r["tier"] == "Hyperscaler" for r in rows if r["provider"] in ("AWS", "Google Cloud"))


@pytest.mark.asyncio
async def test_untiered_row_is_refused(temp_db):
    from fsku.core.models import Observation

    class NoTier(BaseProviderAdapter):
        provider_id = "notier"
        provider_name = "NoTier"
        source_url = "https://example.invalid"
        mode = "catalog"
        catalog_as_of = "2026-01-01"

        async def fetch_observations(self):
            return [Observation(provider="NoTier", gpu="H100 PCIe", instance="x", total=1.0, perGpu=1.0, vram=80, source="notier")]

    with pytest.raises(RuntimeError, match="capacity tier"):
        await SyncEngine(db=temp_db, adapters=[NoTier]).resync(create_snapshot=False)


def test_sku_summary_reports_tiers_present():
    db = FSKUDb()
    summaries = {s.sku: s for s in PricingEngine.calculate_sku_index_summaries(db.observations.find())}
    hgx = summaries["H100 SXM (HGX 8x)"]
    assert set(hgx.tiers) >= {"Hyperscaler", "Specialized cloud"}, "the HGX 8x index mixes tiers and must say so"
    assert summaries["H100 PCIe"].tiers == ["Community"]


def test_api_filters_by_tier():
    from fsku.api.app import create_app
    client = TestClient(create_app())
    res = client.get("/api/observations?tier=Community")
    assert res.status_code == 200
    items = res.json()["items"]
    assert items
    assert all(i["tier"] == "Community" for i in items)
    assert all(i["provider"] == "RunPod" for i in items)
