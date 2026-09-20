"""Nebius AI Cloud provider adapter -- catalog.

Rates captured from https://nebius.com/prices on catalog_as_of. Nebius
publishes per-GPU-hour prices for HGX nodes in two bases: on-demand and
preemptible (published here as Spot). Reservation discounts up to 35% are
"contact us" and are not listed. No public JSON endpoint was found.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List
from fsku.core.models import Observation
from fsku.sync.base import BaseProviderAdapter

class NebiusAdapter(BaseProviderAdapter):
    """Nebius HGX node pricing, on-demand and preemptible."""

    provider_id = "nebius"
    provider_name = "Nebius"
    source_url = "https://nebius.com/prices"
    mode = "catalog"
    catalog_as_of = "2026-09-20"
    tier = "Specialized cloud"

    HGX = {"gpu_count": 8, "form_factor": "SXM5", "interconnect": "NVLink 4 (900 GB/s)", "topology": "HGX 8x Clustered (3.2 Tbps InfiniBand)"}
    NEBIUS_CATALOG = [
        {"gpu": "H100 SXM (HGX 8x)", "instance": "HGX H100", "basis": "On-demand", "per_gpu": 3.85, "vram": 80, **HGX},
        {"gpu": "H100 SXM (HGX 8x)", "instance": "HGX H100", "basis": "Spot",      "per_gpu": 2.15, "vram": 80, **HGX},
        {"gpu": "H200 SXM (HGX 8x)", "instance": "HGX H200", "basis": "On-demand", "per_gpu": 4.50, "vram": 141, **HGX},
        {"gpu": "H200 SXM (HGX 8x)", "instance": "HGX H200", "basis": "Spot",      "per_gpu": 2.45, "vram": 141, **HGX},
        {"gpu": "B200 SXM (HGX 8x)", "instance": "HGX B200", "basis": "On-demand", "per_gpu": 7.15, "vram": 180, **{**HGX, "form_factor": "SXM6", "interconnect": "NVLink 5 (1.8 TB/s)"}},
        {"gpu": "B200 SXM (HGX 8x)", "instance": "HGX B200", "basis": "Spot",      "per_gpu": 3.95, "vram": 180, **{**HGX, "form_factor": "SXM6", "interconnect": "NVLink 5 (1.8 TB/s)"}},
        {"gpu": "B300 SXM (HGX 8x)", "instance": "HGX B300", "basis": "On-demand", "per_gpu": 7.85, "vram": 288, **{**HGX, "form_factor": "Blackwell Ultra", "interconnect": "NVLink 5 (1.8 TB/s)"}},
        {"gpu": "B300 SXM (HGX 8x)", "instance": "HGX B300", "basis": "Spot",      "per_gpu": 4.30, "vram": 288, **{**HGX, "form_factor": "Blackwell Ultra", "interconnect": "NVLink 5 (1.8 TB/s)"}},
        {"gpu": "L40S PCIe", "instance": "L40S (AMD CPU), from", "basis": "On-demand", "per_gpu": 1.55, "vram": 48, "gpu_count": 1, "form_factor": "PCIe Gen4", "interconnect": "PCIe Bus (32 GB/s)", "topology": "Enterprise Inference Server"},
    ]

    async def fetch_observations(self) -> List[Observation]:
        now = datetime.now(timezone.utc).isoformat()
        out: List[Observation] = []
        for it in self.NEBIUS_CATALOG:
            total = round(it["per_gpu"] * it["gpu_count"], 4)
            slug = f"{it['gpu']}_{it['basis']}".lower().replace(" ", "_").replace("(", "").replace(")", "")
            out.append(Observation(
                id=f"obs_nebius_{slug}", provider="Nebius", gpu=it["gpu"], instance=it["instance"], basis=it["basis"],
                gpuCount=it["gpu_count"], total=total, perGpu=it["per_gpu"], vram=it["vram"],
                form_factor=it["form_factor"], interconnect=it["interconnect"], topology=it["topology"],
                source="nebius", region="EU / US", recorded_at=now,
            ))
        return out
