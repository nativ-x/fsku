"""Lambda Cloud GPU provider adapter."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List
from fsku.core.models import Observation
from fsku.sync.base import BaseProviderAdapter

class LambdaCloudAdapter(BaseProviderAdapter):
    """Fetches Lambda Cloud instance catalog pricing."""

    provider_id = "lambda"
    provider_name = "Lambda Labs"
    source_url = "https://lambdalabs.com/service/gpu-cloud"

    LAMBDA_CATALOG = [
        {"gpu": "H100 SXM (1x)", "instance": "1x H100 SXM5", "basis": "On-demand", "gpu_count": 1, "total": 2.49, "vram": 80, "form_factor": "SXM5", "interconnect": "NVLink / Sliced", "topology": "1x Standalone Pod"},
        {"gpu": "H100 SXM (HGX 8x)", "instance": "8x H100 SXM5", "basis": "On-demand", "gpu_count": 8, "total": 19.92, "vram": 80, "form_factor": "SXM5", "interconnect": "NVLink 4 (900 GB/s)", "topology": "HGX 8x Clustered (3.2 Tbps InfiniBand)"},
        {"gpu": "A100 SXM (1x)", "instance": "1x A100 SXM4 80GB", "basis": "On-demand", "gpu_count": 1, "total": 1.29, "vram": 80, "form_factor": "SXM4", "interconnect": "NVLink / Sliced", "topology": "1x Standalone Pod"},
        {"gpu": "A100 SXM (HGX 8x)", "instance": "8x A100 SXM4 80GB", "basis": "On-demand", "gpu_count": 8, "total": 10.32, "vram": 80, "form_factor": "SXM4", "interconnect": "NVLink 3 (600 GB/s)", "topology": "HGX 8x Clustered (1.6 Tbps HDR)"},
        {"gpu": "GH200 NVLink-C2C", "instance": "1x GH200 Grace Hopper", "basis": "On-demand", "gpu_count": 1, "total": 2.99, "vram": 96, "form_factor": "Superchip", "interconnect": "NVLink-C2C (900 GB/s)", "topology": "Coherent CPU+GPU Superchip"},
    ]

    async def fetch_observations(self) -> List[Observation]:
        observations: List[Observation] = []
        now = datetime.now(timezone.utc).isoformat()

        for item in self.LAMBDA_CATALOG:
            per_gpu = Observation.compute_normalized(item["total"], item["gpu_count"])
            slug = f"{item['gpu']}_{item['instance']}".lower().replace(" ", "_").replace("(", "").replace(")", "")
            obs = Observation(
                id=f"obs_lambda_{slug}",
                provider="Lambda Labs",
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
                source="lambda",
                region="US-West",
                recorded_at=now,
            )
            observations.append(obs)

        return observations
