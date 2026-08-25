"""Tests for FSKU multi-provider resync engine."""

import shutil
import tempfile
import pytest
from fsku.core.database import FSKUDb
from fsku.sync.engine import SyncEngine
from fsku.sync.providers.azure import AzureAdapter
from fsku.sync.providers.runpod import RunPodAdapter
from fsku.sync.providers.coreweave import CoreWeaveAdapter

@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db = FSKUDb(storage_dir=temp_dir)
    yield db
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.mark.asyncio
async def test_sync_adapters_fetch():
    runpod = RunPodAdapter()
    rp_obs = await runpod.fetch_observations()
    assert len(rp_obs) > 0
    assert any("H100" in o.gpu for o in rp_obs)
    assert any(o.form_factor == "SXM5" for o in rp_obs)

    cw = CoreWeaveAdapter()
    cw_obs = await cw.fetch_observations()
    assert len(cw_obs) > 0
    assert any(o.provider == "CoreWeave" for o in cw_obs)
    assert any(o.topology and "HGX 8x" in o.topology for o in cw_obs)

    az = AzureAdapter()
    az_obs = await az.fetch_observations()
    assert len(az_obs) > 0
    assert any(o.form_factor == "SXM5" for o in az_obs)

@pytest.mark.asyncio
async def test_sync_engine_resync_cycle(temp_db):
    engine = SyncEngine(db=temp_db)

    log1 = await engine.resync(label="Initial test sync")
    assert log1.status in ("success", "partial")
    assert log1.added_count > 0
    assert temp_db.observations.count() > 0
    assert temp_db.snapshots.count() >= 1

    log2 = await engine.resync(label="Second test sync")
    assert log2.added_count == 0
    assert log2.unchanged_count > 0

@pytest.mark.asyncio
async def test_sync_dry_run(temp_db):
    engine = SyncEngine(db=temp_db)
    init_count = temp_db.observations.count()

    log = await engine.resync(dry_run=True)
    assert log.added_count > 0
    assert temp_db.observations.count() == init_count
