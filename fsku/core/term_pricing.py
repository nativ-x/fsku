"""Term pricing: published $/GPU-hour by commitment length x GPU family.

The Fix answers "what does an hour cost today?". This answers "what does it
cost if you commit?", from prices sellers publish for reserved instances,
savings plans, committed-use discounts, capacity blocks and monthly/annual
contracts (fsku/sync/term_catalog.py). Rules:

  * Segments are never blended: `neocloud` and `hyperscaler` are priced
    separately, the same split as the Fix.
  * A single node is the unit. Quotes that require a multi-node cluster
    (min_gpus > 8) are listed as excluded, not averaged in -- the pooling bias
    the contract-unit resolution exists to remove.
  * A quote applies to every term bucket inside the commitment range it is sold
    for: an AWS Capacity Block (any length 1-182 days) prices 1M, 3M and 6M; a
    Together 31-90 day reservation prices 3M only.
  * One vote per seller per cell -- its lowest published per-GPU price for that
    term -- and the cell is the median of the votes. No winsorizing, no weights.

Empty cells stay empty unless `fill` is asked for. Then an empty cell is
estimated from the same family's nearest observed term, scaled by the median
ratio between those two terms across the families that have both. Estimates are
never chained, never cross segments, and carry the arithmetic that made them.
"""

from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from fsku.core.pricing import PricingEngine
from fsku.sync.term_catalog import TERM_CATALOG_AS_OF, TERM_QUOTES, TERM_REFERENCES

TERMS = [("OD", "On-demand", 0), ("1M", "1M", 30), ("3M", "3M", 90), ("6M", "6M", 180),
         ("1Y", "1Y", 365), ("2Y", "2Y", 730), ("3Y", "3Y", 1095), ("5Y", "5Y", 1825)]
FAMILIES = ["A100", "H100", "H200", "B200", "B300"]
MAX_UNIT_GPUS = 8
RULE = ("published term prices; one vote per seller per cell (its lowest per-GPU price for that term); "
        "median across sellers; single node (<= 8 GPUs); neocloud and hyperscaler never blended; unweighted")


class TermQuote(BaseModel):
    id: str
    provider: str
    segment: Literal["neocloud", "hyperscaler"]
    family: str
    instance: str
    option: str = Field(description="What the seller calls the product")
    min_days: int = Field(description="Shortest commitment this price is sold for (0 = on-demand)")
    max_days: int = Field(description="Longest commitment this price is sold for")
    gpus: int = Field(description="GPUs in the unit the published price is for")
    min_gpus: int = Field(description="Smallest quantity the seller will commit for at this price")
    form_factor: str
    per_gpu: float
    published: str = Field(description="The figure as published, in its own unit")
    math: str = Field(description="How per_gpu was derived from the published figure")
    region: str = ""
    source: str
    captured: str
    notes: Optional[str] = None


class TermBucket(BaseModel):
    key: str
    label: str
    days: int


class TermCell(BaseModel):
    family: str
    term: str
    value: Optional[float] = Field(description="Median of seller votes, or the estimate; null if neither")
    status: Literal["observed", "estimated", "none"]
    n_sellers: int = 0
    sellers: List[str] = Field(default_factory=list)
    low: Optional[float] = None
    high: Optional[float] = None
    quote_ids: List[str] = Field(default_factory=list, description="The one quote per seller that voted")
    estimate: Optional[str] = Field(default=None, description="The arithmetic behind an estimated cell")


class TermReference(BaseModel):
    segment: str
    family: str
    term: str
    low: float
    high: float
    label: str
    source: str
    captured: str


class TermPricingResult(BaseModel):
    segment: str
    fill: bool
    families: List[str]
    terms: List[TermBucket]
    empty_terms: List[str] = Field(default_factory=list, description="Terms no seller in this segment publishes, for any family")
    cells: List[TermCell] = Field(description="Family-major, in `families` x `terms` order")
    quotes: List[TermQuote] = Field(description="Every eligible quote; each cell's quote_ids name the ones that voted")
    excluded: List[Dict[str, Any]] = Field(description="Quotes in this segment left out, with the reason")
    references: List[TermReference]
    coverage: Dict[str, int]
    captured: str = TERM_CATALOG_AS_OF
    rule: str = RULE


class TermPricingEngine:
    @staticmethod
    def covers(q: Dict[str, Any], days: int) -> bool:
        return q["min_days"] <= days <= q["max_days"]

    @classmethod
    def _estimate(cls, cells: Dict[tuple, TermCell], votes: Dict[tuple, Dict[str, float]], families: List[str], keys: List[str]) -> None:
        """Fill empty cells from the family's nearest observed term, scaled by the
        median same-seller ratio between the two terms in other families. Ratios
        are matched by seller: comparing one seller's 3Y with another's 5Y would
        measure seller mix, not term."""
        for fam in families:
            for ti, term in enumerate(keys):
                cell = cells[(fam, term)]
                if cell.status != "none":
                    continue
                # Nearest observed term of this family first; shorter term wins a tie.
                refs = sorted((r for r in keys if cells[(fam, r)].status == "observed"),
                              key=lambda r: (abs(keys.index(r) - ti), keys.index(r) > ti))
                for ref in refs:
                    pairs = [(g, p, votes[(g, term)][p] / votes[(g, ref)][p]) for g in families if g != fam
                             for p in votes[(g, term)] if p in votes[(g, ref)]]
                    if not pairs:
                        continue
                    ratio = PricingEngine.median([r for _, _, r in pairs])
                    base = cells[(fam, ref)].value
                    cell.value = round(base * ratio, 4)
                    cell.status = "estimated"
                    cell.estimate = (f"{fam} {ref} ${base:.2f} x {ratio:.3f}, the median same-seller {ref}->{term} ratio of "
                                     + ", ".join(f"{p} {g}" for g, p, _ in pairs))
                    break

    @classmethod
    def compute(cls, segment: str = "neocloud", fill: bool = False, families: Optional[List[str]] = None,
                quotes: Optional[List[Dict[str, Any]]] = None,
                references: Optional[List[Dict[str, Any]]] = None) -> TermPricingResult:
        families = [f.upper() for f in (families or FAMILIES)]
        quotes = TERM_QUOTES if quotes is None else quotes
        references = TERM_REFERENCES if references is None else references

        pool = [q for q in quotes if q["segment"] == segment and q["family"].upper() in families]
        eligible, excluded = [], []
        for q in pool:
            if q["min_gpus"] > MAX_UNIT_GPUS:
                excluded.append({"id": q["id"], "provider": q["provider"], "family": q["family"], "option": q["option"],
                                 "per_gpu": q["per_gpu"], "source": q["source"],
                                 "reason": f"cluster product: min {q['min_gpus']} GPUs; term pricing covers a single node"})
            else:
                eligible.append(q)

        cells: Dict[tuple, TermCell] = {}
        votes: Dict[tuple, Dict[str, float]] = {}
        for fam in families:
            for key, _, days in TERMS:
                best: Dict[str, Dict[str, Any]] = {}
                for q in eligible:
                    if q["family"].upper() == fam and cls.covers(q, days):
                        if q["provider"] not in best or q["per_gpu"] < best[q["provider"]]["per_gpu"]:
                            best[q["provider"]] = q
                ballot = sorted(best.values(), key=lambda q: q["per_gpu"])
                vals = [q["per_gpu"] for q in ballot]
                votes[(fam, key)] = {q["provider"]: q["per_gpu"] for q in ballot}
                cells[(fam, key)] = TermCell(
                    family=fam, term=key,
                    value=round(PricingEngine.median(vals), 4) if vals else None,
                    status="observed" if vals else "none",
                    n_sellers=len(vals), sellers=[q["provider"] for q in ballot],
                    low=round(vals[0], 4) if vals else None, high=round(vals[-1], 4) if vals else None,
                    quote_ids=[q["id"] for q in ballot],
                )

        # A term no seller in this segment publishes for any family is dropped
        # and named, not drawn as an empty column (no hyperscaler sells 2 years).
        keys = [k for k, _, _ in TERMS if any(cells[(f, k)].status == "observed" for f in families)]
        empty_terms = [k for k, _, _ in TERMS if k not in keys]
        if fill:
            cls._estimate(cells, votes, families, keys)

        ordered = [cells[(f, k)] for f in families for k in keys]
        return TermPricingResult(
            segment=segment, fill=fill, families=families,
            terms=[TermBucket(key=k, label=lbl, days=d) for k, lbl, d in TERMS if k in keys],
            empty_terms=empty_terms,
            cells=ordered,
            quotes=[TermQuote(**q) for q in sorted(eligible, key=lambda q: (families.index(q["family"].upper()), q["min_days"], q["per_gpu"]))],
            excluded=excluded,
            references=[TermReference(**r) for r in references if r["segment"] == segment and r["family"].upper() in families],
            coverage={
                "observed": sum(c.status == "observed" for c in ordered),
                "estimated": sum(c.status == "estimated" for c in ordered),
                "none": sum(c.status == "none" for c in ordered),
                "total": len(ordered),
            },
        )
