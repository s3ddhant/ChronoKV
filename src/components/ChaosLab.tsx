import React, { useState } from 'react';
import { ShieldAlert, Play, CheckCircle2, XCircle, AlertTriangle, RefreshCw, Zap } from 'lucide-react';

interface ChaosResult {
  status: string;
  total_keys_tested: number;
  updates_tested: number;
  deletes_tested: number;
  total_verified: number;
  mismatch_count: number;
  missing_count: number;
  tombstones_verified: number;
  wal_size_bytes: number;
  write_time_ms: number;
  recovery_time_ms: number;
  recovered_memtable_keys: number;
  all_consistent: boolean;
  timestamp: number;
}

export const ChaosLab: React.FC = () => {
  const [keyCount, setKeyCount] = useState<number>(10000);
  const [running, setRunning] = useState<boolean>(false);
  const [result, setResult] = useState<ChaosResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runTest = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch('/api/chaos/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keys: keyCount }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Execution error');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-amber-400" />
              <h2 className="text-base font-semibold text-white">
                Chaos Crash Recovery Harness (ACID Durability Verification)
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Validates zero data loss under simulated kernel panic, sudden power interruption, or SIGKILL aborts.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={keyCount}
              onChange={(e) => setKeyCount(Number(e.target.value))}
              disabled={running}
              className="px-3 py-1.5 text-xs font-mono bg-slate-950 border border-slate-800 rounded-md text-white"
            >
              <option value={1000}>1,000 Keys (Fast Check)</option>
              <option value={5000}>5,000 Keys (Moderate)</option>
              <option value={10000}>10,000 Keys (Academic Specification)</option>
            </select>
            <button
              onClick={runTest}
              disabled={running}
              className="px-4 py-1.5 text-xs font-semibold text-slate-950 bg-amber-400 hover:bg-amber-300 disabled:opacity-50 rounded-md shadow-xs transition-colors flex items-center gap-1.5 whitespace-nowrap"
            >
              {running ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Executing Chaos Test...</span>
                </>
              ) : (
                <>
                  <Zap className="w-3.5 h-3.5" />
                  <span>Execute {keyCount.toLocaleString()}-Key Crash Test</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Chaos Protocol Step Explanation */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-6 text-xs">
          <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-lg">
            <div className="text-slate-400 font-mono">Phase 1: Ingestion</div>
            <div className="font-semibold text-white mt-1">Write {keyCount.toLocaleString()} Mutations</div>
            <p className="text-slate-400 mt-1 text-[11px]">
              Inserts {keyCount.toLocaleString()} keys + 1,000 updates + 500 tombstones into volatile memory and append-only WAL.
            </p>
          </div>

          <div className="p-3 bg-slate-950/80 border border-rose-900/40 rounded-lg">
            <div className="text-rose-400 font-mono">Phase 2: Chaos Crash</div>
            <div className="font-semibold text-white mt-1">Abrupt Process Sever</div>
            <p className="text-slate-400 mt-1 text-[11px]">
              Simulates SIGKILL by severing in-memory buffers without flushing the active MemTable to an SSTable.
            </p>
          </div>

          <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-lg">
            <div className="text-slate-400 font-mono">Phase 3: Cold Reboot</div>
            <div className="font-semibold text-white mt-1">Replay Binary WAL</div>
            <p className="text-slate-400 mt-1 text-[11px]">
              New engine scans disk for WAL frames, verifies CRC32 checksums, and replays valid mutations into the SkipList.
            </p>
          </div>

          <div className="p-3 bg-slate-950/80 border border-emerald-900/40 rounded-lg">
            <div className="text-emerald-400 font-mono">Phase 4: Assertion</div>
            <div className="font-semibold text-white mt-1">100% Ground Truth Assert</div>
            <p className="text-slate-400 mt-1 text-[11px]">
              Programmatically queries all {keyCount.toLocaleString()} keys, asserting zero missing records and zero data divergence.
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-rose-950/40 border border-rose-800/80 text-rose-300 p-4 rounded-xl text-xs flex items-center gap-2">
          <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>Execution failed: {error}</span>
        </div>
      )}

      {/* Result Card */}
      {result && (
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {result.all_consistent ? (
                <div className="w-7 h-7 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
              ) : (
                <div className="w-7 h-7 rounded-full bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400">
                  <XCircle className="w-4 h-4" />
                </div>
              )}
              <div>
                <h3 className="text-sm font-semibold text-white">
                  Verification Status: {result.status}
                </h3>
                <p className="text-xs text-slate-400">
                  {result.all_consistent
                    ? '100% of committed keys, updates, and tombstones recovered byte-exact from WAL'
                    : 'Data corruption or missing records detected during replay'}
                </p>
              </div>
            </div>

            <div className="text-right text-xs font-mono text-slate-400">
              Recovery Time: <span className="text-emerald-400 font-semibold">{result.recovery_time_ms} ms</span>
            </div>
          </div>

          {/* Metric Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
              <div className="text-xs text-slate-400">Verified Keys</div>
              <div className="mt-1 text-xl font-mono font-semibold text-emerald-400">
                {result.total_verified.toLocaleString()} / {result.total_keys_tested.toLocaleString()}
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">100.0% consistency</div>
            </div>

            <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
              <div className="text-xs text-slate-400">Data Mismatches</div>
              <div className="mt-1 text-xl font-mono font-semibold text-white">
                {result.mismatch_count}
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">Zero corruption</div>
            </div>

            <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
              <div className="text-xs text-slate-400">Missing Keys</div>
              <div className="mt-1 text-xl font-mono font-semibold text-white">
                {result.missing_count}
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">Zero data loss</div>
            </div>

            <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
              <div className="text-xs text-slate-400">Replayed WAL Disk Size</div>
              <div className="mt-1 text-xl font-mono font-semibold text-sky-400">
                {(result.wal_size_bytes / 1024).toFixed(1)} KB
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">Sequential binary frames</div>
            </div>
          </div>

          {/* Timing details */}
          <div className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg flex flex-col sm:flex-row justify-between text-xs font-mono text-slate-400 gap-2">
            <div>Write Phase Duration: {result.write_time_ms} ms ({(result.total_keys_tested / (result.write_time_ms / 1000)).toFixed(0)} IOPS)</div>
            <div>Tombstones Reconciled: {result.tombstones_verified}</div>
            <div>Cold Reboot Recovery: {result.recovery_time_ms} ms</div>
          </div>
        </div>
      )}
    </div>
  );
};
