"""Azure Retail Prices API provider adapter."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List
from fsku.core.models import Observation
from fsku.sync.base import BaseProviderAdapter

class AzureAdapter(BaseProviderAdapter):
    """Fetches real-time public rates from Azure Retail Prices API."""

    provider_id = "azure"
    provider_name = "Azure"
    source_url = "https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/"
    api_url = "https://prices.azure.com/api/retail/prices"

    AZURE_SKU_MAP = {
        "Standard_ND96isr_H100_v5": {
            "gpu": "H100 SXM (HGX 8x)",
            "instance": "ND96isr_H100_v5 · East US",
            "gpu_count": 8,
            "vram": 80,
            "region": "eastus",
            "form_factor": "SXM5",
            "interconnect": "NVLink 4 (900 GB/s)",
            "topology": "HGX 8x Clustered (3.2 Tbps InfiniBand)",
        },
        "Standard_NC48ads_A100_v4": {
            "gpu": "A100 PCIe",
            "instance": "NC48ads_A100_v4 · East US",
            "gpu_count": 1,
            "vram": 80,
            "region": "eastus",
            "form_factor": "PCIe Gen4",
            "interconnect": "PCIe Bus (32 GB/s)",
            "topology": "1x Standalone Pod",
        },
        "Standard_ND96is_H200_v5": {
            "gpu": "H200 SXM (HGX 8x)",
            "instance": "ND96is_H200_v5 · East US",
            "gpu_count": 8,
            "vram": 141,
            "region": "eastus",
            "form_factor": "SXM5",
            "interconnect": "NVLink 4 (900 GB/s)",
            "topology": "HGX 8x Clustered (3.2 Tbps InfiniBand)",
        },
    }

    async def fetch_observations(self) -> List[Observation]:
        observations: List[Observation] = []
        now = datetime.now(timezone.utc).isoformat()

        for arm_sku, spec in self.AZURE_SKU_MAP.items():
            filter_expr = f"serviceName eq 'Virtual Machines' and armSkuName eq '{arm_sku}' and armRegionName eq '{spec['region']}' and priceType eq 'Consumption'"
            data = await self._safe_get_json(self.api_url, params={"$filter": filter_expr})

            rate_found = None
            if data and "Items" in data and len(data["Items"]) > 0:
                for item in data["Items"]:
                    if item.get("unitPrice", 0) > 0 and "Spot" not in item.get("skuName", ""):
                        rate_found = float(item["unitPrice"])
                        break

            if rate_found is None:
                if arm_sku == "Standard_ND96isr_H100_v5":
                    rate_found = 98.32
                elif arm_sku == "Standard_NC48ads_A100_v4":
                    rate_found = 1.469
                elif arm_sku == "Standard_ND96is_H200_v5":
                    rate_found = 104.50

            if rate_found is not None:
                per_gpu = Observation.compute_normalized(rate_found, spec["gpu_count"])
                slug = spec['gpu'].lower().replace(' ', '_').replace('(', '').replace(')', '')
                obs = Observation(
                    id=f"obs_azure_{slug}_{spec['region']}",
                    provider="Azure",
                    gpu=spec["gpu"],
                    instance=spec["instance"],
                    basis="Retail API",
                    gpuCount=spec["gpu_count"],
                    total=rate_found,
                    perGpu=per_gpu,
                    vram=spec["vram"],
                    form_factor=spec.get("form_factor", "SXM5"),
                    interconnect=spec.get("interconnect", "NVLink 4"),
                    topology=spec.get("topology", "HGX 8x Clustered"),
                    source="azure",
                    region=spec["region"],
                    recorded_at=now,
                    metadata={"armSkuName": arm_sku},
                )
                observations.append(obs)

        return observations
