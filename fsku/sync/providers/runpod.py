"""RunPod provider adapter -- live, both tiers.

RunPod's public GraphQL endpoint answers unauthenticated POSTs with per-GPU
hourly rates for two capacity tiers:

    securePrice     Secure Cloud    -- RunPod-operated datacenter capacity
    communityPrice  Community Cloud -- peer-hosted marketplace capacity

Both are published as separate rows with their own `tier`. Until 2026-09 this
adapter read a hardcoded table of Community Cloud rates and labelled them
"On-demand" with no tier; the table survives below as the fallback used only
when the API gives nothing usable, and every such substitution is reported.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fsku.core.models import Observation
from fsku.sync.base import BaseProviderAdapter

class RunPodAdapter(BaseProviderAdapter):
    """Fetches RunPod Secure Cloud and Community Cloud per-GPU rates."""

    provider_id = "runpod"
    provider_name = "RunPod"
    source_url = "https://www.runpod.io/gpu-models"
    api_url = "https://api.runpod.io/graphql"
    mode = "live"
    # Fallback constants below are RunPod Community Cloud rates captured on
    # this date (they still matched communityPrice to the cent on 2026-09-19).
    catalog_as_of = "2026-08-25"
    # Rows carry their own tier (Secure or Community); fallback rows are Community.
    tier = None

    QUERY = "query { gpuTypes { id displayName memoryInGb securePrice communityPrice } }"

    # RunPod displayName -> our SKU. RunPod sells per-GPU slices of shared
    # nodes, so every SKU here is the 1x / standalone deliverable unit.
    SKU_MAP: Dict[str, Dict[str, Any]] = {
        "H100 SXM":  {"gpu": "H100 SXM (1x)", "vram": 80,  "form_factor": "SXM5",            "interconnect": "NVLink / Sliced",   "topology": "1x Standalone Pod",         "fallback": 2.69},
        "H100 PCIe": {"gpu": "H100 PCIe",     "vram": 80,  "form_factor": "PCIe Gen5",       "interconnect": "PCIe Bus (64 GB/s)", "topology": "Standard PCIe Server",      "fallback": 1.99},
        "H100 NVL":  {"gpu": "H100 NVL",      "vram": 94,  "form_factor": "NVL Dual",        "interconnect": "NVLink (600 GB/s)",  "topology": "Dual-GPU Inference Module", "fallback": 2.59},
        "H200 SXM":  {"gpu": "H200 SXM (1x)", "vram": 141, "form_factor": "SXM5",            "interconnect": "NVLink / Sliced",   "topology": "1x Standalone Pod",         "fallback": 3.59},
        "B200":      {"gpu": "B200 SXM (1x)", "vram": 180, "form_factor": "SXM6",            "interconnect": "NVLink 5 / Sliced", "topology": "1x Standalone Pod",         "fallback": 5.98},
        "A100 PCIe": {"gpu": "A100 PCIe",     "vram": 80,  "form_factor": "PCIe Gen4",       "interconnect": "PCIe Bus (32 GB/s)", "topology": "Standard PCIe Server",      "fallback": 1.19},
        "A100 SXM":  {"gpu": "A100 SXM (1x)", "vram": 80,  "form_factor": "SXM4",            "interconnect": "NVLink / Sliced",   "topology": "1x Standalone Pod",         "fallback": 1.39},
        "L40S":      {"gpu": "L40S PCIe",     "vram": 48,  "form_factor": "PCIe Gen4",       "interconnect": "PCIe Bus (32 GB/s)", "topology": "Enterprise Inference Server", "fallback": 0.79},
        "RTX 4090":  {"gpu": "RTX 4090 PCIe", "vram": 24,  "form_factor": "PCIe Gen4",       "interconnect": "PCIe Bus (32 GB/s)", "topology": "Workstation / Bare Metal",  "fallback": 0.34},
    }
    # SKUs RunPod's API does not list but the old catalog carried.
    CATALOG_ONLY: Dict[str, Dict[str, Any]] = {
        "B300": {"gpu": "B300 SXM (1x)", "vram": 288, "form_factor": "Blackwell Ultra", "interconnect": "NVLink 5 / Sliced", "topology": "1x Standalone Pod", "fallback": 6.94},
    }

    def _row(self, spec: Dict[str, Any], tier: str, rate: float, provenance: str, recorded_at: str, meta: Dict[str, Any]) -> Observation:
        slug = spec["gpu"].lower().replace(" ", "_").replace("(", "").replace(")", "")
        return Observation(
            id=f"obs_runpod_{slug}_{tier.lower()}",
            provider="RunPod",
            gpu=spec["gpu"],
            instance=f"{tier} Cloud",
            basis="On-demand",
            tier=tier,
            gpuCount=1,
            total=rate,
            perGpu=rate,
            vram=spec["vram"],
            form_factor=spec["form_factor"],
            interconnect=spec["interconnect"],
            topology=spec["topology"],
            source="runpod",
            region="Global",
            recorded_at=recorded_at,
            provenance=provenance,
            metadata=meta,
        )

    async def fetch_observations(self) -> List[Observation]:
        now = datetime.now(timezone.utc).isoformat()
        data = await self._safe_post_json(self.api_url, {"query": self.QUERY})
        types = ((data or {}).get("data") or {}).get("gpuTypes") if isinstance(data, dict) else None
        by_name: Dict[str, Dict[str, Any]] = {}
        if isinstance(types, list):
            for g in types:
                if isinstance(g, dict) and g.get("displayName"):
                    by_name[g["displayName"]] = g

        observations: List[Observation] = []
        for name, spec in self.SKU_MAP.items():
            g = by_name.get(name)
            got_any = False
            if g:
                for tier, key in (("Secure", "securePrice"), ("Community", "communityPrice")):
                    rate = g.get(key)
                    if isinstance(rate, (int, float)) and rate > 0:
                        got_any = True
                        observations.append(self._row(spec, tier, float(rate), "live", now,
                                                      {"runpodId": g.get("id"), "memoryInGb": g.get("memoryInGb")}))
            if not got_any:
                why = "not in API response" if by_name else "API request failed"
                self.note_fallback(f"{name}: {why}; substituted Community {spec['fallback']} (as of {self.catalog_as_of})")
                observations.append(self._row(spec, "Community", spec["fallback"], "fallback", self.catalog_as_of, {}))

        for name, spec in self.CATALOG_ONLY.items():
            self.note_fallback(f"{name}: RunPod API does not list it; substituted Community {spec['fallback']} (as of {self.catalog_as_of})")
            observations.append(self._row(spec, "Community", spec["fallback"], "fallback", self.catalog_as_of, {}))

        return observations
