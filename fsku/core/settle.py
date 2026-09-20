"""The daily settlement: sync, snapshot, verify, publish the Fix, append history.

Ornn settles OCPI once a day at 4 pm ET and stands behind the number; Silicon
Data publishes daily. This is the free equivalent. One run:

  1. resync every adapter (live and catalog, honestly labelled);
  2. take a snapshot of the tape and verify its checksum re-derives;
  3. compute the Fix for each settled family from that snapshot's constituents;
  4. append one compact row per family to `fix_history` -- values, depth,
     constituent ids, snapshot id and checksum -- so any published number can
     be traced to the exact rows behind it without re-reading the snapshot.

Settlement is idempotent per UTC date: settling twice on one day replaces that
day's row rather than appending a second.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fsku.core.database import FSKUDb
from fsku.core.fix import FixEngine, FixResult

SETTLED_FAMILIES = ("H100", "H200", "B200", "A100")


class FixHistoryRow(BaseModel):
    id: str
    date: str = Field(description="UTC settlement date YYYY-MM-DD")
    family: str
    settled_at: str
    neocloud: Optional[float]
    neocloud_n: int
    neocloud_providers: List[str]
    hyperscaler: Optional[float]
    hyperscaler_n: int
    standardized: Optional[float] = Field(default=None, description="Term-standardized, seller-balanced reading (FixEngine.standardized)")
    standardized_n: int = Field(default=0, description="Sellers that voted")
    standardized_ids: List[str] = Field(default_factory=list, description="The one quote per seller")
    as_of: str
    snapshot_id: str
    checksum: str
    verified: bool
    constituent_ids: Dict[str, List[str]]
    method: str
    sync_status: Optional[str] = None
    sync_live: int = 0
    sync_fallback: int = 0
    sync_catalog: int = 0


class SettlementResult(BaseModel):
    date: str
    settled_at: str
    snapshot_id: str
    checksum: str
    verified: bool
    sync_status: Optional[str]
    rows: List[FixHistoryRow]


class SettlementEngine:
    def __init__(self, db: FSKUDb):
        self.db = db

    @property
    def history(self):
        return self.db.collection("fix_history")

    async def settle(self, families=SETTLED_FAMILIES, do_sync: bool = True, label: Optional[str] = None) -> SettlementResult:
        from fsku.sync.engine import SyncEngine
        now = datetime.now(timezone.utc)
        date = now.strftime("%Y-%m-%d")
        sync_log = None
        if do_sync:
            sync_log = await SyncEngine(db=self.db).resync(create_snapshot=False)

        snap = self.db.create_snapshot(label=label or f"Daily Fix {date}")
        self.db.snapshots.update_by_id(snap["id"], {"provenance": "settle"})
        verify = self.db.verify_snapshot(snap["id"])
        obs = snap["observations"]

        rows: List[FixHistoryRow] = []
        for fam in families:
            fx: FixResult = FixEngine.compute(obs, fam)
            neo, hyp = fx.segments["neocloud"], fx.segments["hyperscaler"]
            row = FixHistoryRow(
                id=f"fix_{date}_{fam.lower()}",
                date=date, family=fam.upper(), settled_at=now.isoformat(),
                neocloud=neo.value, neocloud_n=neo.n, neocloud_providers=neo.providers,
                hyperscaler=hyp.value, hyperscaler_n=hyp.n,
                standardized=fx.standardized.value if fx.standardized else None,
                standardized_n=fx.standardized.n_sellers if fx.standardized else 0,
                standardized_ids=[q.id for q in fx.standardized.quotes] if fx.standardized else [],
                as_of=fx.as_of, snapshot_id=snap["id"], checksum=snap["checksum"],
                verified=bool(verify.get("verified")),
                constituent_ids={"neocloud": [c.id for c in neo.constituents], "hyperscaler": [c.id for c in hyp.constituents]},
                method=fx.method,
                sync_status=sync_log.status if sync_log else None,
                sync_live=sync_log.live_count if sync_log else 0,
                sync_fallback=sync_log.fallback_count if sync_log else 0,
                sync_catalog=sync_log.catalog_count if sync_log else 0,
            )
            doc = row.model_dump()
            if self.history.find_by_id(row.id):
                self.history.update_by_id(row.id, doc)
            else:
                self.history.insert(doc)
            rows.append(row)

        return SettlementResult(date=date, settled_at=now.isoformat(), snapshot_id=snap["id"], checksum=snap["checksum"],
                                verified=bool(verify.get("verified")), sync_status=sync_log.status if sync_log else None, rows=rows)

    def history_for(self, family: str, limit: int = 365) -> List[Dict[str, Any]]:
        rows = [r for r in self.history.find() if r.get("family") == family.upper()]
        rows.sort(key=lambda r: r.get("date", ""))
        return rows[-limit:]
