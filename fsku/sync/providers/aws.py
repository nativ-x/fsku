"""AWS EC2 and Capacity Blocks provider adapter."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List
from fsku.core.models import Observation
from fsku.sync.base import BaseProviderAdapter

class AWSAdapter(BaseProviderAdapter):
    """Fetches AWS EC2 and Capacity Blocks pricing observations."""

    provider_id = "aws"
    provider_name = "AWS"
    source_url = "https://aws.amazon.com/ec2/capacityblocks/pricing/"

    AWS_CATALOG = [
        {
            "gpu": "H100 SXM (1x)",
            "instance": "p5.4xlarge · N. Virginia",
            "basis": "Capacity block",
            "gpu_count": 1,
            "total": 5.191,
            "vram": 80,
            "region": "us-east-1",
            "form_factor": "SXM5",
            "interconnect": "NVLink / Sliced",
            "topology": "1x Standalone Pod",
        },
        {
            "gpu": "H100 SXM (HGX 8x)",
            "instance": "p5.48xlarge · N. Virginia",
            "basis": "On-demand",
            "gpu_count": 8,
            "total": 98.32,
            "vram": 80,
            "region": "us-east-1",
            "form_factor": "SXM5",
            "interconnect": "NVLink 4 (900 GB/s)",
            "topology": "HGX 8x Clustered (3.2 Tbps EFA)",
        },
    ]

    async def fetch_observations(self) -> List[Observation]:
        observations: List[Observation] = []
        now = datetime.now(timezone.utc).isoformat()

        for item in self.AWS_CATALOG:
            per_gpu = Observation.compute_normalized(item["total"], item["gpu_count"])
            slug = f"{item['gpu']}_{item['basis']}".lower().replace(" ", "_").replace("(", "").replace(")", "")
            obs = Observation(
                id=f"obs_aws_{slug}_{item['gpu_count']}g",
                provider="AWS",
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
                source="aws",
                region=item["region"],
                recorded_at=now,
            )
            observations.append(obs)

        return observations
