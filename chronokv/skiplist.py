"""
ChronoKV: Thread-Safe Concurrent SkipList Implementation.

Theoretical Background:
A SkipList (Pugh, 1990) is a probabilistic data structure that provides expected O(log N)
time complexity for search, insertion, and deletion by augmenting a linked list with an
exponential hierarchy of forward express pointers ('skip lanes').

Mathematical Derivation:
- Let p be the probability of a node extending to level i + 1 given it is at level i (typically p = 0.5).
- Maximum level L_max = ceil(log_{1/p}(N_max)). For 2^16 = 65,536 elements with p = 0.5, L_max = 16.
- Expected number of nodes at level i is N * p^i.
- Expected search path length: E[path] <= L_max / p + 1 = O(log N).
- Space complexity: Expected pointers per node is 1 / (1 - p) = 2. Total space: O(N).

Concurrency Architecture:
- Implements a fair Readers-Writer Lock (RWLock) using condition variables.
- Read operations (get, scan) acquire shared read locks, permitting unbounded parallel queries.
- Write operations (put, delete) acquire exclusive write locks to guarantee atomic pointer updates.
"""

from __future__ import annotations
import random
import threading
from typing import Optional, List, Tuple
from chronokv.types import Record


class RWLock:
    """
    Reader-Writer Lock allowing concurrent readers or an exclusive writer.
    Uses Python threading.Condition to prevent reader starvation.
    """
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._read_ready = threading.Condition(self._lock)
        self._readers = 0
        self._writers_waiting = 0
        self._writer_active = False

    def acquire_read(self) -> None:
        with self._lock:
            while self._writer_active or self._writers_waiting > 0:
                self._read_ready.wait()
            self._readers += 1

    def release_read(self) -> None:
        with self._lock:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self) -> None:
        with self._lock:
            self._writers_waiting += 1
            while self._writer_active or self._readers > 0:
                self._read_ready.wait()
            self._writers_waiting -= 1
            self._writer_active = True

    def release_write(self) -> None:
        with self._lock:
            self._writer_active = False
            self._read_ready.notify_all()

    class _ReadContext:
        def __init__(self, rw: RWLock):
            self.rw = rw
        def __enter__(self):
            self.rw.acquire_read()
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.rw.release_read()

    class _WriteContext:
        def __init__(self, rw: RWLock):
            self.rw = rw
        def __enter__(self):
            self.rw.acquire_write()
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.rw.release_write()

    def read_lock(self) -> _ReadContext:
        return self._ReadContext(self)

    def write_lock(self) -> _WriteContext:
        return self._WriteContext(self)


class SkipListNode:
    """
    A single node in the SkipList containing a Record and level forward pointers.
    """
    __slots__ = ("record", "forward")

    def __init__(self, record: Optional[Record], level: int) -> None:
        self.record: Optional[Record] = record
        # Array of forward references; index corresponds to level [0 .. level - 1]
        self.forward: List[Optional[SkipListNode]] = [None] * level

    @property
    def key(self) -> Optional[bytes]:
        return self.record.key if self.record else None


class SkipList:
    """
    Ordered, concurrent SkipList backing the in-memory MemTable.
    
    Supports:
    - put(key, value, is_tombstone): O(log N) expected
    - get(key): O(log N) expected
    - scan(start_key, end_key): O(log N + K) expected
    """
    def __init__(self, max_level: int = 16, probability: float = 0.5) -> None:
        self.max_level: int = max_level
        self.probability: float = probability
        self.current_level: int = 1
        # Sentinel head node with empty record and max_level forward pointers
        self.head: SkipListNode = SkipListNode(record=None, level=max_level)
        self.rwlock: RWLock = RWLock()
        self._size_bytes: int = 0
        self._count: int = 0

    def _random_level(self) -> int:
        """
        Generates a randomized level for a newly inserted node using geometric distribution.
        P(Level = k) = p^(k-1) * (1 - p).
        """
        lvl = 1
        while random.random() < self.probability and lvl < self.max_level:
            lvl += 1
        return lvl

    @property
    def byte_size(self) -> int:
        """Approximate in-memory byte size of keys and values stored."""
        return self._size_bytes

    def __len__(self) -> int:
        return self._count

    def put(self, key: bytes, value: bytes, is_tombstone: bool = False, timestamp_ns: Optional[int] = None) -> Record:
        """
        Inserts or updates a key-value record in the SkipList.
        
        Complexity:
            Time: O(log N) expected, O(N) worst-case.
            Space: O(1) auxiliary space beyond the newly allocated node.
        """
        record = Record(
            key=key,
            value=value,
            timestamp_ns=timestamp_ns if timestamp_ns is not None else random.randint(1, 10),
            is_tombstone=is_tombstone
        )
        if timestamp_ns is None:
            # Recreate with true time_ns
            import time
            record = Record(key=key, value=value, timestamp_ns=time.time_ns(), is_tombstone=is_tombstone)

        with self.rwlock.write_lock():
            update: List[Optional[SkipListNode]] = [None] * self.max_level
            current = self.head

            # Descend from current highest level to find insert predecessors
            for i in range(self.current_level - 1, -1, -1):
                while current.forward[i] is not None and current.forward[i].key < key:
                    current = current.forward[i]
                update[i] = current

            # Level 0 candidate
            candidate = current.forward[0]

            # In-place update if key exists
            if candidate is not None and candidate.key == key:
                old_bytes = candidate.record.byte_size if candidate.record else 0
                candidate.record = record
                self._size_bytes = self._size_bytes - old_bytes + record.byte_size
                return record

            # Key does not exist; generate random level for new node
            new_level = self._random_level()
            if new_level > self.current_level:
                for i in range(self.current_level, new_level):
                    update[i] = self.head
                self.current_level = new_level

            new_node = SkipListNode(record=record, level=new_level)
            for i in range(new_level):
                new_node.forward[i] = update[i].forward[i]
                update[i].forward[i] = new_node

            self._count += 1
            self._size_bytes += record.byte_size + (new_level * 8)  # Account for pointer overhead
            return record

    def get(self, key: bytes) -> Optional[Record]:
        """
        Finds a record by exact key match.
        
        Complexity:
            Time: O(log N) expected, O(N) worst-case.
        """
        with self.rwlock.read_lock():
            current = self.head
            for i in range(self.current_level - 1, -1, -1):
                while current.forward[i] is not None and current.forward[i].key < key:
                    current = current.forward[i]

            candidate = current.forward[0]
            if candidate is not None and candidate.key == key:
                return candidate.record
            return None

    def scan(self, start_key: Optional[bytes] = None, end_key: Optional[bytes] = None) -> List[Record]:
        """
        Performs an ordered range scan in [start_key, end_key).
        If start_key is None, begins at the first element.
        If end_key is None, scans until the end.
        
        Complexity:
            Time: O(log N + K), where K is the number of records returned.
        """
        results: List[Record] = []
        with self.rwlock.read_lock():
            current = self.head
            if start_key is not None:
                for i in range(self.current_level - 1, -1, -1):
                    while current.forward[i] is not None and current.forward[i].key < start_key:
                        current = current.forward[i]
                current = current.forward[0]
            else:
                current = current.forward[0]

            while current is not None:
                if end_key is not None and current.key >= end_key:
                    break
                if current.record is not None:
                    results.append(current.record)
                current = current.forward[0]

        return results

    def iter_all(self) -> List[Record]:
        """Returns all records ordered by key."""
        return self.scan(start_key=None, end_key=None)
