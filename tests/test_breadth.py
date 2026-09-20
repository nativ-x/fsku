"""Nebius and Together join the tape; Lambda's table is current; H200 has real breadth."""

import shutil
import tempfile
import pytest
from fsku.core.database import FSKUDb
from fsku.core.fix import FixEngine
from fsku.sync.engine import SyncEngine
from fsku.sync.providers.nebius import NebiusAdapter
from fsku.sync.providers.together import TogetherAdapter
from fsku.sync.providers.lambda_cloud import LambdaCloudAdapter
from fsku.sync.providers.coreweave import CoreWeaveAdapter


@pytest.fixture
def temp_db():
    d = tempfile.mkdtemp()
    db = FSKUDb(storage_dir=d); db.observations.clear()
    yield db
    shutil.rmtree(d, ignore_errors=True)


def test_new_adapters_are_dated_catalogs():
    for cls in (NebiusAdapter, TogetherAdapter, LambdaCloudAdapter):
        assert cls.mode == "catalog" and cls.catalog_as_of == "2026-09-20" and cls.tier == "Specialized cloud", cls.__name__


@pytest.mark.asyncio
async def test_rows_are_consistent():
    for cls in (NebiusAdapter, TogetherAdapter, LambdaCloudAdapter):
        rows = await cls().fetch_observations()
        assert rows, cls.__name__
        for r in rows:
            assert abs(r.total / r.gpuCount - r.perGpu) < 1e-6, r.id
            assert r.basis in ("On-demand", "Spot", "Reserved"), r.id


@pytest.mark.asyncio
async def test_h200_neocloud_fix_has_breadth_from_catalogs_alone(temp_db):
    await SyncEngine(db=temp_db, adapters=[CoreWeaveAdapter, NebiusAdapter, TogetherAdapter, LambdaCloudAdapter]).resync(create_snapshot=False)
    fx = FixEngine.compute(temp_db.observations.find(), "H200")
    neo = fx.segments["neocloud"]
    assert set(neo.providers) >= {"CoreWeave", "Nebius", "Together AI"}
    assert all(c.basis != "Reserved" for c in neo.constituents), "reserved is a term product and stays out of the Fix"
    assert fx.excluded.get("term_basis", 0) >= 1


@pytest.mark.asyncio
async def test_lambda_no_longer_carries_the_stale_h100_rate():
    rows = await LambdaCloudAdapter().fetch_observations()
    h100 = {r.gpu: r.perGpu for r in rows if r.gpu.startswith("H100 SXM")}
    assert h100 == {"H100 SXM (1x)": 4.29, "H100 SXM (HGX 8x)": 3.99}
