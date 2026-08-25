"""FastAPI routes and REST API endpoints for FSKU benchmark index & forward curves."""

from __future__ import annotations
import csv
import io
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from fsku import __version__
from fsku.core.database import FSKUDb, get_db
from fsku.core.forward_curve import ForwardCurveEngine
from fsku.core.models import (
    ForwardCurveRequest,
    ForwardCurveResult,
    HardwareSpec,
    MarketSnapshot,
    MethodologySensitivity,
    MultiCurveComparisonResult,
    Observation,
    ProviderPriceRow,
    SkuIndexSummary,
    SourceAblationResult,
    SourceRef,
    SyncLog,
)
from fsku.core.pricing import PricingEngine
from fsku.sync.engine import SyncEngine

router = APIRouter(prefix="/api", tags=["FSKU Core Benchmark API"])

@router.get("/health")
def health_check(db: FSKUDb = Depends(get_db)):
    """API health status and database statistics."""
    return {
        "status": "healthy",
        "service": "FSKU Benchmark & Settlement Intelligence Platform",
        "version": __version__,
        "database": {
            "observations": db.observations.count(),
            "snapshots": db.snapshots.count(),
            "specs": db.specs.count(),
            "sources": db.sources.count(),
            "sync_logs": db.sync_logs.count(),
        },
    }

@router.get("/kpis")
def get_market_kpis(db: FSKUDb = Depends(get_db)):
    """Executive market metrics, dispersion, and memory economics."""
    observations = db.observations.find()
    specs = db.specs.find()
    kpis = PricingEngine.calculate_kpis(observations)
    mem_econ = PricingEngine.calculate_memory_economics(observations, specs)
    return {
        "kpis": kpis,
        "memory_economics": mem_econ,
    }

@router.get("/index/summary", response_model=List[SkuIndexSummary])
def get_sku_index_summaries(
    method: str = Query("median", description="Index methodology: median, trimmed_10, trimmed_20, provider_balanced, simple_mean, gpu_weighted"),
    db: FSKUDb = Depends(get_db),
):
    """Retrieve computed spot indices for all tracked GPU SKUs under the selected methodology."""
    observations = db.observations.find()
    return PricingEngine.calculate_sku_index_summaries(observations, method=method)

@router.get("/index/sensitivity", response_model=List[MethodologySensitivity])
def get_methodology_sensitivity(db: FSKUDb = Depends(get_db)):
    """Examine index price sensitivity across 6 standard aggregation methodologies."""
    observations = db.observations.find()
    return PricingEngine.calculate_sensitivity(observations)

@router.get("/index/ablation", response_model=List[SourceAblationResult])
def get_source_ablation(
    sku: Optional[str] = Query(None, description="Optional target SKU filter (e.g. H100 SXM, B200)"),
    db: FSKUDb = Depends(get_db),
):
    """Examine index resilience by assessing the price delta when each data provider is ablated."""
    observations = db.observations.find()
    return PricingEngine.calculate_ablation(observations, target_sku=sku)

@router.get("/providers/matrix", response_model=List[ProviderPriceRow])
def get_provider_pricing_matrix(db: FSKUDb = Depends(get_db)):
    """Cross-provider pricing matrix with basis normalization and delta vs benchmark index."""
    observations = db.observations.find()
    sources = db.sources.find()
    return PricingEngine.calculate_provider_matrix(observations, sources=sources)

@router.get("/history")
def get_historical_indices(db: FSKUDb = Depends(get_db)):
    """Time-series index benchmarks reconstructed across historical snapshots."""
    snaps = db.snapshots.find(sort_by="timestamp")
    series_by_sku: Dict[str, List[Dict[str, Any]]] = {}
    timestamps = []

    for s in snaps:
        ts = s.get("timestamp", "")
        timestamps.append(ts)

        if "sku_indices" in s and s["sku_indices"]:
            for sku, price in s["sku_indices"].items():
                series_by_sku.setdefault(sku, []).append({
                    "timestamp": ts,
                    "date": ts[:10] if len(ts) >= 10 else ts,
                    "price": price,
                    "snapshot_id": s.get("id"),
                    "label": s.get("label", ""),
                })
        elif "observations" in s and s["observations"]:
            by_sku = PricingEngine.calculate_sku_index_summaries(s["observations"])
            for summary in by_sku:
                series_by_sku.setdefault(summary.sku, []).append({
                    "timestamp": ts,
                    "date": ts[:10] if len(ts) >= 10 else ts,
                    "price": summary.index_price,
                    "snapshot_id": s.get("id"),
                    "label": s.get("label", ""),
                })

    return {
        "timestamps": timestamps,
        "snapshots_count": len(snaps),
        "series": series_by_sku,
    }

@router.get("/observations")
def list_observations(
    provider: Optional[str] = Query(None, description="Filter by provider name"),
    gpu: Optional[str] = Query(None, description="Filter by GPU family or name"),
    basis: Optional[str] = Query(None, description="Filter by price basis (On-demand, Spot, etc.)"),
    region: Optional[str] = Query(None, description="Filter by region"),
    search: Optional[str] = Query(None, description="Full-text search query across fields"),
    sort_by: Optional[str] = Query("perGpu", description="Field to sort by"),
    reverse: bool = Query(False, description="Sort descending"),
    limit: Optional[int] = Query(None, description="Max records to return"),
    offset: int = Query(0, description="Offset for pagination"),
    db: FSKUDb = Depends(get_db),
):
    """Retrieve filtered, sorted price observations from the current tape."""
    query: Dict[str, Any] = {}
    if provider:
        query["provider"] = {"$contains": provider}
    if gpu and gpu != "all":
        query["gpu"] = {"$contains": gpu}
    if basis and basis != "all":
        query["basis"] = basis
    if region and region != "all":
        query["region"] = {"$contains": region}

    all_rows = db.observations.find(filter_query=query, sort_by=sort_by, reverse=reverse)

    if search:
        s = search.lower().strip()
        all_rows = [
            r for r in all_rows
            if s in f"{r.get('provider', '')} {r.get('gpu', '')} {r.get('instance', '')} {r.get('basis', '')} {r.get('region', '')}".lower()
        ]

    total_matched = len(all_rows)
    paged = all_rows[offset : (offset + limit) if limit else None]

    return {
        "total": total_matched,
        "offset": offset,
        "limit": limit,
        "items": paged,
    }

@router.post("/observations", status_code=status.HTTP_201_CREATED)
def create_observation(obs: Observation, db: FSKUDb = Depends(get_db)):
    """Manually append or record a custom observation to the tape."""
    obs.perGpu = Observation.compute_normalized(obs.total, obs.gpuCount)
    saved = db.observations.insert(obs.model_dump())
    return saved

@router.get("/observations/{obs_id}")
def get_observation(obs_id: str, db: FSKUDb = Depends(get_db)):
    """Retrieve a single observation by ID."""
    obs = db.observations.find_by_id(obs_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")
    return obs

@router.delete("/observations/{obs_id}")
def delete_observation(obs_id: str, db: FSKUDb = Depends(get_db)):
    """Delete an observation by ID."""
    deleted = db.observations.delete_by_id(obs_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Observation not found")
    return {"deleted": True, "id": obs_id}

@router.post("/forward-curve", response_model=ForwardCurveResult)
def calculate_forward_curve(req: ForwardCurveRequest, db: FSKUDb = Depends(get_db)):
    """Calculate implied forward curve term structure with custom parameters."""
    observations = db.observations.find()
    res = ForwardCurveEngine.calculate_forward_curve(observations, req)
    if not res:
        raise HTTPException(status_code=404, detail=f"No pricing observations found for GPU family '{req.family}'")
    return res

@router.get("/forward-curve", response_model=ForwardCurveResult)
def get_forward_curve(
    family: str = Query("H100", description="GPU family (H100, H200, B200, B300, A100)"),
    basis: str = Query("firm", description="Price basis anchor: firm, all, or spot"),
    cadence: int = Query(24, ge=6, le=60, description="Architecture cadence in months"),
    carry_rate: float = Query(5.0, description="Annual carry + scarcity rate in %"),
    horizon: int = Query(36, ge=6, le=60, description="Forward curve horizon in months"),
    db: FSKUDb = Depends(get_db),
):
    """GET endpoint to calculate implied forward curve."""
    req = ForwardCurveRequest(
        family=family,
        basis=basis,
        cadence=cadence,
        carry_rate=carry_rate,
        horizon=horizon,
    )
    observations = db.observations.find()
    res = ForwardCurveEngine.calculate_forward_curve(observations, req)
    if not res:
        raise HTTPException(status_code=404, detail=f"No pricing observations found for GPU family '{family}'")
    return res

@router.get("/forward-curves/compare")
def compare_forward_curves(
    families: str = Query("H100,H200,B200,B300,A100", description="Comma-separated GPU families"),
    basis: str = Query("firm", description="Price basis anchor: firm, all, or spot"),
    cadence: int = Query(24, ge=6, le=60),
    carry_rate: float = Query(5.0),
    horizon: int = Query(36, ge=6, le=60),
    db: FSKUDb = Depends(get_db),
):
    """Simultaneously calculate and align multiple forward curves for cross-SKU term structure analysis."""
    fam_list = [f.strip() for f in families.split(",") if f.strip()]
    observations = db.observations.find()
    return ForwardCurveEngine.compare_forward_curves(
        observations=observations,
        families=fam_list,
        basis=basis,
        cadence=cadence,
        carry_rate=carry_rate,
        horizon=horizon,
    )

@router.get("/specs")
def list_specs(db: FSKUDb = Depends(get_db)):
    """Official hardware engineering specs (VRAM, memory bandwidth, TDP, peak compute)."""
    return db.specs.find(sort_by="name")

@router.get("/sources")
def list_sources(db: FSKUDb = Depends(get_db)):
    """Primary source provenance references."""
    return db.sources.find()

@router.post("/sync", response_model=SyncLog)
async def trigger_resync(
    provider: Optional[str] = Query(None, description="Optional provider filter (e.g. azure, runpod, coreweave)"),
    dry_run: bool = Query(False, description="Preview changes without updating database"),
    label: Optional[str] = Query(None, description="Optional snapshot label"),
    db: FSKUDb = Depends(get_db),
):
    """Trigger an on-demand market feed resynchronization across all or selected providers."""
    engine = SyncEngine(db=db)
    try:
        log = await engine.resync(
            provider_filter=provider,
            dry_run=dry_run,
            snapshot_label=label,
        )
        return log
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync execution failed: {str(e)}")

@router.get("/sync/history")
def get_sync_history(limit: int = Query(20, ge=1, le=100), db: FSKUDb = Depends(get_db)):
    """Audit log of past resync runs."""
    return db.sync_logs.find(sort_by="started_at", reverse=True, limit=limit)

@router.get("/snapshots")
def list_snapshots(limit: int = Query(50, ge=1, le=200), db: FSKUDb = Depends(get_db)):
    """List historical point-in-time market snapshots."""
    snaps = db.snapshots.find(sort_by="timestamp", reverse=True, limit=limit)
    summaries = []
    for s in snaps:
        s_copy = dict(s)
        s_copy.pop("observations", None)
        summaries.append(s_copy)
    return summaries

@router.get("/snapshots/{snap_id}")
def get_snapshot(snap_id: str, db: FSKUDb = Depends(get_db)):
    """Retrieve full detail and observation array of a specific snapshot."""
    snap = db.snapshots.find_by_id(snap_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap

@router.get("/export/csv")
def export_observations_csv(db: FSKUDb = Depends(get_db)):
    """Export current observation tape as formatted CSV."""
    rows = db.observations.find(sort_by="perGpu")
    sources_map = {s["id"]: s for s in db.sources.find()}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Provider",
        "GPU / Instance",
        "Instance Name",
        "Basis",
        "GPU Count",
        "Published USD/hr",
        "Normalized USD/GPU-hr",
        "VRAM GB",
        "Region",
        "Source URL",
        "Recorded At",
    ])

    for r in rows:
        src = sources_map.get(r.get("source", ""), {})
        writer.writerow([
            r.get("provider", ""),
            r.get("gpu", ""),
            r.get("instance", ""),
            r.get("basis", ""),
            r.get("gpuCount", 1),
            f"{r.get('total', 0):.4f}",
            f"{r.get('perGpu', 0):.4f}",
            r.get("vram", 0),
            r.get("region", "Global"),
            src.get("url", ""),
            r.get("recorded_at", ""),
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="fsku-market-observations.csv"'},
    )

@router.get("/export/forward-csv")
def export_forward_csv(
    family: str = Query("H100"),
    basis: str = Query("firm"),
    cadence: int = Query(24),
    carry_rate: float = Query(5.0),
    horizon: int = Query(36),
    db: FSKUDb = Depends(get_db),
):
    """Export calculated forward curve term structure as CSV."""
    req = ForwardCurveRequest(
        family=family,
        basis=basis,
        cadence=cadence,
        carry_rate=carry_rate,
        horizon=horizon,
    )
    observations = db.observations.find()
    res = ForwardCurveEngine.calculate_forward_curve(observations, req)
    if not res:
        raise HTTPException(status_code=404, detail="Could not derive forward curve for export")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "GPU Family",
        "Tenor Months",
        "Cash Anchor USD/GPU-hr",
        "Implied Forward USD/GPU-hr",
        "Lower IQR USD/GPU-hr",
        "Upper IQR USD/GPU-hr",
        "Change vs Cash %",
        "Tech Deflation Annual",
        "Carry Scarcity Annual",
        "Net Annual Factor",
        "Basis Mode",
    ])

    for pt in res.points:
        writer.writerow([
            res.family,
            pt.m,
            f"{res.S0:.4f}",
            f"{pt.base:.4f}",
            f"{pt.low:.4f}",
            f"{pt.high:.4f}",
            f"{pt.chg_pct * 100:.2f}%",
            f"{res.d * 100:.2f}%",
            f"{res.carry:.2f}%",
            f"{res.annual_factor:.4f}",
            res.mode,
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="fsku-forward-curve-{family.lower()}.csv"'},
    )

@router.get("/export/history-csv")
def export_history_csv(db: FSKUDb = Depends(get_db)):
    """Export historical spot index benchmark time-series as CSV."""
    snaps = db.snapshots.find(sort_by="timestamp")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Snapshot ID", "Timestamp", "Label", "Observation Count", "Median Rate", "H100 SXM", "H200", "B200", "A100 SXM", "MI300X"])

    for s in snaps:
        sku_idx = s.get("sku_indices", {})
        writer.writerow([
            s.get("id"),
            s.get("timestamp"),
            s.get("label", ""),
            s.get("observation_count", 0),
            f"{s.get('median_rate', 0):.2f}",
            f"{sku_idx.get('H100 SXM', '')}",
            f"{sku_idx.get('H200', '')}",
            f"{sku_idx.get('B200', '')}",
            f"{sku_idx.get('A100 SXM', '')}",
            f"{sku_idx.get('MI300X', '')}",
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="fsku-historical-indices.csv"'},
    )
