"""The FSKU Fix: one published reading per GPU family, segmented by who is selling.

Why this exists. The per-SKU index tables report the median of every listed
price for a SKU, and on this tape three hyperscaler retail list rows sit in a
six-row H100 median. Nobody rents H100 hours at list; the two paid benchmarks
(Ornn OCPI, Silicon Data SDH100RT) are within a few percent of each other and
both exclude exactly that. FSKU is meant to publish the same kind of number for
free, so the Fix:

  * takes the family's SXM/OAM rows only (PCIe and NVL are different products),
    both topologies (HGX 8x nodes and 1x pods, per-GPU normalized);
  * takes spot-market bases only -- On-demand, Spot, Retail API -- never term
    products (Capacity block, Reserved);
  * splits sellers into two segments and never blends them:
        neocloud     Community, Secure, Specialized cloud   <- the headline
        hyperscaler  Hyperscaler retail list                <- published beside it
  * winsorizes each segment at the 10th/90th percentile and takes the median.

There is no volume weighting because there is no free source of trade volume;
the Fix is a listed-price reading, and says so in `method`.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fsku.core.pricing import PricingEngine

NEOCLOUD_TIERS = ("Community", "Secure", "Specialized cloud")
HYPERSCALER_TIERS = ("Hyperscaler",)
SPOT_BASES = ("On-demand", "Spot", "Retail API")
EXCLUDED_FORM_FACTORS = ("PCIe", "NVL")  # substrings of the gpu name
WINSOR = 0.10
METHOD = "listed-price; SXM/OAM rows, both topologies, per-GPU; spot bases only; segmented by seller tier; 10/90 winsorized median; unweighted"


class FixConstituent(BaseModel):
    id: str
    provider: str
    sku: str
    basis: str
    tier: Optional[str]
    per_gpu: float
    provenance: str
    recorded_at: str


class FixReading(BaseModel):
    segment: str
    value: Optional[float] = Field(description="10/90 winsorized median $/GPU-hr; null if no constituents")
    n: int
    providers: List[str]
    tiers: List[str]
    low: Optional[float]
    high: Optional[float]
    trimmed_mean_10: Optional[float]
    simple_mean: Optional[float]
    constituents: List[FixConstituent]


class FixResult(BaseModel):
    family: str
    computed_at: str
    as_of: str = Field(description="Newest recorded_at among headline constituents -- how fresh the number actually is")
    headline_segment: str = "neocloud"
    headline: Optional[float]
    segments: Dict[str, FixReading]
    excluded: Dict[str, int] = Field(description="Rows of this family left out, by reason")
    method: str = METHOD


class FixEngine:
    @classmethod
    def universe(cls, observations: List[Dict[str, Any]], family: str):
        fam = family.upper()
        rows, excluded = [], {"other_family": 0, "pcie_or_nvl": 0, "term_basis": 0, "no_price": 0, "no_tier": 0}
        for r in observations:
            if (PricingEngine.extract_gpu_family(r.get("gpu", "")) or "").upper() != fam:
                excluded["other_family"] += 1
                continue
            if any(x in r.get("gpu", "") for x in EXCLUDED_FORM_FACTORS):
                excluded["pcie_or_nvl"] += 1
                continue
            if r.get("basis") not in SPOT_BASES:
                excluded["term_basis"] += 1
                continue
            if not r.get("perGpu") or r["perGpu"] <= 0:
                excluded["no_price"] += 1
                continue
            if not r.get("tier"):
                excluded["no_tier"] += 1
                continue
            rows.append(r)
        excluded = {k: v for k, v in excluded.items() if v}
        return rows, excluded

    @staticmethod
    def winsorized_median(values: List[float], w: float = WINSOR) -> float:
        lo = PricingEngine.quantile(values, w)
        hi = PricingEngine.quantile(values, 1 - w)
        return round(PricingEngine.median([min(max(v, lo), hi) for v in values]), 4)

    @classmethod
    def reading(cls, segment: str, rows: List[Dict[str, Any]]) -> FixReading:
        rows = sorted(rows, key=lambda r: r["perGpu"])
        prices = [r["perGpu"] for r in rows]
        return FixReading(
            segment=segment,
            value=cls.winsorized_median(prices) if prices else None,
            n=len(rows),
            providers=sorted({r.get("provider", "") for r in rows}),
            tiers=sorted({r.get("tier") for r in rows if r.get("tier")}),
            low=round(prices[0], 4) if prices else None,
            high=round(prices[-1], 4) if prices else None,
            trimmed_mean_10=round(PricingEngine.trimmed_mean(prices, 0.10), 4) if prices else None,
            simple_mean=round(sum(prices) / len(prices), 4) if prices else None,
            constituents=[
                FixConstituent(id=r.get("id", ""), provider=r.get("provider", ""), sku=r.get("gpu", ""),
                               basis=r.get("basis", ""), tier=r.get("tier"), per_gpu=round(r["perGpu"], 4),
                               provenance=r.get("provenance", "seed"), recorded_at=r.get("recorded_at", ""))
                for r in rows
            ],
        )

    @classmethod
    def compute(cls, observations: List[Dict[str, Any]], family: str = "H100") -> FixResult:
        rows, excluded = cls.universe(observations, family)
        neo = [r for r in rows if r.get("tier") in NEOCLOUD_TIERS]
        hyper = [r for r in rows if r.get("tier") in HYPERSCALER_TIERS]
        segments = {"neocloud": cls.reading("neocloud", neo), "hyperscaler": cls.reading("hyperscaler", hyper)}
        head = segments["neocloud"]
        return FixResult(
            family=family.upper(),
            computed_at=datetime.now(timezone.utc).isoformat(),
            as_of=max((c.recorded_at for c in head.constituents), default=""),
            headline=head.value,
            segments=segments,
            excluded=excluded,
        )
