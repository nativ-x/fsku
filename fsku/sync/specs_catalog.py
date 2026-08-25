"""Hardware specifications catalog synchronizer."""

from __future__ import annotations
from typing import Any, Dict, List
from fsku.core.database import FSKUDb
from fsku.core.models import HardwareSpec

class SpecsCatalogSync:
    """Synchronizes official hardware specifications."""

    HARDWARE_SPECS = [
        {
            "id": "h100_sxm",
            "name": "H100 SXM",
            "gen": "NVIDIA · Hopper",
            "vram": 80,
            "type": "HBM3",
            "bw": 3.35,
            "power": 700,
            "compute": "FP8 3.96 PFLOPS*",
            "src": "h100",
            "release_year": 2022,
        },
        {
            "id": "h200_sxm",
            "name": "H200 SXM",
            "gen": "NVIDIA · Hopper",
            "vram": 141,
            "type": "HBM3e",
            "bw": 4.8,
            "power": 700,
            "compute": "FP8 3.96 PFLOPS*",
            "src": "h200",
            "release_year": 2024,
        },
        {
            "id": "b200_sxm",
            "name": "B200 SXM",
            "gen": "NVIDIA · Blackwell",
            "vram": 180,
            "type": "HBM3e",
            "bw": 8.0,
            "power": 1200,
            "compute": "FP8 10 PFLOPS*",
            "src": "nvidiaComp",
            "release_year": 2025,
        },
        {
            "id": "b300_sxm",
            "name": "B300 SXM",
            "gen": "NVIDIA · Blackwell Ultra",
            "vram": 288,
            "type": "HBM3e",
            "bw": 8.0,
            "power": 1400,
            "compute": "FP8 10 PFLOPS*",
            "src": "nvidiaComp",
            "release_year": 2026,
        },
        {
            "id": "mi300x",
            "name": "MI300X",
            "gen": "AMD · CDNA 3",
            "vram": 192,
            "type": "HBM3",
            "bw": 5.3,
            "power": 750,
            "compute": "BF16 1.30 PFLOPS",
            "src": "amd",
            "release_year": 2023,
        },
    ]

    @classmethod
    def sync_specs(cls, db: FSKUDb) -> int:
        """Upsert official hardware specs into the database."""
        count = 0
        for spec in cls.HARDWARE_SPECS:
            existing = db.specs.find_by_id(spec["id"])
            if existing:
                db.specs.update_by_id(spec["id"], spec)
            else:
                db.specs.insert(spec)
            count += 1
        return count
