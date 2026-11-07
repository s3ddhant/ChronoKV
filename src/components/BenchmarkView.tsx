import React, { useState } from 'react';
import { Gauge, Play, RefreshCw, BarChart3, ArrowUpRight, CheckCircle2 } from 'lucide-react';

interface BenchmarkResult {
  num_keys: number;
  value_size_bytes: number;
  write_duration_sec: number;
  write_iops: number;
  write_mb_per_sec: number;
  read_sample_size: number;
  read_duration_sec: number;
  read_iops: number;
  read_hit_rate: number;
  latency_p50_us: number;
  latency_p90_us: number;
  latency_p95_us: number;
  latency_p99_us: number;
  latency_p999_us: number;
  latency_avg_us: number;
  write_amplification_factor: number;
  space_amplification_factor: number;
  total_user_bytes: number;
  total_disk_bytes: number;
}

export const BenchmarkView: React.FC = () => {
  const [numKeys, setNumKeys] = useState<number>(3000);
  const [running, setRunning] = useState<boolean>(false);
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runBenchmark = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch('/api/benchmark/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keys: numKeys }),
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
      {/* Control Card */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Gauge className="w-5 h-5 text-indigo-400" />
              <h2 className="text-base font-semibold text-white">
                ChronoKV Performance Benchmarking Suite
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Quantifies Write IOPS, Read Latency percentiles (p50-p99.9), Write Amplification (WAF), and Space Amplification (SAF).
            </p>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={numKeys}
              onChange={(e) => setNumKeys(Number(e.target.value))}
              disabled={running}
              className="px-3 py-1.5 text-xs font-mono bg-slate-950 border border-slate-800 rounded-md text-white"
            >
              <option value={1000}>1,000 Keys</option>
              <option value={3000}>3,000 Keys (Standard)</option>
              <option value={5000}>5,000 Keys (Intensive)</option>
            </select>
            <button
              onClick={runBenchmark}
              disabled={running}
              className="px-4 py-1.5 text-xs font-semibold text-slate-950 bg-indigo-400 hover:bg-indigo-300 disabled:opacity-50 rounded-md shadow-xs transition-colors flex items-center gap-1.5 whitespace-nowrap"
            >
              {running ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Profiling Engine...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>Execute Benchmark</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-rose-950/40 border border-rose-800 text-rose-300 p-4 rounded-xl text-xs">
          Benchmark error: {error}
        </div>
      )}

      {/* Metrics Results */}
      {result && (
        <div className="space-y-6">
          {/* Main Throughput Strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
              <div className="text-xs text-slate-400">Write Throughput</div>
              <div className="mt-1 text-2xl font-mono font-semibold tabular-nums text-emerald-400">
                {result.write_iops.toLocaleString()} <span className="text-xs font-normal text-slate-400">IOPS</span>
              </div>
              <div className="mt-1 text-xs text-slate-400">
                {result.write_mb_per_sec} MB/s in {result.write_duration_sec}s
              </div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
              <div className="text-xs text-slate-400">Read Throughput</div>
              <div className="mt-1 text-2xl font-mono font-semibold tabular-nums text-sky-400">
                {result.read_iops.toLocaleString()} <span className="text-xs font-normal text-slate-400">IOPS</span>
              </div>
              <div className="mt-1 text-xs text-slate-400">
                {(result.read_hit_rate * 100).toFixed(1)}% hit rate
              </div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
              <div className="text-xs text-slate-400">Write Amplification (WAF)</div>
              <div className="mt-1 text-2xl font-mono font-semibold tabular-nums text-amber-400">
                {result.write_amplification_factor}x
              </div>
              <div className="mt-1 text-xs text-slate-400">
                Disk Bytes / User Bytes
              </div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
              <div className="text-xs text-slate-400">Median Latency (p50)</div>
              <div className="mt-1 text-2xl font-mono font-semibold tabular-nums text-indigo-400">
                {result.latency_p50_us} <span className="text-xs font-normal text-slate-400">µs</span>
              </div>
              <div className="mt-1 text-xs text-slate-400">
                Avg: {result.latency_avg_us} µs
              </div>
            </div>
          </div>

          {/* Read Latency Percentile Distribution */}
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6">
            <h3 className="text-sm font-semibold text-white">
              Point-Lookup Read Latency Percentiles (Monotonic Nanosecond Clock)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Cumulative tail latency distribution across {result.read_sample_size.toLocaleString()} point queries
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-4 text-xs font-mono">
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-slate-400">p50 (Median)</div>
                <div className="text-lg font-semibold text-emerald-400 mt-1">
                  {result.latency_p50_us} µs
                </div>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-slate-400">p90</div>
                <div className="text-lg font-semibold text-emerald-300 mt-1">
                  {result.latency_p90_us} µs
                </div>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-slate-400">p95</div>
                <div className="text-lg font-semibold text-sky-400 mt-1">
                  {result.latency_p95_us} µs
                </div>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-slate-400">p99</div>
                <div className="text-lg font-semibold text-amber-400 mt-1">
                  {result.latency_p99_us} µs
                </div>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-slate-400">p99.9 (Tail)</div>
                <div className="text-lg font-semibold text-rose-400 mt-1">
                  {result.latency_p999_us} µs
                </div>
              </div>
            </div>

            {/* Visual Bar representation */}
            <div className="mt-6 space-y-2 text-xs font-mono">
              {[
                { label: 'p50', val: result.latency_p50_us, color: 'bg-emerald-400' },
                { label: 'p90', val: result.latency_p90_us, color: 'bg-emerald-300' },
                { label: 'p95', val: result.latency_p95_us, color: 'bg-sky-400' },
                { label: 'p99', val: result.latency_p99_us, color: 'bg-amber-400' },
                { label: 'p99.9', val: result.latency_p999_us, color: 'bg-rose-400' },
              ].map((item) => {
                const maxVal = Math.max(1, result.latency_p999_us);
                const widthPct = Math.min(100, Math.max(4, (item.val / maxVal) * 100));
                return (
                  <div key={item.label} className="flex items-center gap-3">
                    <span className="w-12 text-slate-400">{item.label}</span>
                    <div className="flex-1 bg-slate-950 h-3 rounded-full overflow-hidden p-0.5 border border-slate-800">
                      <div
                        className={`${item.color} h-full rounded-full transition-all duration-300`}
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                    <span className="w-20 text-right text-slate-300">{item.val} µs</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
