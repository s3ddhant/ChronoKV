"""
ChronoKV: Benchmarking Suite and Metric Amplification Profiler.

Theoretical Metrics:
1. Write Throughput: Operations Per Second (IOPS) and Megabytes/sec (MB/s).
2. Read Latency Percentiles: p50, p90, p95, p99, p99.9 using nanosecond monotonic timing.
3. Write Amplification Factor (WAF):
   WAF = Total Disk Bytes Written (WAL + SSTables + Compactions) / Logical User Payload Bytes Written.
   In standard LSM-Trees, WAF is typically 2x - 10x depending on level branching factor.
4. Space Amplification Factor (SAF):
   SAF = Total Disk Storage Used / Logical Live Uncompressed Data Size.
   Indicates disk overhead from tombstones, duplicate keys, Bloom filters, and sparse indexes.
"""

from __future__ import annotations
import os
import random
import string
import time
from typing import Dict, List
from chronokv.engine import ChronoKV
from chronokv.types import EngineConfig


class BenchmarkSuite:
    """
    Executes standardized I/O performance benchmarks against ChronoKV.
    """
    def __init__(self, data_dir: str = "data_benchmark") -> None:
        self.data_dir = data_dir

    @staticmethod
    def _random_string(length: int = 16) -> str:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def run_suite(
        self,
        num_keys: int = 5000,
        value_size_bytes: int = 128,
        read_sample_size: int = 2000
    ) -> Dict:
        """
        Executes complete benchmark workflow:
        1. Sequential Writes
        2. Random Reads (Latencies p50/p95/p99)
        3. Flush and Compaction
        4. WAF and SAF calculation
        """
        config = EngineConfig(
            data_dir=self.data_dir,
            memtable_size_bytes=64 * 1024,  # Trigger regular flushes
            sparse_index_interval=16,
            bloom_false_positive_rate=0.01,
            wal_sync_on_write=False
        )
        engine = ChronoKV(config)

        # Generate dataset
        payload = "x" * value_size_bytes
        keys = [f"user_{i:07d}".encode("utf-8") for i in range(num_keys)]
        random_keys = list(keys)
        random.shuffle(random_keys)

        total_user_bytes_written = sum(len(k) + len(payload) for k in keys)

        # -------------------------------------------------------------
        # 1. Sequential Write Benchmark
        # -------------------------------------------------------------
        start_write_ns = time.perf_counter_ns()
        for k in keys:
            engine.put(k, payload)
        end_write_ns = time.perf_counter_ns()

        write_duration_sec = (end_write_ns - start_write_ns) / 1e9
        write_iops = num_keys / max(1e-6, write_duration_sec)
        write_mb_per_sec = (total_user_bytes_written / (1024 * 1024)) / max(1e-6, write_duration_sec)

        # -------------------------------------------------------------
        # 2. Point Lookup Read Benchmark (Latencies)
        # -------------------------------------------------------------
        latencies_ns: List[int] = []
        hits = 0
        read_queries = random_keys[:read_sample_size]

        start_read_ns = time.perf_counter_ns()
        for k in read_queries:
            t0 = time.perf_counter_ns()
            val = engine.get(k)
            t1 = time.perf_counter_ns()
            latencies_ns.append(t1 - t0)
            if val is not None:
                hits += 1
        end_read_ns = time.perf_counter_ns()

        read_duration_sec = (end_read_ns - start_read_ns) / 1e9
        read_iops = len(read_queries) / max(1e-6, read_duration_sec)

        latencies_ns.sort()
        n = len(latencies_ns)
        p50 = latencies_ns[int(n * 0.50)] / 1000.0   # microseconds
        p90 = latencies_ns[int(n * 0.90)] / 1000.0
        p95 = latencies_ns[int(n * 0.95)] / 1000.0
        p99 = latencies_ns[int(n * 0.99)] / 1000.0
        p999 = latencies_ns[int(n * 0.999)] / 1000.0
        avg_lat = (sum(latencies_ns) / max(1, n)) / 1000.0

        # -------------------------------------------------------------
        # 3. Flushes & Disk Space Calculation
        # -------------------------------------------------------------
        engine.manual_flush()
        time.sleep(0.1)

        stats = engine.get_stats()
        total_disk_bytes = stats["sstable_total_disk_bytes"] + stats["wal_total_bytes"]

        # Calculate WAF and SAF
        waf = total_disk_bytes / max(1, total_user_bytes_written)
        saf = stats["sstable_total_disk_bytes"] / max(1, total_user_bytes_written)

        engine.close()

        # Clean benchmark artifacts
        import shutil
        try:
            shutil.rmtree(self.data_dir, ignore_errors=True)
        except Exception:
            pass

        return {
            "num_keys": num_keys,
            "value_size_bytes": value_size_bytes,
            "write_duration_sec": round(write_duration_sec, 4),
            "write_iops": round(write_iops, 2),
            "write_mb_per_sec": round(write_mb_per_sec, 2),
            "read_sample_size": len(read_queries),
            "read_duration_sec": round(read_duration_sec, 4),
            "read_iops": round(read_iops, 2),
            "read_hit_rate": round(hits / max(1, len(read_queries)), 4),
            "latency_p50_us": round(p50, 2),
            "latency_p90_us": round(p90, 2),
            "latency_p95_us": round(p95, 2),
            "latency_p99_us": round(p99, 2),
            "latency_p999_us": round(p999, 2),
            "latency_avg_us": round(avg_lat, 2),
            "write_amplification_factor": round(waf, 2),
            "space_amplification_factor": round(saf, 2),
            "total_user_bytes": total_user_bytes_written,
            "total_disk_bytes": total_disk_bytes,
        }
