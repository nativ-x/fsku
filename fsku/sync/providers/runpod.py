"""RunPod GPU catalog provider adapter."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List
from fsku.core.models import Observation
from fsku.sync.base import BaseProviderAdapter

class RunPodAdapter(BaseProviderAdapter):
    """Fetches RunPod on-demand GPU instance catalog pricing."""

    provider_id = "runpod"
    provider_name = "RunPod"
    source_url = "https://www.runpod.io/gpu-models"
    api_url = "https://api.runpod.io/graphql"

    RUNPOD_CATALOG = [
        {"gpu": "H100 SXM (1x)", "vram": 80, "rate": 2.69, "form_factor": "SXM5", "interconnect": "NVLink / Sliced", "topology": "1x Standalone Pod"},
        {"gpu": "H100 PCIe", "vram": 80, "rate": 1.99, "form_factor": "PCIe Gen5", "interconnect": "PCIe Bus (64 GB/s)", "topology": "Standard PCIe Server"},
        {"gpu": "H100 NVL", "vram": 94, "rate": 2.59, "form_factor": "NVL Dual", "interconnect": "NVLink (600 GB/s)", "topology": "Dual-GPU Inference Module"},
        {"gpu": "H200 SXM (1x)", "vram": 141, "rate": 3.59, "form_factor": "SXM5", "interconnect": "NVLink / Sliced", "topology": "1x Standalone Pod"},
        {"gpu": "B200 SXM (1x)", "vram": 180, "rate": 5.98, "form_factor": "SXM6", "interconnect": "NVLink 5 / Sliced", "topology": "1x Standalone Pod"},
        {"gpu": "B300 SXM (1x)", "vram": 288, "rate": 6.94, "form_factor": "Blackwell Ultra", "interconnect": "NVLink 5 / Sliced", "topology": "1x Standalone Pod"},
        {"gpu": "A100 PCIe", "vram": 80, "rate": 1.19, "form_factor": "PCIe Gen4", "interconnect": "PCIe Bus (32 GB/s)", "topology": "Standard PCIe Server"},
        {"gpu": "A100 SXM (1x)", "vram": 80, "rate": 1.39, "form_factor": "SXM4", "interconnect": "NVLink / Sliced", "topology": "1x Standalone Pod"},
        {"gpu": "L40S PCIe", "vram": 48, "rate": 0.79, "form_factor": "PCIe Gen4", "interconnect": "PCIe Bus (32 GB/s)", "topology": "Enterprise Inference Server"},
        {"gpu": "RTX 4090 PCIe", "vram": 24, "rate": 0.34, "form_factor": "PCIe Gen4", "interconnect": "PCIe Bus (32 GB/s)", "topology": "Workstation / Bare Metal"},
    ]

    async def fetch_observations(self) -> List[Observation]:
        observations: List[Observation] = []
        now = datetime.now(timezone.utc).isoformat()

        for item in self.RUNPOD_CATALOG:
            rate = item["rate"]
            slug = item["gpu"].lower().replace(" ", "_").replace("(", "").replace(")", "")
            obs = Observation(
                id=f"obs_runpod_{slug}",
                provider="RunPod",
                gpu=item["gpu"],
                instance="GPU model",
                basis="On-demand",
                gpuCount=1,
                total=rate,
                perGpu=rate,
                vram=item["vram"],
                form_factor=item.get("form_factor", "PCIe"),
                interconnect=item.get("interconnect", "PCIe"),
                topology=item.get("topology", "1x Standalone Pod"),
                source="runpod",
                region="Global",
                recorded_at=now,
            )
            observations.append(obs)

        return observations
