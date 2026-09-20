"""Together AI provider adapter -- catalog.

Rates captured from https://www.together.ai/pricing (GPU Clusters section) on
catalog_as_of. Together lists on-demand per-GPU-hour for HGX clusters and a
7-30 day reserved tier; longer commitments are "contact us". The H100
on-demand rate is a published promotion (was $5.49) valid to 2026-09-30,
noted on the row. No public JSON endpoint was found.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import List
from fsku.core.models import Observation
from fsku.sync.base import BaseProviderAdapter

class TogetherAdapter(BaseProviderAdapter):
    """Together AI HGX cluster pricing, on-demand and 7-30 day reserved."""

    provider_id = "together"
    provider_name = "Together AI"
    source_url = "https://www.together.ai/pricing"
    mode = "catalog"
    catalog_as_of = "2026-09-20"
    tier = "Specialized cloud"

    HGX = {"gpu_count": 8, "form_factor": "SXM5", "interconnect": "NVLink 4 (900 GB/s)", "topology": "HGX 8x Clustered (3.2 Tbps InfiniBand)"}
    B = {**HGX, "form_factor": "SXM6", "interconnect": "NVLink 5 (1.8 TB/s)"}
    TOGETHER_CATALOG = [
        {"gpu": "H100 SXM (HGX 8x)", "instance": "HGX H100 cluster (promo to 2026-09-30, list 5.49)", "basis": "On-demand", "per_gpu": 3.99, "vram": 80, **HGX},
        {"gpu": "H100 SXM (HGX 8x)", "instance": "HGX H100 cluster, 7-30 day",  "basis": "Reserved",  "per_gpu": 3.69, "vram": 80, **HGX},
        {"gpu": "H200 SXM (HGX 8x)", "instance": "HGX H200 cluster",            "basis": "On-demand", "per_gpu": 5.99, "vram": 141, **HGX},
        {"gpu": "H200 SXM (HGX 8x)", "instance": "HGX H200 cluster, 7-30 day",  "basis": "Reserved",  "per_gpu": 4.99, "vram": 141, **HGX},
        {"gpu": "B200 SXM (HGX 8x)", "instance": "HGX B200 cluster",            "basis": "On-demand", "per_gpu": 8.19, "vram": 180, **B},
        {"gpu": "B200 SXM (HGX 8x)", "instance": "HGX B200 cluster, 7-30 day",  "basis": "Reserved",  "per_gpu": 7.99, "vram": 180, **B},
    ]

    async def fetch_observations(self) -> List[Observation]:
        now = datetime.now(timezone.utc).isoformat()
        out: List[Observation] = []
        for it in self.TOGETHER_CATALOG:
            slug = f"{it['gpu']}_{it['basis']}".lower().replace(" ", "_").replace("(", "").replace(")", "")
            out.append(Observation(
                id=f"obs_together_{slug}", provider="Together AI", gpu=it["gpu"], instance=it["instance"], basis=it["basis"],
                gpuCount=it["gpu_count"], total=round(it["per_gpu"] * it["gpu_count"], 4), perGpu=it["per_gpu"], vram=it["vram"],
                form_factor=it["form_factor"], interconnect=it["interconnect"], topology=it["topology"],
                source="together", region="US", recorded_at=now,
            ))
        return out
