"""Sync Engine orchestrator for multi-provider market feed ingestion."""

from __future__ import annotations
import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type
from fsku.core.database import FSKUDb, get_db
from fsku.core.models import Observation, SyncLog
from fsku.sync.base import BaseProviderAdapter
from fsku.sync.providers.azure import AzureAdapter
from fsku.sync.providers.runpod import RunPodAdapter
from fsku.sync.providers.coreweave import CoreWeaveAdapter
from fsku.sync.providers.aws import AWSAdapter
from fsku.sync.providers.gcp import GCPAdapter
from fsku.sync.providers.lambda_cloud import LambdaCloudAdapter
from fsku.sync.specs_catalog import SpecsCatalogSync

class SyncEngine:
    """Orchestrates multi-provider compute rate fetching and database synchronization."""

    DEFAULT_ADAPTERS: List[Type[BaseProviderAdapter]] = [
        AzureAdapter,
        RunPodAdapter,
        CoreWeaveAdapter,
        AWSAdapter,
        GCPAdapter,
        LambdaCloudAdapter,
    ]

    def __init__(self, db: Optional[FSKUDb] = None, adapters: Optional[List[Type[BaseProviderAdapter]]] = None):
        self.db = db or get_db()
        self.adapter_classes = adapters or self.DEFAULT_ADAPTERS

    async def resync(
        self,
        provider_filter: Optional[str] = None,
        dry_run: bool = False,
        create_snapshot: bool = True,
        snapshot_label: Optional[str] = None,
        label: Optional[str] = None,
    ) -> SyncLog:
        """Run synchronization across selected or all provider adapters."""
        start_time = time.time()
        start_iso = datetime.now(timezone.utc).isoformat()
        snap_label = label or snapshot_label

        target_classes = self.adapter_classes
        if provider_filter:
            p_filter = provider_filter.lower()
            target_classes = [
                cls for cls in self.adapter_classes
                if p_filter in cls.provider_id.lower() or p_filter in cls.provider_name.lower()
            ]
            if not target_classes:
                raise ValueError(f"No adapter matched provider filter: {provider_filter}")

        adapters = [cls() for cls in target_classes]
        providers_polled = [a.provider_name for a in adapters]

        tasks = [adapter.fetch_observations() for adapter in adapters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        fetched_observations: List[Observation] = []
        errors: List[str] = []

        for i, res in enumerate(results):
            adapter = adapters[i]
            if isinstance(res, Exception):
                errors.append(f"{adapter.provider_name}: {str(res)}")
            elif isinstance(res, list):
                fetched_observations.extend(res)

        added = 0
        updated = 0
        unchanged = 0

        if not dry_run and fetched_observations:

            SpecsCatalogSync.sync_specs(self.db)

            active_keys = set()
            for obs in fetched_observations:
                obs_dict = obs.model_dump()
                key = (obs.provider, obs.gpu, obs.instance, obs.basis, obs.gpuCount)
                active_keys.add(key)

                existing = self.db.observations.find_one({
                    "provider": obs.provider,
                    "gpu": obs.gpu,
                    "instance": obs.instance,
                    "basis": obs.basis,
                    "gpuCount": obs.gpuCount,
                })

                if existing:

                    obs_dict["id"] = existing["id"]
                    self.db.observations.update_by_id(existing["id"], obs_dict)
                    if existing.get("perGpu") != obs.perGpu or existing.get("total") != obs.total:
                        updated += 1
                    else:
                        unchanged += 1
                else:
                    self.db.observations.insert(obs_dict)
                    added += 1

            if not provider_filter:
                all_obs = self.db.observations.find()
                for old_rec in all_obs:
                    old_key = (old_rec.get("provider"), old_rec.get("gpu"), old_rec.get("instance"), old_rec.get("basis"), old_rec.get("gpuCount"))
                    if old_key not in active_keys and old_rec.get("provider") in providers_polled:
                        self.db.observations.delete_by_id(old_rec["id"])

        end_time = time.time()
        end_iso = datetime.now(timezone.utc).isoformat()
        duration_ms = int((end_time - start_time) * 1000)

        snapshot_id = None
        if not dry_run and create_snapshot and (added > 0 or updated > 0 or self.db.snapshots.count() == 0):
            s_label = snap_label or f"Live Resync ({len(providers_polled)} providers)"
            snap = self.db.create_snapshot(label=s_label)
            snapshot_id = snap["id"]

        status = "success" if not errors else ("partial" if fetched_observations else "failed")

        log = SyncLog(
            started_at=start_iso,
            completed_at=end_iso,
            status=status,
            duration_ms=duration_ms,
            providers_polled=providers_polled,
            added_count=added if not dry_run else len(fetched_observations),
            updated_count=updated,
            unchanged_count=unchanged,
            total_active=self.db.observations.count(),
            snapshot_id=snapshot_id,
            errors=errors,
        )

        if not dry_run:
            self.db.sync_logs.insert(log.model_dump())

        return log
