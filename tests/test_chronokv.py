"""
Comprehensive Unit and Integration Test Suite for ChronoKV.
Covers:
- Module 1: SkipList concurrent operations, RWLock correctness, WAL serialization and CRC32 checks.
- Module 2: Bloom Filter false positive bounds, SSTable binary file format, Sparse Index binary search.
- Module 3: Multi-Way Merge Compaction and tombstone eviction.
- Module 4: Crash recovery consistency.
"""

import os
import shutil
import unittest
import threading
from chronokv.types import EngineConfig, Record
from chronokv.skiplist import SkipList
from chronokv.wal import WALWriter, WALReader
from chronokv.bloom import BloomFilter
from chronokv.sstable import SSTableWriter, SSTableReader
from chronokv.compactor import Compactor
from chronokv.engine import ChronoKV
from chronokv.chaos_test import ChaosCrashHarness


class TestSkipList(unittest.TestCase):
    def test_put_get_scan(self):
        sl = SkipList(max_level=8)
        sl.put(b"alpha", b"val_a")
        sl.put(b"gamma", b"val_g")
        sl.put(b"beta", b"val_b")

        self.assertEqual(sl.get(b"alpha").value, b"val_a")
        self.assertEqual(sl.get(b"beta").value, b"val_b")
        self.assertEqual(sl.get(b"gamma").value, b"val_g")
        self.assertIsNone(sl.get(b"delta"))

        # Scan ordered range
        records = sl.scan(b"alpha", b"gamma")
        keys = [r.key for r in records]
        self.assertEqual(keys, [b"alpha", b"beta"])

    def test_concurrent_access(self):
        sl = SkipList(max_level=12)
        def worker(start, count):
            for i in range(start, start + count):
                sl.put(f"k_{i:04d}".encode(), f"v_{i}".encode())

        threads = [threading.Thread(target=worker, args=(i * 100, 100)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(sl), 400)
        for i in range(400):
            res = sl.get(f"k_{i:04d}".encode())
            self.assertIsNotNone(res)


class TestWAL(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_wal_dir"
        os.makedirs(self.test_dir, exist_ok=True)
        self.wal_path = os.path.join(self.test_dir, "test.wal")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_wal_write_and_recovery(self):
        writer = WALWriter(self.wal_path, sync_on_write=True)
        rec1 = Record(key=b"user1", value=b"data1", timestamp_ns=1000)
        rec2 = Record(key=b"user2", value=b"data2", timestamp_ns=2000, is_tombstone=True)
        writer.append(rec1)
        writer.append(rec2)
        writer.close()

        # Read back
        reader = WALReader(self.wal_path)
        records = [r for r, _ in reader.read_records()]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].key, b"user1")
        self.assertEqual(records[0].value, b"data1")
        self.assertFalse(records[0].is_tombstone)
        self.assertEqual(records[1].key, b"user2")
        self.assertTrue(records[1].is_tombstone)

    def test_corrupt_wal_recovery(self):
        writer = WALWriter(self.wal_path, sync_on_write=True)
        writer.append(Record(key=b"valid1", value=b"val1"))
        writer.close()

        # Append corrupt garbage bytes
        with open(self.wal_path, "ab") as f:
            f.write(b"\x00\x00\x00\x01junk_partial_bytes")

        # Recovery should recover valid1 and cleanly halt at corrupt record
        sl = SkipList()
        recovered = WALReader.recover_into(self.wal_path, sl)
        self.assertEqual(recovered, 1)
        self.assertIsNotNone(sl.get(b"valid1"))


class TestBloomFilter(unittest.TestCase):
    def test_bloom_no_false_negatives(self):
        bf = BloomFilter(expected_elements=1000, false_positive_rate=0.01)
        keys = [f"key_{i}".encode() for i in range(500)]
        for k in keys:
            bf.add(k)

        # Invariant: 0% false negatives
        for k in keys:
            self.assertTrue(bf.contains(k))

        # Check false positive rate on absent keys
        false_positives = 0
        test_absent = 1000
        for i in range(500, 500 + test_absent):
            if bf.contains(f"key_{i}".encode()):
                false_positives += 1

        empirical_fp_rate = false_positives / test_absent
        self.assertLess(empirical_fp_rate, 0.05)  # Well within confidence bounds


class TestSSTable(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_sstable_dir"
        os.makedirs(self.test_dir, exist_ok=True)
        self.sst_path = os.path.join(self.test_dir, "test.sst")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sstable_writer_reader(self):
        records = [
            Record(key=f"k_{i:04d}".encode(), value=f"val_{i}".encode(), timestamp_ns=100 + i)
            for i in range(100)
        ]
        writer = SSTableWriter(self.sst_path, expected_records=len(records), sparse_interval=8)
        writer.write_records(records)

        reader = SSTableReader(self.sst_path)
        self.assertEqual(reader.key_count, 100)

        # Lookup present keys
        rec, _ = reader.get(b"k_0042")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.value, b"val_42")

        # Lookup absent key
        rec_absent, _ = reader.get(b"k_9999")
        self.assertIsNone(rec_absent)

        reader.close()


class TestCompaction(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_compaction_dir"
        os.makedirs(self.test_dir, exist_ok=True)
        self.config = EngineConfig(data_dir=self.test_dir, sparse_index_interval=4)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_k_way_merge_and_tombstone_purge(self):
        p1 = os.path.join(self.test_dir, "s1.sst")
        p2 = os.path.join(self.test_dir, "s2.sst")

        # Table 1: Old values
        w1 = SSTableWriter(p1, 3, sparse_interval=4)
        w1.write_records([
            Record(key=b"k1", value=b"v1_old", timestamp_ns=10),
            Record(key=b"k2", value=b"v2_live", timestamp_ns=10),
            Record(key=b"k3", value=b"v3_old", timestamp_ns=10),
        ])

        # Table 2: New updates and a tombstone
        w2 = SSTableWriter(p2, 2, sparse_interval=4)
        w2.write_records([
            Record(key=b"k1", value=b"v1_NEW", timestamp_ns=20),
            Record(key=b"k3", value=b"", timestamp_ns=25, is_tombstone=True),
        ])

        compactor = Compactor(self.config)
        result = compactor.compact_tables([p1, p2], is_bottom_level=True)
        self.assertIsNotNone(result)
        compacted_path, total_in, total_out = result

        # Read back merged table
        reader = SSTableReader(compacted_path)
        rec_k1, _ = reader.get(b"k1")
        self.assertEqual(rec_k1.value, b"v1_NEW")

        rec_k2, _ = reader.get(b"k2")
        self.assertEqual(rec_k2.value, b"v2_live")

        # k3 was a tombstone on bottom level; must be completely purged!
        rec_k3, _ = reader.get(b"k3")
        self.assertIsNone(rec_k3)
        self.assertEqual(reader.key_count, 2)  # Only k1 and k2 survive
        reader.close()


class TestCrashHarness(unittest.TestCase):
    def test_mini_crash_recovery(self):
        harness = ChaosCrashHarness(data_dir="test_chaos_mini")
        res = harness.run_10k_crash_recovery_test(total_keys=1000)
        self.assertEqual(res["status"], "PASS")
        self.assertTrue(res["all_consistent"])
        self.assertEqual(res["mismatch_count"], 0)


if __name__ == "__main__":
    unittest.main()
