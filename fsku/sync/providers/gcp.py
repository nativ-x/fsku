"""Google Cloud accelerator-optimized VM pricing provider adapter."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List
from fsku.core.models import Observation
from fsku.sync.base import BaseProviderAdapter

class GCPAdapter(BaseProviderAdapter):
    """Fetches Google Cloud A3/A2 accelerator VM pricing."""

    provider_id = "gcp"
    provider_name = "Google Cloud"
    source_url = "https://cloud.google.com/products/compute/pricing/accelerator-optimized"

    GCP_CATALOG = [
        {
            "gpu": "H100 SXM (HGX 8x)",
            "instance": "a3-highgpu-8g",
            "basis": "On-demand",
            "gpu_count": 8,
            "total": 88.4900,
            "vram": 80,
            "region": "us-central1",
            "form_factor": "SXM5",
            "interconnect": "NVLink 4 (900 GB/s)",
            "topology": "HGX 8x Clustered (GPUDirect TCPX)",
        },
        {
            "gpu": "H200 SXM (HGX 8x)",
            "instance": "a3-ultragpu-8g",
            "basis": "On-demand",
            "gpu_count": 8,
            "total": 84.8069,
            "vram": 141,
            "region": "us-central1",
            "form_factor": "SXM5",
            "interconnect": "NVLink 4 (900 GB/s)",
            "topology": "HGX 8x Clustered (3.2 Tbps RoCE)",
        },
        {
            "gpu": "A100 SXM (1x)",
            "instance": "a2-highgpu-1g",
            "basis": "On-demand",
            "gpu_count": 1,
            "total": 3.6738,
            "vram": 80,
            "region": "us-central1",
            "form_factor": "SXM4",
            "interconnect": "NVLink / Sliced",
            "topology": "1x Standalone Pod",
        },
    ]

    async def fetch_observations(self) -> List[Observation]:
        observations: List[Observation] = []
        now = datetime.now(timezone.utc).isoformat()

        for item in self.GCP_CATALOG:
            per_gpu = Observation.compute_normalized(item["total"], item["gpu_count"])
            slug = item["instance"].lower().replace("-", "_")
            obs = Observation(
                id=f"obs_gcp_{slug}",
                provider="Google Cloud",
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
                source="gcp",
                region=item["region"],
                recorded_at=now,
            )
            observations.append(obs)

        return observations
