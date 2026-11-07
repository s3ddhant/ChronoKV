"""
ChronoKV: Multi-Way Merge Compaction and Tombstone Eviction.

Theoretical Background:
In LSM-Trees, sequential writes cause multiple versions of keys and tombstones (deletions)
to accumulate across multiple SSTables on disk. This results in Read Amplification (having to check
multiple files) and Space Amplification (storing obsolete or deleted data).

Compaction (O'Neil et al., 1996):
- Selects K sorted SSTables and executes a K-Way Merge Sort in O(N * log K) time.
- Uses a Min-Heap (priority queue) to stream records in lexicographical order.
- Conflict Resolution: For duplicate keys, retains only the record with the maximum timestamp.
- Tombstone Reconciliation: If the newest version of a key is a tombstone, and compaction
  includes all SSTables (or reaches the bottom level), the tombstone is purged permanently from disk!
- Atomic Disk Replacement: Writes the new SSTable to a temporary file before atomically renaming
  and unlinking the superseded source SSTables.
"""

from __future__ import annotations
import heapq
import os
import threading
import time
from typing import List, Optional, Tuple, Callable
from chronokv.sstable import SSTableReader, SSTableWriter
from chronokv.types import Record, EngineConfig


class SSTableIteratorWrapper:
    """Helper to wrap generator with a peekable state for heapq."""
    __slots__ = ("index", "gen", "current")

    def __init__(self, index: int, gen) -> None:
        self.index: int = index
        self.gen = gen
        self.advance()

    def advance(self) -> None:
        try:
            self.current: Optional[Record] = next(self.gen)
        except StopIteration:
            self.current = None


class Compactor:
    """
    Executes multi-way merge sort over SSTables, reconciling tombstones and deduplicating keys.
    """
    def __init__(self, config: EngineConfig) -> None:
        self.config: EngineConfig = config
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def compact_tables(
        self,
        sstable_paths: List[str],
        is_bottom_level: bool = True
    ) -> Optional[Tuple[str, int, int]]:
        """
        Merges specified SSTable files into a single compacted SSTable.
        
        Args:
            sstable_paths: List of SSTable disk paths to merge.
            is_bottom_level: If True, tombstones are permanently purged.
            
        Returns:
            Tuple of (new_sstable_path, total_input_keys, surviving_output_keys)
        """
        if len(sstable_paths) < 2:
            return None

        readers: List[SSTableReader] = []
        for path in sstable_paths:
            try:
                readers.append(SSTableReader(path))
            except Exception:
                pass

        if len(readers) < 2:
            for r in readers:
                r.close()
            return None

        # Prepare heap for K-Way Merge Sort
        # Heap item: (record.key, -record.timestamp_ns, iterator_index, wrapper)
        heap: List[Tuple[bytes, int, int, SSTableIteratorWrapper]] = []
        total_input_keys = 0

        for i, reader in enumerate(readers):
            wrapper = SSTableIteratorWrapper(i, reader.iter_all())
            if wrapper.current is not None:
                total_input_keys += 1
                heapq.heappush(heap, (wrapper.current.key, -wrapper.current.timestamp_ns, i, wrapper))

        temp_compacted_path = os.path.join(
            self.config.data_dir, f"compacting_{int(time.time_ns())}.tmp"
        )
        final_compacted_path = os.path.join(
            self.config.data_dir, f"sstable_compacted_{int(time.time_ns())}.sst"
        )

        surviving_records: List[Record] = []
        last_processed_key: Optional[bytes] = None

        # Execute K-Way Merge
        while heap:
            key, neg_ts, idx, wrapper = heapq.heappop(heap)
            rec = wrapper.current

            # Advance this iterator and push back if more records exist
            wrapper.advance()
            if wrapper.current is not None:
                total_input_keys += 1
                heapq.heappush(heap, (wrapper.current.key, -wrapper.current.timestamp_ns, idx, wrapper))

            # Deduplication: Because heap orders by (key ASC, -timestamp ASC),
            # the first time we see `key`, it is guaranteed to be the newest version!
            if key == last_processed_key:
                # Obsolete historical version; drop it
                continue

            last_processed_key = key

            # Tombstone Reconciliation
            if rec.is_tombstone and is_bottom_level:
                # Permanent eviction: Do not emit tombstone to disk
                continue

            surviving_records.append(rec)

        # Write merged records to temporary SSTable
        writer = SSTableWriter(
            filepath=temp_compacted_path,
            expected_records=len(surviving_records),
            sparse_interval=self.config.sparse_index_interval,
            bloom_fp_rate=self.config.bloom_false_positive_rate
        )
        writer.write_records(surviving_records)

        # Close all open readers
        for reader in readers:
            reader.close()

        # Atomically rename temp file to final SSTable path
        os.replace(temp_compacted_path, final_compacted_path)

        # Unlink old source SSTables
        for path in sstable_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

        return final_compacted_path, total_input_keys, len(surviving_records)
