"""Quantitative implied forward curve and term structure engine for GPU compute."""

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple
from fsku.core.models import (
    ForwardCurveRequest,
    ForwardCurveResult,
    ForwardTenorPoint,
    TechDecayPair,
    TechDecaySummary,
)
from fsku.core.pricing import PricingEngine

class ForwardCurveEngine:
    """Computes model-implied term structure from observed cash price tape."""

    @classmethod
    def infer_tech_decay(
        cls,
        observations: List[Dict[str, Any]],
        cadence_months: int = 24,
        target_family: Optional[str] = None,
    ) -> TechDecaySummary:
        """Calculate cross-generation rental price compression strictly across matched providers."""
        pairs_to_check = [
            ("A100", "H100"),
            ("H100", "B200"),
            ("H100", "H200"),
            ("H200", "B200"),
            ("B200", "B300"),
            ("RTX 4090", "L40S"),
            ("L40S", "H100"),
            ("MI300X", "H100"),
        ]
        decay_pairs: List[TechDecayPair] = []
        providers = sorted({r["provider"] for r in observations if "provider" in r})

        for older, newer in pairs_to_check:
            for provider in providers:
                older_rows = [
                    r["perGpu"] for r in observations
                    if r.get("provider") == provider
                    and (older == PricingEngine.extract_gpu_family(r.get("gpu", "")) or older in (r.get("gpu", "") or ""))
                    and r.get("basis") != "Spot"
                    and r.get("perGpu", 0) > 0
                ]
                newer_rows = [
                    r["perGpu"] for r in observations
                    if r.get("provider") == provider
                    and (newer == PricingEngine.extract_gpu_family(r.get("gpu", "")) or newer in (r.get("gpu", "") or ""))
                    and r.get("basis") != "Spot"
                    and r.get("perGpu", 0) > 0
                ]

                if older_rows and newer_rows:
                    o_med = PricingEngine.median(older_rows)
                    n_med = PricingEngine.median(newer_rows)
                    if n_med > o_med > 0:
                        ratio = o_med / n_med

                        annual_decay = 1.0 - math.pow(ratio, 12.0 / cadence_months)
                        decay_pairs.append(
                            TechDecayPair(
                                provider=provider,
                                older=older,
                                newer=newer,
                                older_rate=round(o_med, 4),
                                newer_rate=round(n_med, 4),
                                annual_decay=round(annual_decay, 4),
                            )
                        )

        baseline_by_family = {
            "A100": 0.30,
            "H100": 0.19,
            "H200": 0.15,
            "B200": 0.10,
            "B300": 0.07,
            "GH200": 0.135,
            "MI300X": 0.17,
            "L40S": 0.22,
            "RTX 4090": 0.26,
        }

        if target_family:
            norm_fam = (PricingEngine.extract_gpu_family(target_family) or target_family).upper()
            clean_fam = target_family.upper().replace(" SXM", "").replace(" PCIE", "").replace(" NVL", "").strip()

            matched_older = [p.annual_decay for p in decay_pairs if p.older.upper() in (norm_fam, clean_fam)]
            matched_newer = [p.annual_decay for p in decay_pairs if p.newer.upper() in (norm_fam, clean_fam)]

            if matched_older:
                target_decay = PricingEngine.median(matched_older)
            elif clean_fam in baseline_by_family:
                target_decay = baseline_by_family[clean_fam]
            elif norm_fam in baseline_by_family:
                target_decay = baseline_by_family[norm_fam]
            elif matched_newer:

                target_decay = PricingEngine.median(matched_newer) * 0.65
            elif decay_pairs:
                target_decay = PricingEngine.median([p.annual_decay for p in decay_pairs])
            else:
                target_decay = 0.20
        else:
            if decay_pairs:
                target_decay = PricingEngine.median([p.annual_decay for p in decay_pairs])
            else:
                target_decay = 0.20

        clamped_decay = max(0.01, min(0.75, target_decay))
        return TechDecaySummary(decay=round(clamped_decay, 4), observations=decay_pairs)

    @classmethod
    def calculate_forward_curve(
        cls,
        observations: List[Dict[str, Any]],
        req: ForwardCurveRequest,
    ) -> Optional[ForwardCurveResult]:
        """Derive the implied forward curve for a specific GPU family or exact SKU."""
        family_upper = req.family.upper().strip()

        exact_matches = [
            r for r in observations
            if family_upper == (r.get("gpu", "") or "").upper().strip()
        ]

        if exact_matches:
            matching_rows = exact_matches
        else:
            clean_target = family_upper.replace("SXM", "").replace("PCIE", "").replace("NVL", "").strip()
            matching_rows = [
                r for r in observations
                if family_upper in (r.get("gpu", "") or "").upper()
                or family_upper == (PricingEngine.extract_gpu_family(r.get("gpu", "")) or "").upper()
                or (clean_target and clean_target in (r.get("gpu", "") or "").upper())
                or (clean_target and clean_target in (PricingEngine.extract_gpu_family(r.get("gpu", "")) or "").upper())
            ]

        if req.basis == "firm":
            filtered = [r for r in matching_rows if r.get("basis") != "Spot"]
        elif req.basis == "spot":
            filtered = [r for r in matching_rows if r.get("basis") == "Spot"]
        else:
            filtered = list(matching_rows)

        fallback = False
        if not filtered:
            filtered = list(matching_rows)
            fallback = True

        if not filtered:
            return None

        prices = [r["perGpu"] for r in filtered if r.get("perGpu", 0) > 0]
        if not prices:
            return None

        S0 = PricingEngine.median(prices)
        q25 = PricingEngine.quantile(prices, 0.25)
        q75 = PricingEngine.quantile(prices, 0.75)

        tech_summary = cls.infer_tech_decay(observations, req.cadence, target_family=req.family)
        d = tech_summary.decay
        carry_dec = req.carry_rate / 100.0

        annual_factor = max(0.01, (1.0 + carry_dec) * (1.0 - d))

        if q75 > q25 > 0:
            sigma = max(0.08, min(1.20, math.log(q75 / q25) / 1.349))
        else:
            sigma = 0.20

        points: List[ForwardTenorPoint] = []
        for m in range(0, req.horizon + 1):
            years = m / 12.0
            factor = math.pow(annual_factor, years)
            base_p = S0 * factor
            if m == 0:
                low_p = q25
                high_p = q75
            else:
                vol_spread = math.exp(sigma * math.sqrt(max(1.0 / 12.0, years)))
                low_p = max(0.01, base_p / vol_spread)
                high_p = base_p * vol_spread
            chg = (base_p / S0) - 1.0 if S0 > 0 else 0.0

            points.append(
                ForwardTenorPoint(
                    m=m,
                    base=round(base_p, 4),
                    low=round(low_p, 4),
                    high=round(high_p, 4),
                    chg_pct=round(chg, 4),
                )
            )

        return ForwardCurveResult(
            family=req.family,
            mode=req.basis,
            cadence=req.cadence,
            carry=req.carry_rate,
            horizon=req.horizon,
            fallback=fallback,
            S0=round(S0, 4),
            q25=round(q25, 4),
            q75=round(q75, 4),
            d=d,
            annual_factor=round(annual_factor, 4),
            tech=tech_summary,
            points=points,
        )

    @classmethod
    def compare_forward_curves(
        cls,
        observations: List[Dict[str, Any]],
        families: Optional[List[str]] = None,
        basis: str = "firm",
        cadence: int = 24,
        carry_rate: float = 5.0,
        horizon: int = 36,
    ) -> Dict[str, Any]:
        """Generate and align forward curves for multiple GPU families simultaneously."""
        target_families = families or ["H100", "H200", "B200", "B300", "A100"]
        curves: Dict[str, Dict[str, Any]] = {}
        tenors = [0, 3, 6, 12, 18, 24, 36, 48, 60]
        tenors = [t for t in tenors if t <= horizon]

        for fam in target_families:
            req = ForwardCurveRequest(
                family=fam,
                basis=basis,
                cadence=cadence,
                carry_rate=carry_rate,
                horizon=horizon,
            )
            res = cls.calculate_forward_curve(observations, req)
            if res:
                curves[fam] = res.model_dump()

        relative_ratios: Dict[str, Dict[int, float]] = {}
        if "H100" in curves:
            h100_pts = {p["m"]: p["base"] for p in curves["H100"]["points"]}
            for fam, crv in curves.items():
                if fam == "H100":
                    continue
                ratios: Dict[int, float] = {}
                for p in crv["points"]:
                    m = p["m"]
                    if m in h100_pts and h100_pts[m] > 0:
                        ratios[m] = round(p["base"] / h100_pts[m], 2)
                relative_ratios[f"{fam}/H100"] = ratios

        return {
            "curves": curves,
            "tenors": tenors,
            "relative_ratios": relative_ratios,
            "horizon": horizon,
            "cadence": cadence,
            "carry_rate": carry_rate,
            "basis": basis,
        }
