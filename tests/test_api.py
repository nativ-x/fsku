"""Tests for FastAPI REST endpoints."""

import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
from fsku.api.app import create_app
from fsku.core.database import FSKUDb

@pytest.fixture
def client_and_db():
    temp_dir = tempfile.mkdtemp()
    app = create_app(db_storage_dir=temp_dir)
    client = TestClient(app)
    yield client, FSKUDb(storage_dir=temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_api_health(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "database" in data

def test_api_kpis(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/kpis")
    assert res.status_code == 200
    data = res.json()
    assert "kpis" in data
    assert "memory_economics" in data

def test_api_index_summary(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/index/summary?method=median")
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0
    h100 = next(x for x in items if "H100" in x["sku"])
    assert h100["index_price"] > 0
    assert h100["confidence"] in ("HIGH", "MODERATE", "LOW (SPARSE)")

def test_api_index_sensitivity(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/index/sensitivity")
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0
    assert "baseline_median" in items[0]
    assert "trimmed_mean_10" in items[0]
    assert "provider_balanced" in items[0]

def test_api_index_ablation(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/index/ablation")
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0
    assert "provider_removed" in items[0]
    assert "ablated_price" in items[0]

def test_api_providers_matrix(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/providers/matrix")
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0
    assert "delta_vs_index_pct" in items[0]

def test_api_history_series(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/history")
    assert res.status_code == 200
    data = res.json()
    assert "series" in data
    assert "snapshots_count" in data

def test_api_multi_curve_compare(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/forward-curves/compare?families=H100,H200,B200&horizon=36")
    assert res.status_code == 200
    data = res.json()
    assert "curves" in data
    assert "H100" in data["curves"]
    assert "B200" in data["curves"]

def test_api_observations_and_filter(client_and_db):
    client, _ = client_and_db

    res = client.get("/api/observations")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0

    res_h100 = client.get("/api/observations?gpu=H100")
    assert res_h100.status_code == 200
    for item in res_h100.json()["items"]:
        assert "H100" in item["gpu"]

    res_spot = client.get("/api/observations?basis=Spot")
    assert res_spot.status_code == 200
    for item in res_spot.json()["items"]:
        assert item["basis"] == "Spot"

def test_api_forward_curve(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/forward-curve?family=H100&basis=firm&cadence=24&carry_rate=5.0&horizon=36")
    assert res.status_code == 200
    data = res.json()
    assert data["family"] == "H100"
    assert data["S0"] > 0
    assert len(data["points"]) == 37

def test_api_specs_and_sources(client_and_db):
    client, _ = client_and_db
    res_specs = client.get("/api/specs")
    assert res_specs.status_code == 200
    assert len(res_specs.json()) >= 5

    res_sources = client.get("/api/sources")
    assert res_sources.status_code == 200
    assert len(res_sources.json()) >= 5

def test_api_sync_endpoint(client_and_db):
    client, _ = client_and_db
    res = client.post("/api/sync?dry_run=true")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("success", "partial")
    assert "duration_ms" in data

def test_api_exports(client_and_db):
    client, _ = client_and_db

    res_csv = client.get("/api/export/csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert b"Provider,GPU" in res_csv.content

    res_fwd = client.get("/api/export/forward-csv?family=H100")
    assert res_fwd.status_code == 200
    assert "text/csv" in res_fwd.headers["content-type"]
    assert b"GPU Family,Tenor Months" in res_fwd.content

    res_hist = client.get("/api/export/history-csv")
    assert res_hist.status_code == 200
    assert "text/csv" in res_hist.headers["content-type"]
    assert b"Snapshot ID,Timestamp" in res_hist.content
