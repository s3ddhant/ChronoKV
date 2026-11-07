"""
ChronoKV: Production-Grade LSM-Tree Key-Value Storage Engine.

Architecture Overview:
ChronoKV is an embedded Log-Structured Merge-Tree storage engine providing high-throughput
writes and reliable durability.

Write Path:
  Client -> Append to Binary WAL (fsync/buffered) -> Insert into Concurrent SkipList MemTable
  When MemTable size exceeds threshold -> Freeze to Immutable MemTable -> Flush to SSTable on disk.

Read Path:
  Client -> Active MemTable -> Immutable MemTables -> SSTables (newest to oldest)
  For each SSTable:
    Bloom Filter Check (O(k) CPU bit lookups; if 0, bypass disk I/O)
    -> Binary Search on In-Memory Sparse Index
    -> Seek to Data Block slice and scan <= sparse_interval records.

Compaction:
  Background worker triggers multi-way merge sort when L0 SSTable count reaches threshold,
  deduplicating keys and permanently evicting tombstones.
"""

from __future__ import annotations
import glob
import os
import threading
import time
from typing import Dict, List, Optional, Tuple, Union
from chronokv.types import EngineConfig, Record
from chronokv.memtable import MemTableManager
from chronokv.sstable import SSTableReader
from chronokv.compactor import Compactor
from chronokv.wal import WALReader


class ChronoKV:
    """
    Main ChronoKV Storage Engine instance.
    """
    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        self.config: EngineConfig = config or EngineConfig()
        os.makedirs(self.config.data_dir, exist_ok=True)

        self._lock = threading.RLock()
        self._sstables_lock = threading.RLock()
        self._sstables: List[SSTableReader] = []

        # Compactor
        self.compactor = Compactor(self.config)

        # Statistics
        self._total_puts: int = 0
        self._total_gets: int = 0
        self._total_deletes: int = 0
        self._bloom_filter_rejections: int = 0
        self._bloom_filter_positives: int = 0

        # Background worker management
        self._shutdown_event = threading.Event()
        self._background_thread: Optional[threading.Thread] = None

        # 1. Mount existing SSTables from disk
        self._load_existing_sstables()

        # 2. Initialize MemTable manager
        self.mem_manager = MemTableManager(self.config)

        # 3. Recover un-flushed data from existing WALs
        self._recover_wal_state()

        # 4. Start background flush & compaction daemon
        self._start_background_worker()

    def _load_existing_sstables(self) -> None:
        """Discovers and mounts all existing SSTable files on disk sorted by timestamp."""
        pattern = os.path.join(self.config.data_dir, "sstable_*.sst")
        files = glob.glob(pattern)
        # Sort files chronologically by mtime or filename
        files.sort(key=lambda p: os.path.getmtime(p))

        with self._sstables_lock:
            for fpath in files:
                try:
                    reader = SSTableReader(fpath)
                    self._sstables.append(reader)
                except Exception as err:
                    # Log or ignore corrupted SSTables
                    pass

    def _recover_wal_state(self) -> None:
        """Scans for leftover WAL files and replays uncommitted mutations."""
        pattern = os.path.join(self.config.data_dir, "wal_*.wal")
        wal_files = glob.glob(pattern)
        wal_files.sort(key=lambda p: os.path.getmtime(p))

        total_recovered = 0
        for wpath in wal_files:
            # Skip the newly active WAL writer file
            if os.path.abspath(wpath) == os.path.abspath(self.mem_manager._active_wal_path):
                continue
            recovered = WALReader.recover_into(wpath, self.mem_manager.active_memtable)
            total_recovered += recovered

    def _start_background_worker(self) -> None:
        """Launches daemon thread for periodic flush and compaction."""
        self._background_thread = threading.Thread(
            target=self._background_loop, daemon=True, name="ChronoKV-Worker"
        )
        self._background_thread.start()

    def _background_loop(self) -> None:
        """Runs periodic flush and compaction checks."""
        while not self._shutdown_event.is_set():
            try:
                # 1. Flush any immutable MemTables
                flushed_path = self.mem_manager.flush_oldest_immutable()
                if flushed_path:
                    try:
                        new_reader = SSTableReader(flushed_path)
                        with self._sstables_lock:
                            self._sstables.append(new_reader)
                    except Exception:
                        pass

                # 2. Trigger compaction if threshold exceeded
                self._check_and_compact()

            except Exception:
                pass

            self._shutdown_event.wait(timeout=0.25)

    def _check_and_compact(self) -> None:
        """Checks if L0 SSTable count exceeds threshold and executes compaction."""
        with self._sstables_lock:
            if len(self._sstables) < self.config.l0_compaction_threshold:
                return
            tables_to_compact = list(self._sstables)
            paths = [t.filepath for t in tables_to_compact]

        # Compact all tables into one bottom-level table
        result = self.compactor.compact_tables(paths, is_bottom_level=True)
        if result:
            new_path, _, _ = result
            try:
                new_reader = SSTableReader(new_path)
                with self._sstables_lock:
                    # Close old readers
                    for r in tables_to_compact:
                        r.close()
                    self._sstables = [new_reader]
            except Exception:
                pass

    def put(self, key: Union[str, bytes], value: Union[str, bytes]) -> None:
        """
        Stores a key-value pair into the LSM-Tree.
        
        Complexity:
            Time: O(log N) amortized memory insert + sequential append-only disk I/O.
        """
        k_bytes = key.encode("utf-8") if isinstance(key, str) else key
        v_bytes = value.encode("utf-8") if isinstance(value, str) else value

        with self._lock:
            _, needs_flush = self.mem_manager.put(k_bytes, v_bytes, is_tombstone=False)
            self._total_puts += 1
            if needs_flush:
                self.mem_manager.freeze_active_to_immutable()

    def delete(self, key: Union[str, bytes]) -> bool:
        """
        Logically deletes a key by writing a Tombstone record.
        
        Complexity:
            Time: O(log N) amortized.
        """
        k_bytes = key.encode("utf-8") if isinstance(key, str) else key

        with self._lock:
            _, needs_flush = self.mem_manager.put(k_bytes, b"", is_tombstone=True)
            self._total_deletes += 1
            if needs_flush:
                self.mem_manager.freeze_active_to_immutable()
        return True

    def get(self, key: Union[str, bytes]) -> Optional[bytes]:
        """
        Retrieves the value associated with key.
        
        Complexity:
            Best case: O(log N_mem) if resident in Active MemTable.
            Disk case: O(k) Bloom filter check + O(log S) Sparse Index + O(interval) Disk read.
        """
        k_bytes = key.encode("utf-8") if isinstance(key, str) else key
        self._total_gets += 1

        # 1. Search In-Memory MemTables (Active & Immutable)
        rec = self.mem_manager.get(k_bytes)
        if rec is not None:
            return None if rec.is_tombstone else rec.value

        # 2. Search SSTables from newest to oldest
        with self._sstables_lock:
            current_sstables = list(reversed(self._sstables))

        for sstable in current_sstables:
            rec, bloom_checked = sstable.get(k_bytes)
            if not sstable.bloom.contains(k_bytes):
                self._bloom_filter_rejections += 1
                continue
            else:
                self._bloom_filter_positives += 1

            if rec is not None:
                return None if rec.is_tombstone else rec.value

        return None

    def get_with_diagnostics(self, key: Union[str, bytes]) -> Dict:
        """
        Performs a GET query and returns detailed step-by-step diagnostic trace
        (MemTable hit, Bloom filter checks, Sparse index searches, SSTable seeks).
        """
        k_bytes = key.encode("utf-8") if isinstance(key, str) else key
        trace = []
        found_record = None

        # 1. Check Active MemTable
        act_rec = self.mem_manager.active_memtable.get(k_bytes)
        if act_rec:
            trace.append({
                "layer": "Active MemTable",
                "result": "HIT" if not act_rec.is_tombstone else "TOMBSTONE",
                "record": {"key": act_rec.key.decode(errors="replace"), "ts": act_rec.timestamp_ns, "tombstone": act_rec.is_tombstone}
            })
            return {"found": not act_rec.is_tombstone, "value": None if act_rec.is_tombstone else act_rec.value.decode(errors="replace"), "trace": trace}
        else:
            trace.append({"layer": "Active MemTable", "result": "MISS"})

        # 2. Check Immutable MemTables
        for i, (imm, _, gen) in enumerate(reversed(self.mem_manager.immutable_memtables)):
            imm_rec = imm.get(k_bytes)
            if imm_rec:
                trace.append({
                    "layer": f"Immutable MemTable #{i+1} (Gen {gen})",
                    "result": "HIT" if not imm_rec.is_tombstone else "TOMBSTONE",
                    "record": {"key": imm_rec.key.decode(errors="replace"), "ts": imm_rec.timestamp_ns, "tombstone": imm_rec.is_tombstone}
                })
                return {"found": not imm_rec.is_tombstone, "value": None if imm_rec.is_tombstone else imm_rec.value.decode(errors="replace"), "trace": trace}
            else:
                trace.append({"layer": f"Immutable MemTable #{i+1} (Gen {gen})", "result": "MISS"})

        # 3. Check SSTables
        with self._sstables_lock:
            tables = list(reversed(self._sstables))

        for idx, table in enumerate(tables):
            filename = os.path.basename(table.filepath)
            bloom_hit = table.bloom.contains(k_bytes)
            if not bloom_hit:
                trace.append({
                    "layer": f"SSTable: {filename}",
                    "bloom_check": "NEGATIVE (Skipped Disk)",
                    "sparse_index": "SKIPPED",
                    "result": "MISS"
                })
                continue

            rec, _ = table.get(k_bytes)
            if rec:
                trace.append({
                    "layer": f"SSTable: {filename}",
                    "bloom_check": "POSITIVE",
                    "sparse_index": "SEARCHED",
                    "result": "HIT" if not rec.is_tombstone else "TOMBSTONE",
                    "record": {"key": rec.key.decode(errors="replace"), "ts": rec.timestamp_ns, "tombstone": rec.is_tombstone}
                })
                return {"found": not rec.is_tombstone, "value": None if rec.is_tombstone else rec.value.decode(errors="replace"), "trace": trace}
            else:
                trace.append({
                    "layer": f"SSTable: {filename}",
                    "bloom_check": "POSITIVE (False Positive)",
                    "sparse_index": "SEARCHED",
                    "result": "MISS"
                })

        return {"found": False, "value": None, "trace": trace}

    def scan(self, start_key: Optional[Union[str, bytes]] = None, end_key: Optional[Union[str, bytes]] = None) -> List[Tuple[bytes, bytes]]:
        """
        Executes a range scan in [start_key, end_key) across all memory and disk layers,
        reconciling duplicates and filtering tombstones.
        """
        sk = start_key.encode("utf-8") if isinstance(start_key, str) else start_key
        ek = end_key.encode("utf-8") if isinstance(end_key, str) else end_key

        all_records: Dict[bytes, Record] = {}

        # 1. SSTables from oldest to newest
        with self._sstables_lock:
            tables = list(self._sstables)

        for table in tables:
            for r in table.scan(sk, ek):
                if r.key not in all_records or r.timestamp_ns > all_records[r.key].timestamp_ns:
                    all_records[r.key] = r

        # 2. Immutable and Active MemTables
        mem_records = self.mem_manager.scan(sk, ek)
        for r in mem_records:
            if r.key not in all_records or r.timestamp_ns > all_records[r.key].timestamp_ns:
                all_records[r.key] = r

        # 3. Filter out tombstones and sort by key
        live_pairs = [
            (rec.key, rec.value) for rec in sorted(all_records.values(), key=lambda r: r.key)
            if not rec.is_tombstone
        ]
        return live_pairs

    def manual_flush(self) -> Optional[str]:
        """Forces the active MemTable to freeze and flush to disk."""
        with self._lock:
            self.mem_manager.freeze_active_to_immutable()
        flushed_path = self.mem_manager.flush_oldest_immutable()
        if flushed_path:
            reader = SSTableReader(flushed_path)
            with self._sstables_lock:
                self._sstables.append(reader)
        return flushed_path

    def manual_compact(self) -> Optional[Tuple[str, int, int]]:
        """Forces an immediate compaction of all SSTables."""
        with self._sstables_lock:
            if len(self._sstables) < 2:
                return None
            paths = [t.filepath for t in self._sstables]
            old_readers = list(self._sstables)

        result = self.compactor.compact_tables(paths, is_bottom_level=True)
        if result:
            new_path, inp, out = result
            new_reader = SSTableReader(new_path)
            with self._sstables_lock:
                for r in old_readers:
                    r.close()
                self._sstables = [new_reader]
            return result
        return None

    def get_stats(self) -> Dict:
        """Gathers runtime engine diagnostics."""
        with self._sstables_lock:
            sstable_count = len(self._sstables)
            total_disk_bytes = sum(t.file_size for t in self._sstables)
            sstable_keys = sum(t.key_count for t in self._sstables)
            sstable_details = [
                {
                    "filename": os.path.basename(t.filepath),
                    "size_bytes": t.file_size,
                    "key_count": t.key_count,
                    "sparse_samples": len(t.sparse_index),
                    "bloom_bits": t.bloom.num_bits,
                    "bloom_hashes": t.bloom.num_hashes,
                }
                for t in self._sstables
            ]

        # Scan WAL directory
        wal_files = glob.glob(os.path.join(self.config.data_dir, "wal_*.wal"))
        total_wal_bytes = sum(os.path.getsize(f) for f in wal_files if os.path.exists(f))

        return {
            "active_memtable_size_bytes": self.mem_manager.active_size_bytes,
            "active_memtable_key_count": len(self.mem_manager.active_memtable),
            "immutable_memtables_count": len(self.mem_manager.immutable_memtables),
            "sstable_count": sstable_count,
            "sstable_total_disk_bytes": total_disk_bytes,
            "sstable_total_keys": sstable_keys,
            "wal_files_count": len(wal_files),
            "wal_total_bytes": total_wal_bytes,
            "total_puts": self._total_puts,
            "total_gets": self._total_gets,
            "total_deletes": self._total_deletes,
            "bloom_filter_rejections": self._bloom_filter_rejections,
            "bloom_filter_positives": self._bloom_filter_positives,
            "sstables": sstable_details,
        }

    def close(self) -> None:
        """Gracefully shuts down engine, flushes buffers, and closes file handles."""
        self._shutdown_event.set()
        if self._background_thread and self._background_thread.is_alive():
            self._background_thread.join(timeout=1.0)

        with self._lock:
            self.mem_manager.wal_writer.close()

        with self._sstables_lock:
            for sstable in self._sstables:
                sstable.close()
            self._sstables.clear()
