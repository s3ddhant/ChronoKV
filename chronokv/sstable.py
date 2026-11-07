"""
ChronoKV: Immutable SSTable (Sorted String Table) Binary File Format.

Theoretical Background:
An SSTable is an immutable disk file containing sorted, deduplicated records. Once written,
it is never modified in-place, eliminating lock contention and disk fragmentation.

Binary File Layout:
+------------------------------------------------------------------------+
| 1. DATA BLOCK (Sorted Key-Value Records)                               |
|    Record 0: [TS: 8B | Flag: 1B | KLen: 4B | VLen: 4B | Key | Val]    |
|    Record 1: ...                                                       |
+------------------------------------------------------------------------+
| 2. SPARSE INDEX BLOCK                                                  |
|    Entry 0: [KLen: 4B | KeyBytes | Offset: 8B]                         |
|    (Sampled every `index_interval` records for fast binary search)     |
+------------------------------------------------------------------------+
| 3. BLOOM FILTER BLOCK                                                  |
|    [NumBits: 8B | NumHashes: 4B | Count: 4B | BitArray bytes]          |
+------------------------------------------------------------------------+
| 4. FIXED-SIZE FOOTER (44 Bytes at tail of file)                        |
|    [Index_Offset: 8B | Index_Length: 8B | Bloom_Offset: 8B |           |
|     Bloom_Length: 8B | Key_Count: 4B | Magic: b"CKVSST01" (8B)]        |
+------------------------------------------------------------------------+

Complexity Profile:
- Point Lookup:
  1. Bloom Filter Check: O(k) CPU bit operations. If negative => O(0) disk I/O!
  2. Binary Search on In-Memory Sparse Index: O(log(S)) where S = N / interval.
  3. Disk Seek & Small Scan: O(interval) sequential record reads from disk.
- Range Scan: O(log(S) + K) disk streaming.
"""

from __future__ import annotations
import bisect
import os
import struct
from typing import Generator, List, Optional, Tuple
from chronokv.bloom import BloomFilter
from chronokv.types import (
    Record,
    SparseIndexEntry,
    SSTABLE_MAGIC,
    FOOTER_SIZE_BYTES,
    FLAG_PUT,
    FLAG_TOMBSTONE,
)


class SSTableWriter:
    """
    Constructs an immutable SSTable file on disk from an ordered stream of Records.
    """
    def __init__(
        self,
        filepath: str,
        expected_records: int = 1000,
        sparse_interval: int = 16,
        bloom_fp_rate: float = 0.01,
    ) -> None:
        self.filepath: str = filepath
        self.sparse_interval: int = sparse_interval
        self.bloom: BloomFilter = BloomFilter(
            expected_elements=max(1, expected_records),
            false_positive_rate=bloom_fp_rate
        )
        self.sparse_index: List[SparseIndexEntry] = []
        os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
        self._file = open(filepath, "wb")
        self._records_written: int = 0
        self._data_bytes_written: int = 0

    def write_records(self, records: List[Record]) -> int:
        """
        Writes sorted records into the Data Block, populates the Bloom Filter,
        and samples the Sparse Index.
        """
        for record in records:
            # 1. Sparse Index sampling: Record boundary every `sparse_interval` items
            if self._records_written % self.sparse_interval == 0:
                self.sparse_index.append(SparseIndexEntry(key=record.key, offset=self._data_bytes_written))

            # 2. Add key to Bloom Filter
            self.bloom.add(record.key)

            # 3. Serialize and write record to Data Block
            flag = FLAG_TOMBSTONE if record.is_tombstone else FLAG_PUT
            k_len = len(record.key)
            v_len = len(record.value)
            
            # Format: Timestamp (8B), Flag (1B), KeyLen (4B), ValLen (4B)
            rec_header = struct.pack(">QBII", record.timestamp_ns, flag, k_len, v_len)
            frame = rec_header + record.key + record.value
            self._file.write(frame)

            self._data_bytes_written += len(frame)
            self._records_written += 1

        # 4. Serialize and write Sparse Index Block
        index_offset = self._file.tell()
        for entry in self.sparse_index:
            k_len = len(entry.key)
            # Entry: KeyLen (4B) + KeyBytes + Offset (8B)
            entry_bytes = struct.pack(">I", k_len) + entry.key + struct.pack(">Q", entry.offset)
            self._file.write(entry_bytes)
        index_length = self._file.tell() - index_offset

        # 5. Serialize and write Bloom Filter Block
        bloom_offset = self._file.tell()
        bloom_bytes = self.bloom.to_bytes()
        self._file.write(bloom_bytes)
        bloom_length = len(bloom_bytes)

        # 6. Append Fixed-Size Footer (44 Bytes)
        # Format: IndexOffset (8B), IndexLen (8B), BloomOffset (8B), BloomLen (8B), KeyCount (4B), Magic (8B)
        footer = struct.pack(
            ">QQQQI",
            index_offset,
            index_length,
            bloom_offset,
            bloom_length,
            self._records_written
        ) + SSTABLE_MAGIC

        assert len(footer) == FOOTER_SIZE_BYTES, f"Footer size mismatch: expected {FOOTER_SIZE_BYTES}, got {len(footer)}"
        self._file.write(footer)
        self._file.flush()
        os.fsync(self._file.fileno())
        self._file.close()

        return self._records_written


class SSTableReader:
    """
    Random-access reader for an immutable SSTable file.
    
    Caches the Bloom Filter and Sparse Index in memory upon opening;
    data blocks remain on disk and are sought on demand.
    """
    def __init__(self, filepath: str) -> None:
        self.filepath: str = filepath
        self._file = open(filepath, "rb")
        self.file_size: int = os.path.getsize(filepath)

        if self.file_size < FOOTER_SIZE_BYTES:
            raise ValueError(f"SSTable {filepath} is smaller than footer size")

        # 1. Read Footer Metadata
        self._file.seek(self.file_size - FOOTER_SIZE_BYTES)
        footer_bytes = self._file.read(FOOTER_SIZE_BYTES)

        index_offset, index_length, bloom_offset, bloom_length, key_count = struct.unpack(
            ">QQQQI", footer_bytes[:36]
        )
        magic = footer_bytes[36:44]
        if magic != SSTABLE_MAGIC:
            raise ValueError(f"Invalid SSTable magic bytes: {magic!r}")

        self.index_offset: int = index_offset
        self.index_length: int = index_length
        self.bloom_offset: int = bloom_offset
        self.bloom_length: int = bloom_length
        self.key_count: int = key_count

        # 2. Read and deserialize Bloom Filter
        self._file.seek(bloom_offset)
        bloom_data = self._file.read(bloom_length)
        self.bloom: BloomFilter = BloomFilter.from_bytes(bloom_data)

        # 3. Read and deserialize Sparse Index Block
        self._file.seek(index_offset)
        index_data = self._file.read(index_length)
        self.sparse_index: List[SparseIndexEntry] = []
        self._sparse_keys: List[bytes] = []

        ptr = 0
        while ptr < index_length:
            k_len = struct.unpack(">I", index_data[ptr:ptr + 4])[0]
            ptr += 4
            k_bytes = index_data[ptr:ptr + k_len]
            ptr += k_len
            offset = struct.unpack(">Q", index_data[ptr:ptr + 8])[0]
            ptr += 8
            entry = SparseIndexEntry(key=k_bytes, offset=offset)
            self.sparse_index.append(entry)
            self._sparse_keys.append(k_bytes)

    def get(self, key: bytes) -> Tuple[Optional[Record], bool]:
        """
        Attempts to read a key from this SSTable.
        
        Returns:
            (Record or None, bloom_checked: bool)
        """
        # Step 1: Bloom Filter check - O(k) CPU bit lookups
        if not self.bloom.contains(key):
            # Provably absent; bypass disk I/O entirely!
            return None, True

        # Step 2: Binary Search over Sparse Index - O(log S)
        # Find highest sampled key <= target key
        idx = bisect.bisect_right(self._sparse_keys, key) - 1
        if idx < 0:
            # Key is smaller than the first sampled key in this SSTable
            start_offset = 0
        else:
            start_offset = self.sparse_index[idx].offset

        # Determine end offset boundary for data scan
        if idx + 1 < len(self.sparse_index):
            end_offset = self.sparse_index[idx + 1].offset
        else:
            end_offset = self.index_offset

        # Step 3: Seek to start_offset and scan records within the bounded slice
        self._file.seek(start_offset)
        while self._file.tell() < end_offset:
            rec_header = self._file.read(17)
            if len(rec_header) < 17:
                break
            ts, flag, k_len, v_len = struct.unpack(">QBII", rec_header)
            rec_key = self._file.read(k_len)
            rec_val = self._file.read(v_len)

            if rec_key == key:
                record = Record(
                    key=rec_key,
                    value=rec_val,
                    timestamp_ns=ts,
                    is_tombstone=(flag == FLAG_TOMBSTONE)
                )
                return record, True
            elif rec_key > key:
                # Since records are sorted, if we passed key, it does not exist
                break

        return None, True

    def scan(self, start_key: Optional[bytes] = None, end_key: Optional[bytes] = None) -> List[Record]:
        """
        Range scan within this SSTable for keys in [start_key, end_key).
        """
        results: List[Record] = []
        if start_key is not None:
            idx = bisect.bisect_right(self._sparse_keys, start_key) - 1
            start_offset = self.sparse_index[idx].offset if idx >= 0 else 0
        else:
            start_offset = 0

        self._file.seek(start_offset)
        while self._file.tell() < self.index_offset:
            rec_header = self._file.read(17)
            if len(rec_header) < 17:
                break
            ts, flag, k_len, v_len = struct.unpack(">QBII", rec_header)
            rec_key = self._file.read(k_len)
            rec_val = self._file.read(v_len)

            if start_key is not None and rec_key < start_key:
                continue
            if end_key is not None and rec_key >= end_key:
                break

            record = Record(
                key=rec_key,
                value=rec_val,
                timestamp_ns=ts,
                is_tombstone=(flag == FLAG_TOMBSTONE)
            )
            results.append(record)

        return results

    def iter_all(self) -> Generator[Record, None, None]:
        """Sequentially streams all records from the Data Block."""
        self._file.seek(0)
        while self._file.tell() < self.index_offset:
            rec_header = self._file.read(17)
            if len(rec_header) < 17:
                break
            ts, flag, k_len, v_len = struct.unpack(">QBII", rec_header)
            rec_key = self._file.read(k_len)
            rec_val = self._file.read(v_len)
            yield Record(
                key=rec_key,
                value=rec_val,
                timestamp_ns=ts,
                is_tombstone=(flag == FLAG_TOMBSTONE)
            )

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()
