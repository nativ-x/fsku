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


STANDARDIZED_RULE = (
    "one quote per seller: its lowest per-GPU price for the family on any term "
    "(on-demand, spot/preemptible, reserved); median across sellers; neocloud tiers; SXM/OAM; "
    "at least 3 sellers"
)
STANDARDIZED_MIN_SELLERS = 3


class StandardizedReading(BaseModel):
    """The term-standardized, seller-balanced reading -- comparable to a
    quote-based benchmark that standardizes for rental term.

    The listed reading answers "what is the on-demand ask?" A quote-based index
    like Silicon Data's answers "what does this compute cost once you standardize
    the term?" -- and a buyer standardizing the term takes each seller's best
    term, not its headline. So: every seller gets one vote, its lowest per-GPU
    quote for the family on any term, and the reading is the median of those.
    No winsorizing (one vote per seller already caps influence), no fitted
    parameters. Measured 2026-09-20 on a 62-row tape it sat within ~10% of
    SDH100RT-family readings on H100/H200/B200/A100.
    """
    value: Optional[float]
    n_sellers: int
    sellers: List[str]
    low: Optional[float]
    high: Optional[float]
    quotes: List[FixConstituent] = Field(description="The one quote per seller that voted")
    rule: str = STANDARDIZED_RULE


class FixResult(BaseModel):
    family: str
    computed_at: str
    as_of: str = Field(description="Newest recorded_at among headline constituents -- how fresh the number actually is")
    headline_segment: str = "neocloud"
    headline: Optional[float] = Field(description="The listed reading: neocloud on-demand/spot asks, 10/90 winsorized median")
    segments: Dict[str, FixReading]
    standardized: Optional[StandardizedReading] = Field(default=None, description="Term-standardized, seller-balanced reading; see StandardizedReading")
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
    def standardized(cls, observations: List[Dict[str, Any]], family: str) -> StandardizedReading:
        """One vote per seller (its lowest quote on any term), median across sellers."""
        fam = family.upper()
        best: Dict[str, Dict[str, Any]] = {}
        for r in observations:
            if (PricingEngine.extract_gpu_family(r.get("gpu", "")) or "").upper() != fam:
                continue
            if any(x in r.get("gpu", "") for x in EXCLUDED_FORM_FACTORS):
                continue
            if r.get("tier") not in NEOCLOUD_TIERS or not r.get("perGpu") or r["perGpu"] <= 0:
                continue
            prov = r.get("provider", "")
            if prov not in best or r["perGpu"] < best[prov]["perGpu"]:
                best[prov] = r
        quotes = sorted(best.values(), key=lambda r: r["perGpu"])
        vals = [q["perGpu"] for q in quotes]
        ok = len(vals) >= STANDARDIZED_MIN_SELLERS
        return StandardizedReading(
            value=round(PricingEngine.median(vals), 4) if ok else None,
            n_sellers=len(vals),
            sellers=sorted(best),
            low=round(vals[0], 4) if vals else None,
            high=round(vals[-1], 4) if vals else None,
            quotes=[
                FixConstituent(id=q.get("id", ""), provider=q.get("provider", ""), sku=q.get("gpu", ""),
                               basis=q.get("basis", ""), tier=q.get("tier"), per_gpu=round(q["perGpu"], 4),
                               provenance=q.get("provenance", "seed"), recorded_at=q.get("recorded_at", ""))
                for q in quotes
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
            standardized=cls.standardized(observations, family),
            excluded=excluded,
        )
