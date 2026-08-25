"""FSKUDb: A lightweight, zero-dependency embedded NoSQL document database.

Supports JSON collections, atomic transactional file persistence, flexible query filters,
indexing, point-in-time market snapshots, and automatic seed population.
"""

from __future__ import annotations
import json
import os
import re
import shutil
import threading
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

class Collection:
    """Document collection within FSKUDb."""

    def __init__(self, name: str, db: FSKUDb):
        self.name = name
        self.db = db
        self._lock = threading.RLock()
        self._docs: Dict[str, Dict[str, Any]] = {}
        self.file_path = db.storage_dir / f"{name}.json"
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self.file_path.exists():
                try:
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            self._docs = {doc.get("id", str(i)): doc for i, doc in enumerate(data)}
                        elif isinstance(data, dict):
                            self._docs = data
                except Exception as e:

                    backup_path = self.file_path.with_suffix(".corrupt.bak")
                    shutil.copyfile(self.file_path, backup_path)
                    self._docs = {}
            else:
                self._docs = {}

    def _persist(self) -> None:
        with self._lock:
            self.db.storage_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = self.file_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(list(self._docs.values()), f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            if tmp_path.exists():
                if os.name == "nt" and self.file_path.exists():
                    os.replace(tmp_path, self.file_path)
                else:
                    tmp_path.replace(self.file_path)

    def insert(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a document and persist."""
        with self._lock:
            doc_id = str(doc.get("id") or doc.get("_id") or len(self._docs) + 1)
            doc["id"] = doc_id
            self._docs[doc_id] = doc.copy()
            self._persist()
            return doc

    def insert_many(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert multiple documents in a single atomic write."""
        with self._lock:
            inserted = []
            for i, doc in enumerate(docs):
                doc_id = str(doc.get("id") or doc.get("_id") or f"{len(self._docs) + i + 1}")
                doc_copy = doc.copy()
                doc_copy["id"] = doc_id
                self._docs[doc_id] = doc_copy
                inserted.append(doc_copy)
            self._persist()
            return inserted

    def find_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Find a single document by its ID."""
        with self._lock:
            doc = self._docs.get(str(doc_id))
            return doc.copy() if doc else None

    def find(
        self,
        filter_query: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        reverse: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query documents matching filter criteria."""
        with self._lock:
            results = []
            for doc in self._docs.values():
                if not filter_query or self._matches(doc, filter_query):
                    results.append(doc.copy())

            if sort_by:
                def sort_key(item: Dict[str, Any]):
                    v = item.get(sort_by)
                    if v is None:
                        return (1, "")
                    if isinstance(v, (int, float)):
                        return (0, v)
                    return (0, str(v).lower())
                results.sort(key=sort_key, reverse=reverse)

            if offset > 0:
                results = results[offset:]
            if limit is not None and limit > 0:
                results = results[:limit]

            return results

    def find_one(self, filter_query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find the first matching document."""
        res = self.find(filter_query, limit=1)
        return res[0] if res else None

    def update(self, filter_query: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """Update matching documents."""
        with self._lock:
            matched = 0
            for doc_id, doc in list(self._docs.items()):
                if self._matches(doc, filter_query):
                    doc.update(updates)
                    self._docs[doc_id] = doc
                    matched += 1
            if matched > 0:
                self._persist()
            return matched

    def update_by_id(self, doc_id: str, updates: Dict[str, Any]) -> bool:
        """Update a specific document by ID."""
        with self._lock:
            doc = self._docs.get(str(doc_id))
            if doc:
                doc.update(updates)
                self._docs[str(doc_id)] = doc
                self._persist()
                return True
            return False

    def delete(self, filter_query: Dict[str, Any]) -> int:
        """Delete matching documents."""
        with self._lock:
            to_delete = [
                doc_id for doc_id, doc in self._docs.items()
                if self._matches(doc, filter_query)
            ]
            for doc_id in to_delete:
                del self._docs[doc_id]
            if to_delete:
                self._persist()
            return len(to_delete)

    def delete_by_id(self, doc_id: str) -> bool:
        """Delete a single document by ID."""
        with self._lock:
            if str(doc_id) in self._docs:
                del self._docs[str(doc_id)]
                self._persist()
                return True
            return False

    def clear(self) -> None:
        """Clear all documents in the collection."""
        with self._lock:
            self._docs.clear()
            self._persist()

    def count(self, filter_query: Optional[Dict[str, Any]] = None) -> int:
        """Count matching documents."""
        with self._lock:
            if not filter_query:
                return len(self._docs)
            return sum(1 for doc in self._docs.values() if self._matches(doc, filter_query))

    @staticmethod
    def _matches(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        """Evaluate NoSQL filter criteria against a document."""
        for field, target in query.items():
            val = doc.get(field)
            if isinstance(target, dict):

                for op, op_val in target.items():
                    if op == "$eq" and val != op_val:
                        return False
                    elif op == "$ne" and val == op_val:
                        return False
                    elif op == "$gt" and not (val is not None and val > op_val):
                        return False
                    elif op == "$gte" and not (val is not None and val >= op_val):
                        return False
                    elif op == "$lt" and not (val is not None and val < op_val):
                        return False
                    elif op == "$lte" and not (val is not None and val <= op_val):
                        return False
                    elif op == "$in":
                        if isinstance(val, (list, tuple, set)):
                            if not any(x in op_val for x in val):
                                return False
                        elif val not in op_val:
                            return False
                    elif op == "$nin":
                        if isinstance(val, (list, tuple, set)):
                            if any(x in op_val for x in val):
                                return False
                        elif val in op_val:
                            return False
                    elif op == "$contains":
                        if val is None:
                            return False
                        if isinstance(val, (list, tuple, set)):
                            if not any(str(op_val).lower() in str(x).lower() for x in val):
                                return False
                        elif str(op_val).lower() not in str(val).lower():
                            return False
                    elif op == "$regex":
                        if val is None or not re.search(str(op_val), str(val), re.IGNORECASE):
                            return False
            else:
                if val != target:
                    return False
        return True

class FSKUDb:
    """Primary embedded NoSQL database instance for FSKU."""

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None):
        if storage_dir is None:
            base = Path(__file__).resolve().parent.parent.parent / "data" / "fsku_db"
        else:
            base = Path(storage_dir)
        self.storage_dir = base
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._collections: Dict[str, Collection] = {}
        self._lock = threading.RLock()
        self._ensure_seeds()

    def collection(self, name: str) -> Collection:
        """Get or initialize a collection."""
        with self._lock:
            if name not in self._collections:
                self._collections[name] = Collection(name, self)
            return self._collections[name]

    @property
    def observations(self) -> Collection:
        return self.collection("observations")

    @property
    def snapshots(self) -> Collection:
        return self.collection("snapshots")

    @property
    def specs(self) -> Collection:
        return self.collection("specs")

    @property
    def sources(self) -> Collection:
        return self.collection("sources")

    @property
    def sync_logs(self) -> Collection:
        return self.collection("sync_logs")

    def create_snapshot(self, label: str = "Market snapshot") -> Dict[str, Any]:
        """Generate an immutable point-in-time market snapshot."""
        obs = self.observations.find()
        now = datetime.now(timezone.utc).isoformat()

        obs_json = json.dumps(obs, sort_keys=True)
        checksum = hashlib.sha256(obs_json.encode("utf-8")).hexdigest()[:12]
        snapshot_id = f"snap_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{checksum[:6]}"

        from fsku.core.pricing import PricingEngine
        kpis = PricingEngine.calculate_kpis(obs)

        snapshot_doc = {
            "id": snapshot_id,
            "timestamp": now,
            "label": label,
            "observation_count": len(obs),
            "source_count": kpis.get("source_count", 0),
            "gpu_count": kpis.get("gpu_families_count", 0),
            "median_rate": kpis.get("median_observed_rate", 0.0),
            "h100_dispersion": kpis.get("h100_dispersion", 0.0),
            "checksum": checksum,
            "observations": obs,
        }
        self.snapshots.insert(snapshot_doc)
        return snapshot_doc

    def _ensure_seeds(self) -> None:
        """Seed collections from defaults if empty."""
        seeds_dir = Path(__file__).resolve().parent.parent / "data" / "seeds"
        if not seeds_dir.exists():
            return

        for name in ["sources", "specs", "observations", "snapshots"]:
            col = self.collection(name)
            if col.count() == 0:
                seed_file = seeds_dir / f"{name}.json"
                if seed_file.exists():
                    try:
                        with open(seed_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                col.insert_many(data)
                            elif isinstance(data, dict):
                                col.insert_many(list(data.values()))
                    except Exception:
                        pass

_GLOBAL_DB: Optional[FSKUDb] = None
_DB_LOCK = threading.Lock()

def get_db(storage_dir: Optional[Union[str, Path]] = None) -> FSKUDb:
    """Retrieve global thread-safe FSKUDb singleton instance."""
    global _GLOBAL_DB
    with _DB_LOCK:
        if _GLOBAL_DB is None or storage_dir is not None:
            _GLOBAL_DB = FSKUDb(storage_dir)
        return _GLOBAL_DB
