"""
ChronoKV: Command-Line Interface and Systems Diagnostic Utility.

Usage:
  python3 -m chronokv.cli benchmark [--keys 5000] [--val-size 128]
  python3 -m chronokv.cli chaos [--keys 10000]
  python3 -m chronokv.cli inspect-sst <sstable_path>
  python3 -m chronokv.cli inspect-wal <wal_path>
  python3 -m chronokv.cli repl [--dir data_chronokv]
"""

import argparse
import os
import sys
import json
from chronokv.engine import ChronoKV
from chronokv.types import EngineConfig
from chronokv.benchmark import BenchmarkSuite
from chronokv.chaos_test import ChaosCrashHarness
from chronokv.sstable import SSTableReader
from chronokv.wal import WALReader


def cmd_benchmark(args):
    print("=" * 70)
    print("  ChronoKV LSM-Tree Storage Engine: High-Precision Benchmark Suite")
    print("=" * 70)
    print(f"Parameters: {args.keys} keys | {args.val_size} bytes payload | {args.reads} reads sample\n")

    suite = BenchmarkSuite()
    res = suite.run_suite(num_keys=args.keys, value_size_bytes=args.val_size, read_sample_size=args.reads)

    print(f"Write Throughput:         {res['write_iops']:,.1f} IOPS  ({res['write_mb_per_sec']:.2f} MB/s)")
    print(f"Write Duration:           {res['write_duration_sec']:.4f} s")
    print(f"Read Throughput:          {res['read_iops']:,.1f} IOPS  (Hit Rate: {res['read_hit_rate']*100:.1f}%)")
    print(f"Read Latency p50:         {res['latency_p50_us']:.2f} µs")
    print(f"Read Latency p90:         {res['latency_p90_us']:.2f} µs")
    print(f"Read Latency p95:         {res['latency_p95_us']:.2f} µs")
    print(f"Read Latency p99:         {res['latency_p99_us']:.2f} µs")
    print(f"Read Latency p99.9:       {res['latency_p999_us']:.2f} µs")
    print(f"Average Read Latency:     {res['latency_avg_us']:.2f} µs")
    print("-" * 70)
    print(f"Write Amplification (WAF): {res['write_amplification_factor']:.2f}x")
    print(f"Space Amplification (SAF): {res['space_amplification_factor']:.2f}x")
    print(f"User Payload Bytes:       {res['total_user_bytes']:,} bytes")
    print(f"Total Disk Storage:       {res['total_disk_bytes']:,} bytes")
    print("=" * 70)


def cmd_chaos(args):
    print("=" * 70)
    print("  ChronoKV Chaos Crash Recovery Verification (ACID Durability Test)")
    print("=" * 70)
    print(f"Testing {args.keys:,} keys with abrupt abort & cold reboot...\n")

    harness = ChaosCrashHarness()
    res = harness.run_10k_crash_recovery_test(total_keys=args.keys)

    print(f"Status:                   {res['status']}")
    print(f"Total Keys Tested:        {res['total_keys_tested']:,}")
    print(f"Updates Tested:           {res['updates_tested']:,}")
    print(f"Tombstones Tested:        {res['deletes_tested']:,}")
    print(f"Total Verified Intact:    {res['total_verified']:,}")
    print(f"Mismatches:               {res['mismatch_count']}")
    print(f"Missing:                  {res['missing_count']}")
    print(f"Pre-Crash WAL Disk Size:  {res['wal_size_bytes']:,} bytes")
    print(f"Write Phase Duration:     {res['write_time_ms']:.2f} ms")
    print(f"Recovery Replay Time:     {res['recovery_time_ms']:.2f} ms")
    print(f"All Assertions Passed:    {res['all_consistent']}")
    print("=" * 70)


def cmd_inspect_sst(args):
    if not os.path.exists(args.path):
        print(f"Error: SSTable file not found at {args.path}")
        return

    reader = SSTableReader(args.path)
    print(f"SSTable: {args.path}")
    print(f"File Size:         {reader.file_size:,} bytes")
    print(f"Total Records:     {reader.key_count:,}")
    print(f"Sparse Samples:    {len(reader.sparse_index)}")
    print(f"Index Block:       Offset {reader.index_offset}, Length {reader.index_length} B")
    print(f"Bloom Filter:      Offset {reader.bloom_offset}, Length {reader.bloom_length} B")
    print(f"Bloom Filter Bits: {reader.bloom.num_bits:,} ({reader.bloom.bits_set_count():,} bits set, {reader.bloom.num_hashes} hashes)")
    print("\nFirst 5 Sparse Index Samples:")
    for entry in reader.sparse_index[:5]:
        print(f"  Key: {entry.key!r} -> Offset: {entry.offset} B")
    reader.close()


def cmd_inspect_wal(args):
    if not os.path.exists(args.path):
        print(f"Error: WAL file not found at {args.path}")
        return

    reader = WALReader(args.path)
    print(f"WAL File: {args.path} ({os.path.getsize(args.path):,} bytes)")
    count = 0
    tombstones = 0
    for rec, offset in reader.read_records():
        count += 1
        if rec.is_tombstone:
            tombstones += 1
        if count <= 5:
            print(f"  [{offset:06d}] Key={rec.key!r} (TS={rec.timestamp_ns}, Tombstone={rec.is_tombstone})")

    print(f"\nTotal Valid Records Replayed: {count:,} (Tombstones: {tombstones:,})")


def main():
    parser = argparse.ArgumentParser(description="ChronoKV LSM-Tree Storage Engine CLI")
    subparsers = parser.add_subparsers(dest="command")

    bench_p = subparsers.add_parser("benchmark", help="Run performance benchmarking suite")
    bench_p.add_argument("--keys", type=int, default=5000, help="Number of keys to benchmark")
    bench_p.add_argument("--val-size", type=int, default=128, help="Value size in bytes")
    bench_p.add_argument("--reads", type=int, default=2000, help="Number of read samples")

    chaos_p = subparsers.add_parser("chaos", help="Run chaos crash and recovery harness")
    chaos_p.add_argument("--keys", type=int, default=10000, help="Total keys to write before crash")

    sst_p = subparsers.add_parser("inspect-sst", help="Inspect SSTable binary file layout")
    sst_p.add_argument("path", type=str, help="Path to .sst file")

    wal_p = subparsers.add_parser("inspect-wal", help="Inspect binary WAL file records")
    wal_p.add_argument("path", type=str, help="Path to .wal file")

    args = parser.parse_args()
    if args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "chaos":
        cmd_chaos(args)
    elif args.command == "inspect-sst":
        cmd_inspect_sst(args)
    elif args.command == "inspect-wal":
        cmd_inspect_wal(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
