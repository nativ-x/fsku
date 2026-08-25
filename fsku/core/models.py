"""Data models and schemas for FSKU."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
import uuid

class SourceRef(BaseModel):
    """Primary source provenance metadata."""
    id: str
    name: str
    domain: str
    url: str
    desc: str
    adapter: Optional[str] = None

class HardwareSpec(BaseModel):
    """Official hardware engineering specifications."""
    id: Optional[str] = None
    name: str
    gen: str
    vram: int = Field(description="VRAM in GB")
    type: str = Field(description="Memory architecture, e.g. HBM3, HBM3e")
    bw: float = Field(description="Memory bandwidth in TB/s")
    power: int = Field(description="Max TDP / power limit in Watts")
    compute: str = Field(description="Peak tensor compute, e.g. FP8 3.96 PFLOPS*")
    src: str = Field(description="Source reference key")
    release_year: Optional[int] = None

class Observation(BaseModel):
    """Normalized compute price observation record."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    provider: str
    gpu: str
    instance: str
    basis: Literal["On-demand", "Spot", "Capacity block", "Retail API", "Reserved"] = "On-demand"
    gpuCount: int = Field(ge=1, default=1)
    total: float = Field(ge=0.0, description="Published hourly server or instance rate")
    perGpu: float = Field(ge=0.0, description="Normalized hourly rate per GPU unit")
    vram: int = Field(ge=1, description="VRAM in GB per GPU")
    source: str
    region: Optional[str] = "Global / Multiple"
    form_factor: Optional[str] = Field(default="SXM", description="Hardware form factor e.g. SXM5, SXM4, PCIe, NVL, OAM")
    interconnect: Optional[str] = Field(default="NVLink", description="Interconnect architecture e.g. NVLink 4 (900 GB/s), PCIe Gen5 (64 GB/s)")
    topology: Optional[str] = Field(default="HGX 8x Clustered", description="Node chassis deployment scale e.g. HGX 8x Clustered, 1x Standalone, Dual-GPU NVL")
    recorded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    snapshot_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def compute_normalized(cls, total: float, gpu_count: int) -> float:
        if gpu_count <= 0:
            raise ValueError("gpu_count must be positive")
        return round(total / gpu_count, 6)

class TechDecayPair(BaseModel):
    """Cross-generation matched provider price compression observation."""
    provider: str
    older: str
    newer: str
    older_rate: float
    newer_rate: float
    annual_decay: float

class TechDecaySummary(BaseModel):
    """Inferred technology decay summary."""
    decay: float
    observations: List[TechDecayPair] = Field(default_factory=list)

class ForwardTenorPoint(BaseModel):
    """Implied price point for a specific forward horizon tenor."""
    m: int = Field(description="Tenor in months")
    base: float = Field(description="Implied forward $/GPU-hour")
    low: float = Field(description="Interquartile lower bound $/GPU-hour")
    high: float = Field(description="Interquartile upper bound $/GPU-hour")
    chg_pct: float = Field(description="Percentage change vs cash anchor")

class ForwardCurveRequest(BaseModel):
    """Request payload to derive an implied forward curve."""
    family: str = "H100"
    basis: Literal["firm", "all", "spot"] = "firm"
    cadence: int = Field(default=24, ge=6, le=60, description="Architecture cadence in months")
    carry_rate: float = Field(default=5.0, description="Annual carry + scarcity rate in percent (-25% to 100%)")
    horizon: int = Field(default=36, ge=6, le=60, description="Forward curve horizon in months")

class ForwardCurveResult(BaseModel):
    """Calculated implied term structure from the current tape."""
    family: str
    mode: str
    cadence: int
    carry: float
    horizon: int
    fallback: bool
    S0: float
    q25: float
    q75: float
    d: float
    annual_factor: float
    tech: TechDecaySummary
    points: List[ForwardTenorPoint]
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class MarketKpis(BaseModel):
    """Executive KPI metrics across the tape."""
    observation_count: int
    source_count: int
    gpu_families_count: int
    median_observed_rate: float
    h100_dispersion: float
    lowest_h100: Dict[str, Any]
    highest_h100: Dict[str, Any]
    median_h100: float

class SyncLog(BaseModel):
    """Audit log entry for a resync run."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str
    completed_at: str
    status: Literal["success", "partial", "failed"]
    duration_ms: int
    providers_polled: List[str]
    added_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    total_active: int = 0
    snapshot_id: Optional[str] = None
    errors: List[str] = Field(default_factory=list)

class MarketSnapshot(BaseModel):
    """Point-in-time immutable market snapshot."""
    id: str
    timestamp: str
    label: str
    observation_count: int
    source_count: int
    gpu_count: int
    median_rate: float
    h100_dispersion: float
    checksum: str
    observations: List[Observation] = Field(default_factory=list)

class SkuIndexSummary(BaseModel):
    """Comprehensive summary for an individual GPU SKU benchmark index."""
    sku: str
    family: str
    form_factor: Optional[str] = "SXM"
    interconnect: Optional[str] = "NVLink"
    topology: Optional[str] = "HGX 8x Clustered"
    vram: int
    index_price: float
    methodology: str = "Median"
    basis_spread: float
    min_price: float
    max_price: float
    iqr_low: float
    iqr_high: float
    dispersion_ratio: float
    observation_count: int
    provider_count: int
    confidence: Literal["HIGH", "MODERATE", "LOW (SPARSE)"]
    market_status: Literal["ACTIVE", "INDICATIVE", "EMERGING"]
    change_24h: Optional[float] = 0.0

class MethodologySensitivity(BaseModel):
    """Index price sensitivity across calculation methodologies."""
    sku: str
    baseline_median: float
    trimmed_mean_10: float
    trimmed_mean_20: float
    provider_balanced: float
    simple_mean: float
    gpu_weighted_mean: float
    max_divergence_pct: float

class SourceAblationResult(BaseModel):
    """Impact on index price when removing a specific data source/provider."""
    provider_removed: str
    sku: str
    original_price: float
    ablated_price: float
    delta_abs: float
    delta_pct: float
    observations_remaining: int
    impact_level: Literal["NEGLIGIBLE", "LOW", "MODERATE", "HIGH"]

class ProviderPriceRow(BaseModel):
    """Normalized rate and benchmark comparison for a provider."""
    provider: str
    sku: str
    instance: str
    basis: str
    total_rate: float
    gpu_count: int
    per_gpu_rate: float
    index_price: float
    delta_vs_index_pct: float
    vram: int
    region: str
    source_url: str

class MultiCurveComparisonResult(BaseModel):
    """Multiple GPU forward curves for comparative term structure analysis."""
    curves: Dict[str, ForwardCurveResult]
    tenors: List[int]
    relative_spreads: Dict[str, Dict[int, float]]
