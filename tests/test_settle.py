"""One settlement = one verified snapshot + one traceable history row per family, idempotent per day."""

import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
from fsku.core.database import FSKUDb
from fsku.core.settle import SettlementEngine, SETTLED_FAMILIES


@pytest.fixture
def temp_db():
    d = tempfile.mkdtemp()
    db = FSKUDb(storage_dir=d)  # seeded from the shipped tape
    yield db
    shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_settle_without_sync_is_traceable_and_idempotent(temp_db):
    eng = SettlementEngine(temp_db)
    res = await eng.settle(do_sync=False)
    assert res.verified is True
    assert len(res.rows) == len(SETTLED_FAMILIES)
    h100 = next(r for r in res.rows if r.family == "H100")
    assert h100.neocloud is not None and h100.neocloud_n > 0
    assert h100.snapshot_id == res.snapshot_id and h100.checksum == res.checksum
    snap = temp_db.snapshots.find_by_id(res.snapshot_id)
    assert snap["provenance"] == "settle"
    # every constituent id resolves to a row in the settled snapshot
    ids = {o["id"] for o in snap["observations"]}
    assert set(h100.constituent_ids["neocloud"]) <= ids and set(h100.constituent_ids["hyperscaler"]) <= ids
    assert temp_db.verify_snapshot(res.snapshot_id)["verified"] is True

    before = temp_db.collection("fix_history").count()
    res2 = await eng.settle(do_sync=False)
    assert temp_db.collection("fix_history").count() == before, "same day settles replace, not append"
    assert eng.history_for("H100")[-1]["snapshot_id"] == res2.snapshot_id


def test_shipped_snapshots_are_labelled():
    db = FSKUDb()
    snaps = db.snapshots.find()
    assert all(s.get("provenance") in ("seed", "live", "settle") for s in snaps)
    assert sum(1 for s in snaps if s.get("provenance") == "seed") == 4


def test_new_snapshots_carry_provenance_outside_the_checksum(tmp_path):
    db = FSKUDb(storage_dir=tmp_path)
    snap = db.create_snapshot(label="t")
    assert snap["provenance"] == "live"
    assert db.verify_snapshot(snap["id"])["verified"] is True


def test_api_history_and_settle(tmp_path):
    from fsku.api.app import create_app
    client = TestClient(create_app(db_storage_dir=str(tmp_path)))
    assert client.get("/api/fix/history?family=H100").json()["rows"] == []
    res = client.post("/api/settle?sync=false")
    assert res.status_code == 200 and res.json()["verified"] is True
    rows = client.get("/api/fix/history?family=H100").json()["rows"]
    assert len(rows) == 1 and rows[0]["neocloud"] is not None
