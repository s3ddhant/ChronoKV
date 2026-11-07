"""
ChronoKV: Core Type Definitions, Enums, and Common Data Structures.

Academic Specification:
- Log-Structured Merge-Tree (LSM-Tree) primitives.
- Binary record formats, tombstone sentinels, and configuration dataclasses.
"""

from __future__ import annotations
import dataclasses
import time
from typing import Optional, NamedTuple

# Binary protocol constants
WAL_MAGIC: bytes = b"CKVWAL01"
SSTABLE_MAGIC: bytes = b"CKVSST01"
FOOTER_SIZE_BYTES: int = 44  # [IndexOffset: 8B, IndexLen: 8B, BloomOffset: 8B, BloomLen: 8B, KeyCount: 4B, Magic: 8B]
WAL_HEADER_SIZE_BYTES: int = 21  # [CRC32: 4B, Timestamp: 8B, KeyLen: 4B, ValLen: 4B, Flag: 1B]

FLAG_PUT: int = 0x00
FLAG_TOMBSTONE: int = 0x01


@dataclasses.dataclass(frozen=True, slots=True)
class Record:
    """
    Fundamental key-value record within the LSM-Tree.
    
    Attributes:
        key: Raw byte sequence representing the key.
        value: Raw byte sequence representing the value (empty bytes if tombstone).
        timestamp_ns: Monotonic nanosecond timestamp when the record was accepted.
        is_tombstone: Boolean flag indicating if this entry is a deletion marker.
    """
    key: bytes
    value: bytes
    timestamp_ns: int = dataclasses.field(default_factory=time.time_ns)
    is_tombstone: bool = False

    @property
    def key_size(self) -> int:
        return len(self.key)

    @property
    def value_size(self) -> int:
        return len(self.value)

    @property
    def byte_size(self) -> int:
        """Calculates in-memory and on-disk payload byte size."""
        return len(self.key) + len(self.value) + 17  # 8 (timestamp) + 1 (flag) + 8 (size headers)


class SparseIndexEntry(NamedTuple):
    """
    Entry in the SSTable Sparse Index block.
    
    Attributes:
        key: The key sample at this sparse interval boundary.
        offset: The absolute byte offset in the SSTable data block.
    """
    key: bytes
    offset: int


@dataclasses.dataclass
class EngineConfig:
    """
    Configuration parameters for ChronoKV.
    
    Attributes:
        data_dir: Filesystem path to persist WAL and SSTables.
        memtable_size_bytes: Memory limit before Active MemTable flushes to Immutable.
        sparse_index_interval: Number of keys between sparse index entries in SSTables.
        bloom_false_positive_rate: Targeted probability ε of Bloom filter false positives.
        wal_sync_on_write: If True, forces fsync on every WAL record (strict durability).
        l0_compaction_threshold: Number of SSTables in L0 that triggers background compaction.
    """
    data_dir: str = "data_chronokv"
    memtable_size_bytes: int = 256 * 1024  # 256 KB default for demo/academic testing
    sparse_index_interval: int = 16        # Index every 16 keys
    bloom_false_positive_rate: float = 0.01 # 1% false positive rate
    wal_sync_on_write: bool = False        # High-throughput asynchronous fsync by default
    l0_compaction_threshold: int = 4       # Compact when >= 4 SSTables accumulate
