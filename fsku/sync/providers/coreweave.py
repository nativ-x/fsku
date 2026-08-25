"""CoreWeave specialized compute provider adapter."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List
from fsku.core.models import Observation
from fsku.sync.base import BaseProviderAdapter

class CoreWeaveAdapter(BaseProviderAdapter):
    """Fetches CoreWeave HGX server-level on-demand and spot rates."""

    provider_id = "coreweave"
    provider_name = "CoreWeave"
    source_url = "https://www.coreweave.com/pricing"

    COREWEAVE_CATALOG = [
        {"gpu": "H100 SXM (HGX 8x)", "instance": "HGX H100", "basis": "On-demand", "gpu_count": 8, "total": 49.24, "vram": 80, "form_factor": "SXM5", "interconnect": "NVLink 4 (900 GB/s)", "topology": "HGX 8x Clustered (3.2 Tbps InfiniBand)"},
        {"gpu": "H100 SXM (HGX 8x)", "instance": "HGX H100", "basis": "Spot", "gpu_count": 8, "total": 19.71, "vram": 80, "form_factor": "SXM5", "interconnect": "NVLink 4 (900 GB/s)", "topology": "HGX 8x Clustered (3.2 Tbps InfiniBand)"},
        {"gpu": "H200 SXM (HGX 8x)", "instance": "HGX H200", "basis": "On-demand", "gpu_count": 8, "total": 50.44, "vram": 141, "form_factor": "SXM5", "interconnect": "NVLink 4 (900 GB/s)", "topology": "HGX 8x Clustered (3.2 Tbps InfiniBand)"},
        {"gpu": "H200 SXM (HGX 8x)", "instance": "HGX H200", "basis": "Spot", "gpu_count": 8, "total": 20.93, "vram": 141, "form_factor": "SXM5", "interconnect": "NVLink 4 (900 GB/s)", "topology": "HGX 8x Clustered (3.2 Tbps InfiniBand)"},
        {"gpu": "B200 SXM (HGX 8x)", "instance": "HGX B200", "basis": "On-demand", "gpu_count": 8, "total": 68.80, "vram": 180, "form_factor": "SXM6 / HGX", "interconnect": "NVLink 5 (1.8 TB/s)", "topology": "HGX 8x Clustered (3.2 Tbps Quantum-2)"},
        {"gpu": "B200 SXM (HGX 8x)", "instance": "HGX B200", "basis": "Spot", "gpu_count": 8, "total": 34.11, "vram": 180, "form_factor": "SXM6 / HGX", "interconnect": "NVLink 5 (1.8 TB/s)", "topology": "HGX 8x Clustered (3.2 Tbps Quantum-2)"},
        {"gpu": "B300 SXM (HGX 8x)", "instance": "HGX B300", "basis": "Spot", "gpu_count": 8, "total": 35.84, "vram": 270, "form_factor": "Blackwell Ultra", "interconnect": "NVLink 5 (1.8 TB/s)", "topology": "HGX 8x Clustered"},
        {"gpu": "A100 SXM (HGX 8x)", "instance": "A100", "basis": "On-demand", "gpu_count": 8, "total": 21.60, "vram": 80, "form_factor": "SXM4", "interconnect": "NVLink 3 (600 GB/s)", "topology": "HGX 8x Clustered (1.6 Tbps HDR)"},
        {"gpu": "A100 SXM (HGX 8x)", "instance": "A100", "basis": "Spot", "gpu_count": 8, "total": 9.65, "vram": 80, "form_factor": "SXM4", "interconnect": "NVLink 3 (600 GB/s)", "topology": "HGX 8x Clustered (1.6 Tbps HDR)"},
    ]

    async def fetch_observations(self) -> List[Observation]:
        observations: List[Observation] = []
        now = datetime.now(timezone.utc).isoformat()

        for item in self.COREWEAVE_CATALOG:
            per_gpu = Observation.compute_normalized(item["total"], item["gpu_count"])
            slug = f"{item['gpu']}_{item['basis']}".lower().replace(" ", "_").replace("(", "").replace(")", "")
            obs = Observation(
                id=f"obs_cw_{slug}",
                provider="CoreWeave",
                gpu=item["gpu"],
                instance=item["instance"],
                basis=item["basis"],
                gpuCount=item["gpu_count"],
                total=item["total"],
                perGpu=per_gpu,
                vram=item["vram"],
                form_factor=item.get("form_factor", "SXM5"),
                interconnect=item.get("interconnect", "NVLink 4"),
                topology=item.get("topology", "HGX 8x Clustered"),
                source="coreweave",
                region="US/EU",
                recorded_at=now,
            )
            observations.append(obs)

        return observations
