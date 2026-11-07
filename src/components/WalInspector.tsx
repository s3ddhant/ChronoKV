import React, { useEffect, useState } from 'react';
import { ShieldCheck, HardDrive, FileCode, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';

interface WalRecord {
  offset: number;
  key: string;
  value: string;
  timestamp_ns: number;
  is_tombstone: boolean;
  byte_size: number;
}

interface WalDumpData {
  wal_files: string[];
  active_wal: string | null;
  total_records: number;
  records: WalRecord[];
  hex_preview: string;
  file_size: number;
}

export const WalInspector: React.FC = () => {
  const [data, setData] = useState<WalDumpData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchWal = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/wal/dump');
      const json = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWal();
  }, []);

  return (
    <div className="space-y-6">
      {/* Overview Card */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <HardDrive className="w-5 h-5 text-emerald-400" />
              <h2 className="text-base font-semibold text-white">
                Binary Write-Ahead Log (WAL) Inspector
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Append-only sequential binary log guaranteeing ACID durability across power loss and crashes.
            </p>
          </div>
          <button
            onClick={fetchWal}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-medium text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-md transition-colors flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
            <span>Reload WAL Buffer</span>
          </button>
        </div>

        {/* Binary Framing Specification Diagram */}
        <div className="mt-5 p-4 rounded-lg bg-slate-950 border border-slate-800/80">
          <div className="text-xs font-medium text-slate-300 mb-2">
            21-Byte Binary Frame Layout (struct.pack("{'>'}IQIIB", ...)):
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs font-mono text-center">
            <div className="p-2 rounded bg-emerald-950/40 border border-emerald-800/60 text-emerald-300">
              <div className="font-bold">CRC32</div>
              <div className="text-[10px] text-emerald-500/80 mt-0.5">4 Bytes (uint32)</div>
            </div>
            <div className="p-2 rounded bg-indigo-950/40 border border-indigo-800/60 text-indigo-300">
              <div className="font-bold">Timestamp</div>
              <div className="text-[10px] text-indigo-500/80 mt-0.5">8 Bytes (uint64)</div>
            </div>
            <div className="p-2 rounded bg-sky-950/40 border border-sky-800/60 text-sky-300">
              <div className="font-bold">Key Length</div>
              <div className="text-[10px] text-sky-500/80 mt-0.5">4 Bytes (uint32)</div>
            </div>
            <div className="p-2 rounded bg-amber-950/40 border border-amber-800/60 text-amber-300">
              <div className="font-bold">Val Length</div>
              <div className="text-[10px] text-amber-500/80 mt-0.5">4 Bytes (uint32)</div>
            </div>
            <div className="p-2 rounded bg-rose-950/40 border border-rose-800/60 text-rose-300 col-span-2 sm:col-span-1">
              <div className="font-bold">Flag (0x00 / 0x01)</div>
              <div className="text-[10px] text-rose-500/80 mt-0.5">1 Byte (uint8)</div>
            </div>
          </div>
        </div>
      </div>

      {/* Hex Dump Section */}
      {data?.hex_preview && (
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span className="font-semibold text-slate-200">Raw Disk Hex Dump (First 256 Bytes)</span>
            <span className="font-mono text-slate-400">File: {data.active_wal}</span>
          </div>
          <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800 font-mono text-xs text-emerald-400/90 leading-relaxed overflow-x-auto tracking-widest">
            {data.hex_preview}
          </div>
        </div>
      )}

      {/* Decoded Records Table */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-white">Parsed Binary Frames</h3>
            <p className="text-xs text-slate-400">
              CRC32 validated records replayed sequentially during cold boot recovery
            </p>
          </div>
          <div className="text-xs font-mono text-slate-400">
            Total Logged: <span className="text-emerald-400 font-semibold">{data?.total_records || 0}</span>
          </div>
        </div>

        {(!data?.records || data.records.length === 0) ? (
          <div className="py-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-lg">
            No WAL records available. Write a key via the Interactive Console to generate binary frames.
          </div>
        ) : (
          <div className="overflow-x-auto border border-slate-800 rounded-lg">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-950 text-slate-400 font-medium">
                <tr className="border-b border-slate-800">
                  <th className="py-2.5 px-3">Offset (Bytes)</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Timestamp (ns)</th>
                  <th className="py-2.5 px-3">Key</th>
                  <th className="py-2.5 px-3">Value</th>
                  <th className="py-2.5 px-3 text-right">CRC32 Check</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono tabular-nums">
                {data.records.map((r, i) => (
                  <tr key={i} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-2 px-3 text-slate-400">+{r.offset} B</td>
                    <td className="py-2 px-3">
                      {r.is_tombstone ? (
                        <span className="text-rose-400 font-semibold">TOMBSTONE (0x01)</span>
                      ) : (
                        <span className="text-emerald-400 font-semibold">PUT (0x00)</span>
                      )}
                    </td>
                    <td className="py-2 px-3 text-slate-400 text-[11px]">{r.timestamp_ns}</td>
                    <td className="py-2 px-3 text-slate-200 font-medium">{r.key}</td>
                    <td className="py-2 px-3 text-slate-400 truncate max-w-xs">
                      {r.is_tombstone ? '<purged>' : r.value}
                    </td>
                    <td className="py-2 px-3 text-right">
                      <span className="inline-flex items-center gap-1 text-emerald-400 text-xs">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>VALID</span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
