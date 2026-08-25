"""Base provider adapter interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
from fsku.core.models import Observation

class BaseProviderAdapter(ABC):
    """Abstract base class for all compute provider feed adapters."""

    provider_id: str
    provider_name: str
    source_url: str

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds

    @abstractmethod
    async def fetch_observations(self) -> List[Observation]:
        """Fetch and normalize observations from provider."""
        pass

    def get_headers(self) -> Dict[str, str]:
        """Standard HTTP client headers."""
        return {
            "User-Agent": "FSKU-Benchmark-Engine/0.9.0 (+https://github.com/sku-futures/fsku)",
            "Accept": "application/json, text/plain, */*",
        }

    async def _safe_get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Helper to safely execute async GET request and parse JSON."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(url, params=params, headers=self.get_headers())
                if res.status_code == 200:
                    return res.json()
        except Exception:
            return None
        return None
