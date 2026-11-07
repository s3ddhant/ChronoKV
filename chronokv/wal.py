"""
ChronoKV: Binary Write-Ahead Log (WAL) with CRC32 Integrity Checks.

Architectural Purpose:
Provides durability (the 'D' in ACID) for the in-memory MemTable. Every write (PUT / DELETE)
must append a serialized binary record to disk and optionally fsync prior to modifying the
in-memory SkipList.

Binary Record Format:
+-------------------+--------------------+------------------+------------------+---------------+--------------+----------------+
| CRC32 (4 Bytes)   | Timestamp (8 Bytes)| Key Size (4 B)   | Val Size (4 B)   | Flag (1 Byte) | Key (N B)    | Value (M B)    |
| uint32, big-endian| uint64, big-endian | uint32, big-endian| uint32, big-end | uint8 (0/1)   | raw bytes    | raw bytes      |
+-------------------+--------------------+------------------+------------------+---------------+--------------+----------------+
Total Header Size = 21 Bytes.

Integrity Invariants:
1. CRC32 Checksum protects [Timestamp | Key Size | Val Size | Flag | Key | Value].
2. Crash resilience: Incomplete tail writes during sudden power loss or SIGKILL are detected
   via CRC32 mismatch or EOF and safely truncated.
"""

from __future__ import annotations
import os
import struct
import zlib
from typing import Generator, Optional, Tuple, List
from chronokv.types import (
    Record,
    WAL_HEADER_SIZE_BYTES,
    FLAG_PUT,
    FLAG_TOMBSTONE,
)


class WALWriter:
    """
    Append-only binary writer for the Write-Ahead Log.
    """
    def __init__(self, filepath: str, sync_on_write: bool = False) -> None:
        self.filepath: str = filepath
        self.sync_on_write: bool = sync_on_write
        # Open in append binary mode
        os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
        self._file = open(filepath, "a+b")
        self._records_written: int = 0
        self._bytes_written: int = 0

    def append(self, record: Record) -> int:
        """
        Appends a record to the WAL.
        
        Complexity:
            Time: O(K + V) to serialize and write bytes. Disk I/O is append-only sequential.
        
        Returns:
            Total bytes written for this record.
        """
        key_bytes = record.key
        val_bytes = record.value
        k_len = len(key_bytes)
        v_len = len(val_bytes)
        flag = FLAG_TOMBSTONE if record.is_tombstone else FLAG_PUT

        # Pack payload metadata: Timestamp (8B), KeyLen (4B), ValLen (4B), Flag (1B)
        payload_header = struct.pack(">QIIB", record.timestamp_ns, k_len, v_len, flag)
        
        # CRC32 is calculated over: [payload_header + key_bytes + val_bytes]
        crc_data = payload_header + key_bytes + val_bytes
        crc32_checksum = zlib.crc32(crc_data) & 0xFFFFFFFF

        # Complete frame: CRC (4B) + payload_header (17B) + key_bytes + val_bytes
        frame = struct.pack(">I", crc32_checksum) + payload_header + key_bytes + val_bytes

        self._file.write(frame)
        if self.sync_on_write:
            self.sync()

        bytes_count = len(frame)
        self._bytes_written += bytes_count
        self._records_written += 1
        return bytes_count

    def flush(self) -> None:
        """Flushes user-space buffers to OS page cache."""
        self._file.flush()

    def sync(self) -> None:
        """Forces dirty OS page cache pages to physical non-volatile storage (fsync)."""
        self._file.flush()
        os.fsync(self._file.fileno())

    def close(self) -> None:
        if not self._file.closed:
            self.sync()
            self._file.close()

    @property
    def file_size(self) -> int:
        self._file.flush()
        return os.path.getsize(self.filepath)


class WALReader:
    """
    Sequential reader and recovery parser for ChronoKV WAL files.
    """
    def __init__(self, filepath: str) -> None:
        self.filepath: str = filepath

    def read_records(self) -> Generator[Tuple[Record, int], None, None]:
        """
        Iterates through the WAL, validating CRC32 for each record.
        
        Yields:
            (Record, byte_offset)
        
        Stops immediately upon encountering EOF or a corrupt/truncated tail record.
        """
        if not os.path.exists(self.filepath):
            return

        with open(self.filepath, "rb") as f:
            offset = 0
            while True:
                header_bytes = f.read(WAL_HEADER_SIZE_BYTES)
                if not header_bytes:
                    break  # Clean EOF

                if len(header_bytes) < WAL_HEADER_SIZE_BYTES:
                    # Truncated record header due to abrupt system shutdown
                    break

                stored_crc, ts, k_len, v_len, flag = struct.unpack(">IQIIB", header_bytes)
                
                # Sanity guard on sizes to prevent memory allocation faults on corrupted bytes
                if k_len > 64 * 1024 * 1024 or v_len > 256 * 1024 * 1024:
                    # Unrealistic size, indicates corrupted boundary
                    break

                payload_bytes = f.read(k_len + v_len)
                if len(payload_bytes) < (k_len + v_len):
                    # Truncated payload due to mid-write crash
                    break

                key_bytes = payload_bytes[:k_len]
                val_bytes = payload_bytes[k_len:]

                # Verify CRC32
                payload_header = struct.pack(">QIIB", ts, k_len, v_len, flag)
                expected_crc = zlib.crc32(payload_header + key_bytes + val_bytes) & 0xFFFFFFFF

                if stored_crc != expected_crc:
                    # Corrupted record detected! Halt recovery at last consistent checkpoint
                    break

                record = Record(
                    key=key_bytes,
                    value=val_bytes,
                    timestamp_ns=ts,
                    is_tombstone=(flag == FLAG_TOMBSTONE)
                )
                yield record, offset
                offset = f.tell()

    @classmethod
    def recover_into(cls, filepath: str, skiplist) -> int:
        """
        Replays all valid WAL records into a SkipList on cold restart.
        
        Returns:
            Number of successfully recovered records.
        """
        reader = cls(filepath)
        count = 0
        for record, _ in reader.read_records():
            skiplist.put(
                key=record.key,
                value=record.value,
                is_tombstone=record.is_tombstone,
                timestamp_ns=record.timestamp_ns
            )
            count += 1
        return count
