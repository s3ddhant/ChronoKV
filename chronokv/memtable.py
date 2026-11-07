"""
ChronoKV: MemTable Management and Immutable Freeze Lifecycle.

Architectural Concept:
The MemTable is the volatile in-memory buffer where all incoming write operations (PUT and DELETE)
are staged before being flushed to immutable SSTable disk files.

Lifecycle Transitions:
1. Active MemTable: Accepts concurrent writes, backed by an active binary WAL.
2. Freeze / Transition: Once memory threshold (memtable_size_bytes) is crossed:
   - The Active MemTable is frozen into an Immutable MemTable.
   - A fresh Active MemTable and a new WAL are atomically created.
   - The Immutable MemTable is enqueued for asynchronous flushing to disk as an SSTable.
3. Disk Flush:
   - Records are written in sorted order into an SSTable with Bloom filter and Sparse index.
   - The old WAL file associated with the flushed MemTable is safely unlinked.
"""

from __future__ import annotations
import os
import threading
import time
from typing import List, Optional, Tuple
from chronokv.skiplist import SkipList
from chronokv.wal import WALWriter
from chronokv.sstable import SSTableWriter
from chronokv.types import Record, EngineConfig


class MemTableManager:
    """
    Coordinates active and immutable MemTables with thread-safe atomic swapping.
    """
    def __init__(self, config: EngineConfig) -> None:
        self.config: EngineConfig = config
        self._lock = threading.Lock()
        
        # Unique nanosecond counter for WAL and SSTable generation
        self._generation: int = time.time_ns()
        self._active_wal_path = os.path.join(self.config.data_dir, f"wal_{self._generation}.wal")
        self.wal_writer = WALWriter(self._active_wal_path, sync_on_write=self.config.wal_sync_on_write)
        
        self.active_memtable: SkipList = SkipList()
        # List of (ImmutableSkipList, WAL_filepath, generation_id)
        self.immutable_memtables: List[Tuple[SkipList, str, int]] = []

    @property
    def active_size_bytes(self) -> int:
        return self.active_memtable.byte_size

    def put(self, key: bytes, value: bytes, is_tombstone: bool = False) -> Tuple[Record, bool]:
        """
        Writes a key-value pair or tombstone.
        
        Steps:
        1. Append to binary WAL.
        2. Insert into active SkipList.
        3. Check if flush threshold is reached.
        
        Returns:
            (Record, needs_flush: bool)
        """
        # WAL append occurs first for ACID Durability
        ts = time.time_ns()
        temp_record = Record(key=key, value=value, timestamp_ns=ts, is_tombstone=is_tombstone)
        self.wal_writer.append(temp_record)

        # In-memory SkipList insertion
        record = self.active_memtable.put(
            key=key,
            value=value,
            is_tombstone=is_tombstone,
            timestamp_ns=ts
        )

        needs_flush = self.active_memtable.byte_size >= self.config.memtable_size_bytes
        return record, needs_flush

    def get(self, key: bytes) -> Optional[Record]:
        """
        Queries in-memory tables:
        First checks Active MemTable, then Immutable MemTables (newest to oldest).
        """
        # 1. Check Active MemTable
        rec = self.active_memtable.get(key)
        if rec is not None:
            return rec

        # 2. Check Immutable MemTables under lock
        with self._lock:
            for imm_table, _, _ in reversed(self.immutable_memtables):
                rec = imm_table.get(key)
                if rec is not None:
                    return rec

        return None

    def scan(self, start_key: Optional[bytes] = None, end_key: Optional[bytes] = None) -> List[Record]:
        """
        Scans in-memory tables. Returns deduplicated records favoring newest timestamps.
        """
        found_map: dict[bytes, Record] = {}
        
        with self._lock:
            imm_snapshots = [t[0] for t in self.immutable_memtables]

        # Scan oldest immutables first, then active to ensure newer timestamps overwrite
        for imm in imm_snapshots:
            for r in imm.scan(start_key, end_key):
                if r.key not in found_map or r.timestamp_ns > found_map[r.key].timestamp_ns:
                    found_map[r.key] = r

        for r in self.active_memtable.scan(start_key, end_key):
            if r.key not in found_map or r.timestamp_ns > found_map[r.key].timestamp_ns:
                found_map[r.key] = r

        return sorted(found_map.values(), key=lambda r: r.key)

    def freeze_active_to_immutable(self) -> Optional[str]:
        """
        Freezes the current Active MemTable into an Immutable MemTable and spawns
        a new Active MemTable with a fresh WAL.
        
        Returns:
            The WAL filepath of the frozen MemTable.
        """
        with self._lock:
            if len(self.active_memtable) == 0:
                return None

            frozen_memtable = self.active_memtable
            old_wal_path = self._active_wal_path
            old_gen = self._generation

            # Flush and close old WAL
            self.wal_writer.close()

            # Atomically advance generation and initialize new active state
            self._generation += 1
            self._active_wal_path = os.path.join(self.config.data_dir, f"wal_{self._generation}.wal")
            self.wal_writer = WALWriter(self._active_wal_path, sync_on_write=self.config.wal_sync_on_write)
            self.active_memtable = SkipList()

            self.immutable_memtables.append((frozen_memtable, old_wal_path, old_gen))
            return old_wal_path

    def flush_oldest_immutable(self) -> Optional[str]:
        """
        Flushes the oldest Immutable MemTable to an SSTable file on disk.
        Once written and fsync'd, removes it from memory and unlinks its WAL.
        
        Returns:
            The path of the newly written SSTable file, or None if no immutable table exists.
        """
        target = None
        with self._lock:
            if not self.immutable_memtables:
                return None
            target = self.immutable_memtables[0]

        imm_table, wal_path, gen = target
        records = imm_table.iter_all()
        sstable_path = os.path.join(self.config.data_dir, f"sstable_{gen}_{int(time.time_ns())}.sst")

        # Construct SSTable on disk
        writer = SSTableWriter(
            filepath=sstable_path,
            expected_records=len(records),
            sparse_interval=self.config.sparse_index_interval,
            bloom_fp_rate=self.config.bloom_false_positive_rate
        )
        writer.write_records(records)

        # Unlink the obsolete WAL file
        try:
            if os.path.exists(wal_path):
                os.remove(wal_path)
        except OSError:
            pass

        # Remove from immutable queue
        with self._lock:
            if self.immutable_memtables and self.immutable_memtables[0][2] == gen:
                self.immutable_memtables.pop(0)

        return sstable_path
