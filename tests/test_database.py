"""Tests for FSKUDb embedded NoSQL document store."""

import shutil
import tempfile
from pathlib import Path
import pytest
from fsku.core.database import FSKUDb

@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db = FSKUDb(storage_dir=temp_dir)
    yield db
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_db_crud_operations(temp_db):
    col = temp_db.collection("test_col")
    assert col.count() == 0

    doc1 = col.insert({"id": "d1", "provider": "RunPod", "rate": 2.69, "tags": ["fast", "gpu"]})
    assert doc1["id"] == "d1"
    assert col.count() == 1

    col.insert_many([
        {"id": "d2", "provider": "CoreWeave", "rate": 6.15, "tags": ["hgx"]},
        {"id": "d3", "provider": "AWS", "rate": 5.19, "tags": ["cloud"]},
        {"id": "d4", "provider": "Azure", "rate": 12.29, "tags": ["cloud", "enterprise"]},
    ])
    assert col.count() == 4

    found = col.find_by_id("d2")
    assert found is not None
    assert found["provider"] == "CoreWeave"

    expensive = col.find({"rate": {"$gt": 5.0}}, sort_by="rate", reverse=True)
    assert len(expensive) == 3
    assert expensive[0]["provider"] == "Azure"

    contains_filter = col.find({"tags": {"$in": ["enterprise"]}})
    assert len(contains_filter) == 1
    assert contains_filter[0]["id"] == "d4"

    updated = col.update_by_id("d1", {"rate": 2.75})
    assert updated is True
    assert col.find_by_id("d1")["rate"] == 2.75

    deleted = col.delete_by_id("d3")
    assert deleted is True
    assert col.count() == 3
    assert col.find_by_id("d3") is None

def test_db_snapshot_creation(temp_db):
    temp_db.observations.clear()

    temp_db.observations.insert_many([
        {"id": "o1", "provider": "RunPod", "gpu": "H100 SXM", "basis": "On-demand", "gpuCount": 1, "total": 2.69, "perGpu": 2.69, "source": "runpod"},
        {"id": "o2", "provider": "CoreWeave", "gpu": "H100 SXM", "basis": "Spot", "gpuCount": 8, "total": 19.71, "perGpu": 2.46375, "source": "coreweave"},
    ])

    snap = temp_db.create_snapshot(label="Test Checkpoint")
    assert snap["id"].startswith("snap_")
    assert snap["observation_count"] == 2
    assert snap["label"] == "Test Checkpoint"
    assert len(snap["observations"]) == 2

    saved_snap = temp_db.snapshots.find_by_id(snap["id"])
    assert saved_snap is not None
    assert saved_snap["checksum"] == snap["checksum"]

    # Verify SHA-256 integrity
    v = temp_db.verify_snapshot(snap["id"])
    assert v["verified"] is True
    assert v["observation_count"] == 2
    assert v["computed_checksum"] == snap["checksum"]
