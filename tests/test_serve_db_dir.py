"""`fsku serve --db-dir` must put every server read and write in that directory,
and no request may move the server's database anywhere else."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner
from uvicorn.importer import import_from_string

from fsku.cli.main import app as cli
from fsku.core import database
from fsku.core.database import DB_DIR_ENV

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_DB = REPO_ROOT / "data" / "fsku_db"


def _fingerprint(d: Path):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir()) if p.is_file()}


def _serve(args, monkeypatch):
    """Run `fsku serve ...` up to the point uvicorn takes over, then build the app
    exactly as uvicorn would from what serve handed it."""
    calls = []
    monkeypatch.setattr("uvicorn.run", lambda target, **kw: calls.append((target, kw)))
    result = CliRunner().invoke(cli, ["serve", *args])
    assert result.exit_code == 0, result.output
    (target, kw), = calls
    loaded = import_from_string(target)
    return (loaded() if kw.get("factory") else loaded), kw


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv(DB_DIR_ENV, raising=False)                   # serve sets it; restored afterwards
    monkeypatch.setattr(database, "_GLOBAL_DB", database._GLOBAL_DB)  # so is the singleton


def test_db_dir_takes_every_write_and_leaves_the_repo_tape_alone(monkeypatch, tmp_path):
    db_dir = tmp_path / "served_db"
    before = _fingerprint(REPO_DB)

    app, kw = _serve(["--db-dir", str(db_dir), "--reload"], monkeypatch)
    assert kw["factory"] is True and kw["reload"] is True
    assert os.environ[DB_DIR_ENV] == str(db_dir.resolve()), "a --reload worker inherits the directory via the environment"

    client = TestClient(app)
    res = client.post("/api/settle?sync=false")
    assert res.status_code == 200, res.text
    snap_id = res.json()["snapshot_id"]

    assert _fingerprint(REPO_DB) == before, "the committed tape in data/fsku_db must not change"
    assert {"snapshots.json", "fix_history.json"} <= set(_fingerprint(db_dir))
    assert snap_id in (db_dir / "snapshots.json").read_text(encoding="utf-8")
    assert any(s["id"] == snap_id for s in client.get("/api/snapshots").json()), "reads come from the same directory"


def test_requests_cannot_repoint_the_database(monkeypatch, tmp_path):
    db_dir = tmp_path / "served_db"
    app, _ = _serve(["--db-dir", str(db_dir)], monkeypatch)
    client = TestClient(app)

    elsewhere = tmp_path / "elsewhere"
    assert client.get("/api/health", params={"storage_dir": str(elsewhere)}).status_code == 200
    assert not elsewhere.exists(), "a query parameter must not create or select a database directory"
    assert database.get_db().storage_dir == db_dir.resolve()

    spec = client.get("/api/openapi.json").json()
    params = {p["name"] for ops in spec["paths"].values() for op in ops.values() for p in op.get("parameters", [])}
    assert "storage_dir" not in params


def test_without_db_dir_the_default_is_unchanged(monkeypatch):
    _, kw = _serve([], monkeypatch)
    assert DB_DIR_ENV not in os.environ
    assert kw["factory"] is True


def test_a_fresh_server_process_reads_the_directory_from_the_environment(tmp_path):
    """Under --reload uvicorn builds the app in a new process, so the directory
    has to arrive through the environment, not through anything set in the CLI."""
    db_dir = tmp_path / "reload_db"
    code = ("from uvicorn.importer import import_from_string; from fsku.core import database; "
            "import_from_string('fsku.api.app:create_app')(); print(database.get_db().storage_dir)")
    before = _fingerprint(REPO_DB)
    out = subprocess.run([sys.executable, "-c", code], env={**os.environ, DB_DIR_ENV: str(db_dir)},
                         cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    assert Path(out) == db_dir
    assert (db_dir / "observations.json").exists()
    assert _fingerprint(REPO_DB) == before
