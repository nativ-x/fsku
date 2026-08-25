"""Pricing normalization and quantitative market dispersion engine."""

from __future__ import annotations
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from fsku.core.models import (
    MethodologySensitivity,
    ProviderPriceRow,
    SkuIndexSummary,
    SourceAblationResult,
)

class PricingEngine:
    """Quantitative analytics, benchmark indexing, and normalization for GPU compute tape."""

    @staticmethod
    def normalize_rate(total_price: float, gpu_count: int) -> float:
        """Divide total hourly price by GPU count to get standardized $/GPU-hr."""
        if gpu_count <= 0:
            raise ValueError("gpu_count must be at least 1")
        return round(total_price / gpu_count, 6)

    @staticmethod
    def median(values: List[float]) -> float:
        """Compute the statistical median."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 1:
            return float(sorted_vals[mid])
        return float((sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0)

    @staticmethod
    def quantile(values: List[float], q: float) -> float:
        """Compute the quantile value (0.0 to 1.0) using linear interpolation."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        if len(sorted_vals) == 1:
            return float(sorted_vals[0])
        pos = (len(sorted_vals) - 1) * q
        base = int(math.floor(pos))
        rest = pos - base
        if base + 1 < len(sorted_vals):
            return float(sorted_vals[base] + rest * (sorted_vals[base + 1] - sorted_vals[base]))
        return float(sorted_vals[base])

    @classmethod
    def trimmed_mean(cls, values: List[float], trim_fraction: float = 0.10) -> float:
        """Compute the trimmed mean by discarding a fraction of high and low outliers."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n <= 2:
            return cls.median(sorted_vals)
        k = int(math.floor(n * trim_fraction))
        trimmed = sorted_vals[k : n - k] if k > 0 and (n - 2 * k) > 0 else sorted_vals
        return float(sum(trimmed) / len(trimmed))

    @classmethod
    def calculate_index(
        cls,
        observations: List[Dict[str, Any]],
        method: str = "median",
        trim_fraction: float = 0.10,
    ) -> float:
        """Compute benchmark index price for a set of observations using selected methodology."""
        if not observations:
            return 0.0

        prices = [r["perGpu"] for r in observations if r.get("perGpu", 0) > 0]
        if not prices:
            return 0.0

        m = method.lower().strip()
        if m in ("median", "robust_median"):
            return round(cls.median(prices), 4)

        if m in ("trimmed_mean", "trimmed_10", "trimmed"):
            return round(cls.trimmed_mean(prices, trim_fraction), 4)

        if m in ("trimmed_20", "trimmed_mean_20"):
            return round(cls.trimmed_mean(prices, 0.20), 4)

        if m in ("simple_mean", "mean", "arithmetic"):
            return round(float(sum(prices) / len(prices)), 4)

        if m in ("provider_balanced", "provider_weighted", "balanced"):

            by_provider: Dict[str, List[float]] = {}
            for r in observations:
                p = r.get("provider", "Unknown")
                by_provider.setdefault(p, []).append(r["perGpu"])
            provider_medians = [cls.median(vals) for vals in by_provider.values() if vals]
            if provider_medians:
                return round(float(sum(provider_medians) / len(provider_medians)), 4)
            return round(cls.median(prices), 4)

        if m in ("gpu_weighted", "volume_weighted", "count_weighted"):
            total_cost = sum(r.get("total", r["perGpu"] * r.get("gpuCount", 1)) for r in observations)
            total_gpus = sum(r.get("gpuCount", 1) for r in observations)
            if total_gpus > 0:
                return round(float(total_cost / total_gpus), 4)
            return round(cls.median(prices), 4)

        return round(cls.median(prices), 4)

    @staticmethod
    def extract_gpu_family(gpu_name: str) -> Optional[str]:
        """Classify GPU name into primary architecture family."""
        if not gpu_name:
            return None
        upper = gpu_name.upper()
        if "B300" in upper:
            return "B300"
        if "B200" in upper:
            return "B200"
        if "H200" in upper:
            return "H200"
        if "H100" in upper:
            return "H100"
        if "A100" in upper:
            return "A100"
        if "MI300" in upper:
            return "MI300X"
        if "GH200" in upper:
            return "GH200"
        if "L40S" in upper:
            return "L40S"
        if "4090" in upper:
            return "RTX 4090"
        return None

    @classmethod
    def is_h100(cls, gpu_name: str) -> bool:
        """Check if an observation belongs to the H100 family."""
        return bool(re.search(r"\bH100\b", gpu_name or "", re.IGNORECASE))

    @classmethod
    def calculate_sku_index_summaries(
        cls,
        observations: List[Dict[str, Any]],
        method: str = "median",
    ) -> List[SkuIndexSummary]:
        """Compute comprehensive benchmark indices for all tracked GPU SKUs."""
        by_sku: Dict[str, List[Dict[str, Any]]] = {}
        for r in observations:
            sku = r.get("gpu", "").strip()
            if sku:
                by_sku.setdefault(sku, []).append(r)

        summaries: List[SkuIndexSummary] = []
        for sku, rows in by_sku.items():
            prices = [r["perGpu"] for r in rows if r.get("perGpu", 0) > 0]
            if not prices:
                continue

            index_p = cls.calculate_index(rows, method=method)
            min_p = min(prices)
            max_p = max(prices)
            q25 = cls.quantile(prices, 0.25)
            q75 = cls.quantile(prices, 0.75)
            disp_ratio = (max_p / min_p) if min_p > 0 else 1.0
            providers = {r.get("provider") for r in rows if r.get("provider")}
            vram = max(r.get("vram", 80) for r in rows)
            family = cls.extract_gpu_family(sku) or "Other"

            form_factors = {r.get("form_factor") for r in rows if r.get("form_factor")}
            interconnects = {r.get("interconnect") for r in rows if r.get("interconnect")}
            topologies = {r.get("topology") for r in rows if r.get("topology")}

            form_factor_val = next(iter(form_factors)) if form_factors else ("SXM5" if "H100" in sku or "H200" in sku else ("SXM6" if "B200" in sku else "PCIe"))
            interconnect_val = next(iter(interconnects)) if interconnects else ("NVLink 4" if "SXM" in sku else "PCIe")
            topology_val = next(iter(topologies)) if topologies else ("HGX 8x Clustered" if "8x" in sku or "HGX" in sku else ("1x Standalone Pod" if "1x" in sku else "Standard Server"))

            count = len(rows)

            if count >= 4 and len(providers) >= 2:
                conf = "HIGH"
                status = "ACTIVE"
            elif count >= 2:
                conf = "MODERATE"
                status = "ACTIVE"
            else:
                conf = "LOW (SPARSE)"
                status = "INDICATIVE"

            if "B300" in sku or "B200" in sku:
                if status == "INDICATIVE":
                    status = "EMERGING"

            summaries.append(
                SkuIndexSummary(
                    sku=sku,
                    family=family,
                    form_factor=form_factor_val,
                    interconnect=interconnect_val,
                    topology=topology_val,
                    vram=vram,
                    index_price=index_p,
                    methodology=method.capitalize(),
                    basis_spread=round(max_p - min_p, 4),
                    min_price=round(min_p, 4),
                    max_price=round(max_p, 4),
                    iqr_low=round(q25, 4),
                    iqr_high=round(q75, 4),
                    dispersion_ratio=round(disp_ratio, 2),
                    observation_count=count,
                    provider_count=len(providers),
                    confidence=conf,
                    market_status=status,
                    change_24h=0.0,
                )
            )

        order = {
            "H100 SXM (HGX 8x)": 1,
            "H100 SXM (1x)": 2,
            "H100 SXM": 3,
            "H100 PCIe": 4,
            "H100 NVL": 5,
            "H200 SXM (HGX 8x)": 6,
            "H200 SXM (1x)": 7,
            "H200": 8,
            "B200 SXM (HGX 8x)": 9,
            "B200 SXM (1x)": 10,
            "B200": 11,
            "B300 SXM (HGX 8x)": 12,
            "B300 SXM (1x)": 13,
            "B300": 14,
            "A100 SXM (HGX 8x)": 15,
            "A100 SXM (1x)": 16,
            "A100 SXM": 17,
            "A100 PCIe": 18,
            "MI300X (OAM 8x)": 19,
            "MI300X": 20,
            "GH200 NVLink-C2C": 21,
            "GH200": 22,
            "L40S PCIe": 23,
            "L40S": 24,
            "RTX 4090 PCIe": 25,
            "RTX 4090": 26,
        }
        summaries.sort(key=lambda s: (order.get(s.sku, 99), -s.vram))
        return summaries

    @classmethod
    def calculate_sensitivity(cls, observations: List[Dict[str, Any]]) -> List[MethodologySensitivity]:
        """Examine how different weighting and aggregation methods affect the spot index price."""
        by_sku: Dict[str, List[Dict[str, Any]]] = {}
        for r in observations:
            sku = r.get("gpu", "").strip()
            if sku:
                by_sku.setdefault(sku, []).append(r)

        results: List[MethodologySensitivity] = []
        for sku, rows in by_sku.items():
            if not rows:
                continue
            med = cls.calculate_index(rows, "median")
            t10 = cls.calculate_index(rows, "trimmed_10")
            t20 = cls.calculate_index(rows, "trimmed_20")
            bal = cls.calculate_index(rows, "provider_balanced")
            mean = cls.calculate_index(rows, "simple_mean")
            gw = cls.calculate_index(rows, "gpu_weighted")

            all_vals = [med, t10, t20, bal, mean, gw]
            max_v = max(all_vals)
            min_v = min(all_vals)
            divergence = ((max_v - min_v) / med * 100) if med > 0 else 0.0

            results.append(
                MethodologySensitivity(
                    sku=sku,
                    baseline_median=med,
                    trimmed_mean_10=t10,
                    trimmed_mean_20=t20,
                    provider_balanced=bal,
                    simple_mean=mean,
                    gpu_weighted_mean=gw,
                    max_divergence_pct=round(divergence, 2),
                )
            )

        results.sort(key=lambda x: x.max_divergence_pct, reverse=True)
        return results

    @classmethod
    def calculate_ablation(
        cls,
        observations: List[Dict[str, Any]],
        target_sku: Optional[str] = None,
    ) -> List[SourceAblationResult]:
        """Examine index price resilience by dropping each provider one-by-one."""
        all_providers = sorted({r.get("provider") for r in observations if r.get("provider")})
        all_skus = sorted({r.get("gpu") for r in observations if r.get("gpu")})
        if target_sku:
            all_skus = [s for s in all_skus if target_sku.lower() in s.lower()]

        results: List[SourceAblationResult] = []
        for provider in all_providers:
            for sku in all_skus:
                sku_rows = [r for r in observations if r.get("gpu") == sku]
                if len(sku_rows) <= 1:
                    continue

                has_provider = any(r.get("provider") == provider for r in sku_rows)
                if not has_provider:
                    continue

                orig_price = cls.calculate_index(sku_rows, "median")
                ablated_rows = [r for r in sku_rows if r.get("provider") != provider]
                if not ablated_rows:
                    continue
                ablated_price = cls.calculate_index(ablated_rows, "median")

                delta_abs = round(ablated_price - orig_price, 4)
                delta_pct = round((delta_abs / orig_price) * 100, 2) if orig_price > 0 else 0.0

                abs_pct = abs(delta_pct)
                if abs_pct < 1.0:
                    level = "NEGLIGIBLE"
                elif abs_pct < 8.0:
                    level = "LOW"
                elif abs_pct < 20.0:
                    level = "MODERATE"
                else:
                    level = "HIGH"

                results.append(
                    SourceAblationResult(
                        provider_removed=provider,
                        sku=sku,
                        original_price=orig_price,
                        ablated_price=ablated_price,
                        delta_abs=delta_abs,
                        delta_pct=delta_pct,
                        observations_remaining=len(ablated_rows),
                        impact_level=level,
                    )
                )

        results.sort(key=lambda x: abs(x.delta_pct), reverse=True)
        return results

    @classmethod
    def calculate_provider_matrix(
        cls,
        observations: List[Dict[str, Any]],
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ProviderPriceRow]:
        """Cross-provider pricing comparison with delta vs benchmark index."""
        src_map = {s["id"]: s.get("url", "#") for s in (sources or []) if "id" in s}
        sku_indices: Dict[str, float] = {}
        for r in observations:
            sku = r.get("gpu", "")
            if sku not in sku_indices:
                matching = [x for x in observations if x.get("gpu") == sku]
                sku_indices[sku] = cls.calculate_index(matching, "median")

        rows: List[ProviderPriceRow] = []
        for r in observations:
            sku = r.get("gpu", "")
            idx = sku_indices.get(sku, r.get("perGpu", 0.0))
            per_gpu = r.get("perGpu", 0.0)
            delta_pct = ((per_gpu - idx) / idx * 100) if idx > 0 else 0.0

            rows.append(
                ProviderPriceRow(
                    provider=r.get("provider", "Unknown"),
                    sku=sku,
                    instance=r.get("instance", "Standard"),
                    basis=r.get("basis", "On-demand"),
                    total_rate=r.get("total", 0.0),
                    gpu_count=r.get("gpuCount", 1),
                    per_gpu_rate=per_gpu,
                    index_price=idx,
                    delta_vs_index_pct=round(delta_pct, 2),
                    vram=r.get("vram", 80),
                    region=r.get("region", "Global"),
                    source_url=src_map.get(r.get("source", ""), "#"),
                )
            )

        rows.sort(key=lambda x: (x.sku, x.per_gpu_rate))
        return rows

    @classmethod
    def calculate_kpis(cls, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute macro-level market KPIs across the current tape."""
        if not observations:
            return {
                "observation_count": 0,
                "source_count": 0,
                "gpu_families_count": 0,
                "median_observed_rate": 0.0,
                "h100_dispersion": 1.0,
                "lowest_h100": {},
                "highest_h100": {},
                "median_h100": 0.0,
            }

        all_prices = [r.get("perGpu", 0.0) for r in observations if r.get("perGpu") is not None]
        sources = {r.get("source") for r in observations if r.get("source")}
        gpus = {r.get("gpu") for r in observations if r.get("gpu")}

        h100_rows = [r for r in observations if cls.is_h100(r.get("gpu", ""))]
        h100_prices = [r.get("perGpu", 0.0) for r in h100_rows if r.get("perGpu") is not None]

        h_min = min(h100_prices) if h100_prices else 0.0
        h_max = max(h100_prices) if h100_prices else 0.0
        h_med = cls.median(h100_prices)
        h_spread = (h_max / h_min) if h_min > 0 else 1.0

        lowest_h100 = min(h100_rows, key=lambda x: x.get("perGpu", float("inf"))) if h100_rows else {}
        highest_h100 = max(h100_rows, key=lambda x: x.get("perGpu", float("-inf"))) if h100_rows else {}

        return {
            "observation_count": len(observations),
            "source_count": len(sources),
            "gpu_families_count": len(gpus),
            "median_observed_rate": round(cls.median(all_prices), 3),
            "h100_dispersion": round(h_spread, 2),
            "h100_count": len(h100_rows),
            "h100_min": round(h_min, 3),
            "h100_max": round(h_max, 3),
            "median_h100": round(h_med, 3),
            "lowest_h100": {
                "provider": lowest_h100.get("provider", ""),
                "rate": lowest_h100.get("perGpu", 0.0),
                "instance": lowest_h100.get("instance", ""),
            } if lowest_h100 else {},
            "highest_h100": {
                "provider": highest_h100.get("provider", ""),
                "rate": highest_h100.get("perGpu", 0.0),
                "instance": highest_h100.get("instance", ""),
            } if highest_h100 else {},
        }

    @classmethod
    def calculate_memory_economics(
        cls,
        observations: List[Dict[str, Any]],
        specs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute GB of VRAM per rental dollar across specs."""
        fam_map = {
            "H100 SXM": "H100",
            "H200 SXM": "H200",
            "B200 SXM": "B200",
            "B300 SXM": "B300",
            "MI300X": "MI300",
        }
        candidates = []
        for spec in specs:
            name = spec.get("name", "")
            fam = fam_map.get(name)
            if not fam:
                continue
            matching = [
                r for r in observations
                if fam in (r.get("gpu") or "").upper() and r.get("perGpu", 0) > 0
            ]
            if matching:
                low_price = min(r["perGpu"] for r in matching)
                vram = spec.get("vram", 0)
                gb_per_dollar = vram / low_price if low_price > 0 else 0
                candidates.append({
                    "name": name,
                    "family": fam,
                    "vram": vram,
                    "lowest_rate": low_price,
                    "gb_per_dollar": round(gb_per_dollar, 2),
                })

        candidates.sort(key=lambda x: x["gb_per_dollar"], reverse=True)
        leader = candidates[0] if candidates else None
        return {
            "leader": leader,
            "comparisons": candidates,
        }
