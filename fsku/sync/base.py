"""Base provider adapter interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional
import httpx
from fsku import __version__
from fsku.core.models import Observation, ProviderSyncReport

class BaseProviderAdapter(ABC):
    """Abstract base class for all compute provider feed adapters.

    Every adapter declares how it sources prices, and the sync engine reports
    that verbatim. Two modes exist:

      live     -- ``fetch_observations`` performs HTTP requests against the
                  provider's public pricing API. Rows it returns are tagged
                  ``provenance="live"``; if a request fails or returns nothing
                  usable and the adapter substitutes a constant instead, that
                  row is tagged ``provenance="fallback"`` and the substitution
                  is recorded via :meth:`note_fallback`.
      catalog  -- ``fetch_observations`` reads a hardcoded rate table and never
                  touches the network. Rows are tagged ``provenance="catalog"``
                  and carry ``recorded_at = catalog_as_of`` -- the date the
                  constants were captured -- NOT the time of the sync run.

    A sync report that said "Providers Polled: 6 / SUCCESS" while five adapters
    read constants and re-stamped them with today's date is the kind of opacity
    this project exists to remove. The mode and the counters below make the
    difference visible in the log, the CLI, the API and the dashboard.
    """

    provider_id: str
    provider_name: str
    source_url: str

    # How this adapter sources prices. Catalog adapters MUST set catalog_as_of.
    mode: Literal["live", "catalog"] = "catalog"
    # ISO date the hardcoded rates were captured from source_url. Used as
    # recorded_at for catalog rows and for a live adapter's fallback rows.
    catalog_as_of: Optional[str] = None
    # Capacity tier every row from this adapter belongs to, unless the row
    # sets its own (an adapter that quotes several tiers sets it per row).
    # See Observation.tier for the taxonomy.
    tier: Optional[str] = None

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds
        self.requests_attempted = 0
        self.requests_succeeded = 0
        self.fallbacks: List[str] = []
        self.notes: List[str] = []

    @abstractmethod
    async def fetch_observations(self) -> List[Observation]:
        """Fetch and normalize observations from provider."""
        pass

    def get_headers(self) -> Dict[str, str]:
        """Standard HTTP client headers."""
        return {
            "User-Agent": f"FSKU-Benchmark-Engine/{__version__} (+https://github.com/nativ-x/fsku)",
            "Accept": "application/json, text/plain, */*",
        }

    def note_fallback(self, reason: str) -> None:
        """Record that a constant was substituted for a live value, and why."""
        self.fallbacks.append(reason)

    async def _safe_get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Execute an async GET and parse JSON, counting the attempt and its outcome.

        Returns ``None`` on any failure. Callers that substitute a constant on
        ``None`` must call :meth:`note_fallback` so the substitution is reported.
        """
        self.requests_attempted += 1
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(url, params=params, headers=self.get_headers())
                if res.status_code == 200:
                    self.requests_succeeded += 1
                    return res.json()
                self.notes.append(f"GET {url} -> HTTP {res.status_code}")
        except Exception as exc:  # network, timeout, JSON decode
            self.notes.append(f"GET {url} -> {type(exc).__name__}: {exc}")
        return None

    def report(self, observations: List[Observation]) -> ProviderSyncReport:
        """Summarize what this adapter did during one sync run."""
        live = sum(1 for o in observations if o.provenance == "live")
        fallback = sum(1 for o in observations if o.provenance == "fallback")
        catalog = sum(1 for o in observations if o.provenance == "catalog")
        return ProviderSyncReport(
            provider=self.provider_name,
            mode=self.mode,
            requests_attempted=self.requests_attempted,
            requests_succeeded=self.requests_succeeded,
            observations=len(observations),
            live=live,
            fallback=fallback,
            catalog=catalog,
            as_of=self.catalog_as_of,
            fallbacks=list(self.fallbacks),
            notes=list(self.notes),
        )
