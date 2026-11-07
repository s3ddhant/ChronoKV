"""
ChronoKV: JSON Bridge for UI Integration and Systems Telemetry.
Provides atomic JSON-serialized access to ChronoKV primitives for the web visualizer.
"""

import sys
import json
import os
import binascii
from chronokv.engine import ChronoKV
from chronokv.types import EngineConfig
from chronokv.benchmark import BenchmarkSuite
from chronokv.chaos_test import ChaosCrashHarness
from chronokv.wal import WALReader
from chronokv.sstable import SSTableReader

DATA_DIR = os.environ.get("CHRONOKV_DATA_DIR", "data_chronokv")
_config = EngineConfig(
    data_dir=DATA_DIR,
    memtable_size_bytes=64 * 1024,  # 64 KB to demonstrate flush quickly in UI
    sparse_index_interval=8,        # Sample every 8 keys
    bloom_false_positive_rate=0.01
)


def get_engine():
    return ChronoKV(_config)


def handle_status():
    engine = get_engine()
    stats = engine.get_stats()
    engine.close()
    return stats


def handle_put(key: str, value: str):
    engine = get_engine()
    engine.put(key, value)
    stats = engine.get_stats()
    engine.close()
    return {"status": "ok", "key": key, "value": value, "stats": stats}


def handle_get(key: str):
    engine = get_engine()
    res = engine.get_with_diagnostics(key)
    engine.close()
    return res


def handle_delete(key: str):
    engine = get_engine()
    engine.delete(key)
    stats = engine.get_stats()
    engine.close()
    return {"status": "ok", "deleted_key": key, "stats": stats}


def handle_scan(start_key: str = "", end_key: str = ""):
    engine = get_engine()
    sk = start_key if start_key else None
    ek = end_key if end_key else None
    records = engine.scan(sk, ek)
    engine.close()
    return [
        {"key": k.decode(errors="replace"), "value": v.decode(errors="replace")}
        for k, v in records
    ]


def handle_flush():
    engine = get_engine()
    flushed_path = engine.manual_flush()
    stats = engine.get_stats()
    engine.close()
    return {"status": "ok", "flushed_path": flushed_path, "stats": stats}


def handle_compact():
    engine = get_engine()
    result = engine.manual_compact()
    stats = engine.get_stats()
    engine.close()
    if result:
        new_path, inp, out = result
        return {"status": "ok", "compacted_path": new_path, "input_keys": inp, "output_keys": out, "stats": stats}
    return {"status": "skipped", "message": "Fewer than 2 SSTables available for compaction", "stats": stats}


def handle_wal_dump():
    import glob
    wal_files = glob.glob(os.path.join(DATA_DIR, "wal_*.wal"))
    wal_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    
    if not wal_files:
        return {"wal_files": [], "active_wal": None, "records": [], "hex_preview": ""}

    active_wal = wal_files[0]
    records = []
    reader = WALReader(active_wal)
    for rec, offset in reader.read_records():
        records.append({
            "offset": offset,
            "key": rec.key.decode(errors="replace"),
            "value": rec.value.decode(errors="replace"),
            "timestamp_ns": rec.timestamp_ns,
            "is_tombstone": rec.is_tombstone,
            "byte_size": rec.byte_size
        })

    # Read up to first 256 bytes for hex display
    hex_preview = ""
    if os.path.exists(active_wal):
        with open(active_wal, "rb") as f:
            chunk = f.read(256)
            hex_preview = binascii.hexlify(chunk, " ").decode("ascii")

    return {
        "wal_files": [os.path.basename(f) for f in wal_files],
        "active_wal": os.path.basename(active_wal),
        "total_records": len(records),
        "records": records[-50:],  # Return recent 50
        "hex_preview": hex_preview,
        "file_size": os.path.getsize(active_wal) if os.path.exists(active_wal) else 0
    }


def handle_sst_inspect():
    import glob
    sst_files = glob.glob(os.path.join(DATA_DIR, "sstable_*.sst"))
    sst_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    tables = []
    for s_path in sst_files:
        try:
            reader = SSTableReader(s_path)
            sparse_samples = [
                {"key": e.key.decode(errors="replace"), "offset": e.offset}
                for e in reader.sparse_index
            ]
            tables.append({
                "filename": os.path.basename(s_path),
                "file_size": reader.file_size,
                "key_count": reader.key_count,
                "sparse_samples": sparse_samples,
                "sparse_index_offset": reader.index_offset,
                "sparse_index_length": reader.index_length,
                "bloom_offset": reader.bloom_offset,
                "bloom_length": reader.bloom_length,
                "bloom_num_bits": reader.bloom.num_bits,
                "bloom_bits_set": reader.bloom.bits_set_count(),
                "bloom_num_hashes": reader.bloom.num_hashes,
                "bloom_fp_rate": round(reader.bloom.current_false_positive_rate(), 4)
            })
            reader.close()
        except Exception as err:
            pass

    return tables


def handle_seed():
    engine = get_engine()
    sample_data = [
        ("user:001:profile", '{"name":"Johannes Kepler","institution":"Uni Tübingen"}'),
        ("user:002:profile", '{"name":"Ada Lovelace","specialization":"Algorithms"}'),
        ("user:003:profile", '{"name":"Carl Friedrich Gauss","field":"Mathematics"}'),
        ("user:004:profile", '{"name":"Emmy Noether","field":"Abstract Algebra"}'),
        ("metrics:storage:wal_sync", '{"policy":"fsync","status":"nominal"}'),
        ("config:bloom_fp_rate", "0.01"),
        ("config:sparse_index_interval", "8"),
        ("status:cluster:node_a", "active"),
        ("status:cluster:node_b", "active"),
    ]
    for k, v in sample_data:
        engine.put(k, v)
    stats = engine.get_stats()
    engine.close()
    return {"status": "ok", "inserted": len(sample_data), "stats": stats}


def handle_benchmark(num_keys: int = 3000):
    suite = BenchmarkSuite(data_dir="data_bench_temp")
    res = suite.run_suite(num_keys=num_keys, value_size_bytes=128, read_sample_size=1000)
    return res


def handle_chaos(keys: int = 10000):
    harness = ChaosCrashHarness(data_dir="data_chaos_temp")
    res = harness.run_10k_crash_recovery_test(total_keys=keys)
    return res


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No command provided"}))
        return

    cmd = sys.argv[1]
    try:
        if cmd == "status":
            result = handle_status()
        elif cmd == "put":
            result = handle_put(sys.argv[2], sys.argv[3])
        elif cmd == "get":
            result = handle_get(sys.argv[2])
        elif cmd == "delete":
            result = handle_delete(sys.argv[2])
        elif cmd == "scan":
            sk = sys.argv[2] if len(sys.argv) > 2 else ""
            ek = sys.argv[3] if len(sys.argv) > 3 else ""
            result = handle_scan(sk, ek)
        elif cmd == "flush":
            result = handle_flush()
        elif cmd == "compact":
            result = handle_compact()
        elif cmd == "wal_dump":
            result = handle_wal_dump()
        elif cmd == "sst_inspect":
            result = handle_sst_inspect()
        elif cmd == "seed":
            result = handle_seed()
        elif cmd == "benchmark":
            keys = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
            result = handle_benchmark(keys)
        elif cmd == "chaos":
            keys = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
            result = handle_chaos(keys)
        else:
            result = {"error": f"Unknown command: {cmd}"}

        print(json.dumps(result))
    except Exception as e:
        import traceback
        print(json.dumps({"error": str(e), "traceback": traceback.format_exc()}))


if __name__ == "__main__":
    main()
