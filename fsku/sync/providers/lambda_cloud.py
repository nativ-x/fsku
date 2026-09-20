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
    source_url = "https://lambda.ai/pricing"
    # Hardcoded rate table; this adapter never touches the network. Rows are
    # tagged provenance="catalog" and dated catalog_as_of by the sync engine.
    # Lambda's API requires a key, so this stays catalog. Rates captured from
    # the public price page on catalog_as_of; the previous table (as of
    # 2026-08-25) carried H100 SXM at 2.49, which the page no longer shows.
    mode = "catalog"
    catalog_as_of = "2026-09-20"
    tier = "Specialized cloud"

    LAMBDA_CATALOG = [
        {"gpu": "H100 SXM (1x)",     "instance": "1x H100 SXM",       "basis": "On-demand", "gpu_count": 1, "total": 4.29,  "vram": 80,  "form_factor": "SXM5", "interconnect": "NVLink / Sliced",     "topology": "1x Standalone Pod"},
        {"gpu": "H100 SXM (HGX 8x)", "instance": "8x H100 SXM",       "basis": "On-demand", "gpu_count": 8, "total": 31.92, "vram": 80,  "form_factor": "SXM5", "interconnect": "NVLink 4 (900 GB/s)", "topology": "HGX 8x Clustered (3.2 Tbps InfiniBand)"},
        {"gpu": "H100 PCIe",         "instance": "1x H100 PCIe",      "basis": "On-demand", "gpu_count": 1, "total": 3.29,  "vram": 80,  "form_factor": "PCIe Gen5", "interconnect": "PCIe Bus (64 GB/s)", "topology": "Standard PCIe Server"},
        {"gpu": "B200 SXM (HGX 8x)", "instance": "8x B200 SXM6",      "basis": "On-demand", "gpu_count": 8, "total": 53.52, "vram": 180, "form_factor": "SXM6", "interconnect": "NVLink 5 (1.8 TB/s)", "topology": "HGX 8x Clustered (3.2 Tbps InfiniBand)"},
        {"gpu": "B200 SXM (1x)",     "instance": "1x B200 SXM6",      "basis": "On-demand", "gpu_count": 1, "total": 6.99,  "vram": 180, "form_factor": "SXM6", "interconnect": "NVLink 5 / Sliced",   "topology": "1x Standalone Pod"},
        {"gpu": "A100 SXM (HGX 8x)", "instance": "8x A100 SXM4 80GB", "basis": "On-demand", "gpu_count": 8, "total": 22.32, "vram": 80,  "form_factor": "SXM4", "interconnect": "NVLink 3 (600 GB/s)", "topology": "HGX 8x Clustered (1.6 Tbps HDR)"},
        {"gpu": "GH200 NVLink-C2C",  "instance": "1x GH200 Grace Hopper", "basis": "On-demand", "gpu_count": 1, "total": 2.29, "vram": 96, "form_factor": "Superchip", "interconnect": "NVLink-C2C (900 GB/s)", "topology": "Coherent CPU+GPU Superchip"},
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
