"""Vast.ai provider adapter -- live marketplace asks.

Vast.ai is a peer-hosted GPU marketplace. Its public offer search answers
unauthenticated and returns live rentable asks with the machine's GPU name,
GPU count and total $/hr. One observation per SKU is published: the median
per-GPU ask across every rentable on-demand offer for that GPU, with the offer
count, verified count and p10/p90 in metadata so the depth behind the number
is visible.

Known limit: the unauthenticated endpoint returns a capped slice of the
marketplace (64 offers on 2026-09-20), so per-SKU depth can be single digits.
The count is on every row; a thin reading is not hidden.

There is no fallback table. If the API gives nothing, this adapter publishes
nothing and says so -- an outage must not print yesterday's number as today's.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import quote
from fsku.core.models import Observation
from fsku.core.pricing import PricingEngine
from fsku.sync.base import BaseProviderAdapter

class VastAdapter(BaseProviderAdapter):
    """Aggregates live Vast.ai on-demand asks into one per-SKU observation."""

    provider_id = "vast"
    provider_name = "Vast.ai"
    source_url = "https://vast.ai/pricing"
    api_url = "https://console.vast.ai/api/v0/bundles/"
    mode = "live"
    tier = "Community"

    QUERY = {"rentable": {"eq": True}, "type": "on-demand", "limit": 5000}

    # Vast gpu_name -> our SKU
    SKU_MAP: Dict[str, Dict[str, Any]] = {
        "H100 SXM":  {"gpu": "H100 SXM (1x)", "vram": 80,  "form_factor": "SXM5",      "interconnect": "NVLink / Sliced",   "topology": "1x Standalone Pod"},
        "H100 PCIE": {"gpu": "H100 PCIe",     "vram": 80,  "form_factor": "PCIe Gen5", "interconnect": "PCIe Bus (64 GB/s)", "topology": "Standard PCIe Server"},
        "H100 NVL":  {"gpu": "H100 NVL",      "vram": 94,  "form_factor": "NVL Dual",  "interconnect": "NVLink (600 GB/s)",  "topology": "Dual-GPU Inference Module"},
        "H200":      {"gpu": "H200 SXM (1x)", "vram": 141, "form_factor": "SXM5",      "interconnect": "NVLink / Sliced",   "topology": "1x Standalone Pod"},
        "B200":      {"gpu": "B200 SXM (1x)", "vram": 180, "form_factor": "SXM6",      "interconnect": "NVLink 5 / Sliced", "topology": "1x Standalone Pod"},
        "A100 SXM4": {"gpu": "A100 SXM (1x)", "vram": 80,  "form_factor": "SXM4",      "interconnect": "NVLink / Sliced",   "topology": "1x Standalone Pod"},
        "A100 PCIE": {"gpu": "A100 PCIe",     "vram": 80,  "form_factor": "PCIe Gen4", "interconnect": "PCIe Bus (32 GB/s)", "topology": "Standard PCIe Server"},
        "L40S":      {"gpu": "L40S PCIe",     "vram": 48,  "form_factor": "PCIe Gen4", "interconnect": "PCIe Bus (32 GB/s)", "topology": "Enterprise Inference Server"},
        "RTX 4090":  {"gpu": "RTX 4090 PCIe", "vram": 24,  "form_factor": "PCIe Gen4", "interconnect": "PCIe Bus (32 GB/s)", "topology": "Workstation / Bare Metal"},
    }

    @classmethod
    def aggregate(cls, offers: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Per Vast gpu_name: n, n_verified, median/p10/p90/min per-GPU $/hr."""
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for o in offers:
            n = o.get("num_gpus") or 0
            total = o.get("dph_total")
            if n > 0 and isinstance(total, (int, float)) and total > 0 and o.get("gpu_name") in cls.SKU_MAP:
                buckets.setdefault(o["gpu_name"], []).append({"per_gpu": total / n, "verified": o.get("verification") == "verified", "num_gpus": n})
        out = {}
        for name, rows in buckets.items():
            p = sorted(r["per_gpu"] for r in rows)
            out[name] = {
                "n": len(p),
                "n_verified": sum(1 for r in rows if r["verified"]),
                "median": round(PricingEngine.median(p), 4),
                "p10": round(PricingEngine.quantile(p, 0.10), 4),
                "p90": round(PricingEngine.quantile(p, 0.90), 4),
                "min": round(p[0], 4),
                "gpus_per_offer": sorted({r["num_gpus"] for r in rows}),
            }
        return out

    async def fetch_observations(self) -> List[Observation]:
        now = datetime.now(timezone.utc).isoformat()
        url = f"{self.api_url}?q={quote(json.dumps(self.QUERY, separators=(',', ':')))}"
        data = await self._safe_get_json(url)
        offers = data.get("offers") if isinstance(data, dict) else None
        if not isinstance(offers, list):
            self.notes.append("no offers in response; publishing nothing rather than a stale constant")
            return []
        agg = self.aggregate(offers)
        observations: List[Observation] = []
        for name, stats in agg.items():
            spec = self.SKU_MAP[name]
            slug = spec["gpu"].lower().replace(" ", "_").replace("(", "").replace(")", "")
            observations.append(Observation(
                id=f"obs_vast_{slug}",
                provider="Vast.ai",
                gpu=spec["gpu"],
                instance="marketplace median ask",  # stable: the offer count lives in metadata, not the row key
                basis="On-demand",
                tier="Community",
                gpuCount=1,
                total=stats["median"],
                perGpu=stats["median"],
                vram=spec["vram"],
                form_factor=spec["form_factor"],
                interconnect=spec["interconnect"],
                topology=spec["topology"],
                source="vast",
                region="Global",
                recorded_at=now,
                provenance="live",
                metadata={"vast_gpu_name": name, **stats},
            ))
        return observations
