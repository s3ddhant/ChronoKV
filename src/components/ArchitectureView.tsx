import React from 'react';
import { ArrowRight, Layers, HardDrive, Cpu, ShieldCheck, Flame, GitMerge, FileCode, CheckCircle2 } from 'lucide-react';

interface EngineStats {
  active_memtable_size_bytes: number;
  active_memtable_key_count: number;
  immutable_memtables_count: number;
  sstable_count: number;
  sstable_total_disk_bytes: number;
  sstable_total_keys: number;
  wal_files_count: number;
  wal_total_bytes: number;
  total_puts: number;
  total_gets: number;
  total_deletes: number;
  bloom_filter_rejections: number;
  bloom_filter_positives: number;
  sstables: Array<{
    filename: string;
    size_bytes: number;
    key_count: number;
    sparse_samples: number;
    bloom_bits: number;
    bloom_hashes: number;
  }>;
}

interface ArchitectureViewProps {
  stats: EngineStats | null;
  onFlush: () => void;
  onCompact: () => void;
  isLoading: boolean;
}

export const ArchitectureView: React.FC<ArchitectureViewProps> = ({
  stats,
  onFlush,
  onCompact,
  isLoading,
}) => {
  const memtableLimit = 64 * 1024; // 64 KB demo limit
  const activeBytes = stats?.active_memtable_size_bytes || 0;
  const memtablePct = Math.min(100, Math.round((activeBytes / memtableLimit) * 100));

  return (
    <div className="space-y-6">
      {/* Overview Metric Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
          <div className="text-xs text-slate-400">Total Mutations</div>
          <div className="mt-1 text-2xl font-mono font-semibold tabular-nums text-white">
            {((stats?.total_puts || 0) + (stats?.total_deletes || 0)).toLocaleString()}
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-400">
            <span>{stats?.total_puts || 0} PUTs</span>
            <span aria-hidden="true">·</span>
            <span>{stats?.total_deletes || 0} DELs</span>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
          <div className="text-xs text-slate-400">Active In-Memory Keys</div>
          <div className="mt-1 text-2xl font-mono font-semibold tabular-nums text-emerald-400">
            {(stats?.active_memtable_key_count || 0).toLocaleString()}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            {activeBytes.toLocaleString()} bytes in RAM
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
          <div className="text-xs text-slate-400">SSTables on Disk</div>
          <div className="mt-1 text-2xl font-mono font-semibold tabular-nums text-amber-400">
            {stats?.sstable_count || 0}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            {((stats?.sstable_total_disk_bytes || 0) / 1024).toFixed(1)} KB persisted
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
          <div className="text-xs text-slate-400">Bloom Filter Rejections</div>
          <div className="mt-1 text-2xl font-mono font-semibold tabular-nums text-sky-400">
            {(stats?.bloom_filter_rejections || 0).toLocaleString()}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            Zero-seek disk bypasses
          </div>
        </div>
      </div>

      {/* LSM Pipeline Stages */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
          <div>
            <h2 className="text-lg font-semibold text-white">LSM-Tree Storage Pipeline</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Append-only Write-Ahead Log, Concurrent MemTable, Immutable Flush & Multi-Way Compaction
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onFlush}
              disabled={isLoading || (stats?.active_memtable_key_count || 0) === 0}
              className="px-3 py-1.5 text-xs font-medium text-white bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700 rounded-md transition-colors flex items-center gap-1.5"
            >
              <Flame className="w-3.5 h-3.5 text-amber-400" />
              <span>Freeze & Flush to SSTable</span>
            </button>
            <button
              onClick={onCompact}
              disabled={isLoading || (stats?.sstable_count || 0) < 2}
              className="px-3 py-1.5 text-xs font-medium text-white bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700 rounded-md transition-colors flex items-center gap-1.5"
            >
              <GitMerge className="w-3.5 h-3.5 text-sky-400" />
              <span>Compact SSTables (K-Way)</span>
            </button>
          </div>
        </div>

        {/* 4 Pipeline Stages in Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
          {/* Stage 1: WAL */}
          <div className="bg-slate-950/80 border border-slate-800/80 rounded-lg p-4 flex flex-col justify-between relative">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-semibold text-slate-200">1. Binary WAL</span>
                <span className="font-mono text-emerald-400">CRC32 Guarded</span>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs text-slate-300">
                <HardDrive className="w-4 h-4 text-emerald-400 shrink-0" />
                <span className="truncate">Append-Only Disk Log</span>
              </div>
              <p className="mt-2 text-xs text-slate-400 leading-relaxed">
                Every write serializes [CRC32, Timestamp, KeyLen, ValLen, Flag, Payload] with zero in-place mutations.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800/60 text-xs font-mono text-slate-400 flex justify-between">
              <span>Files: {stats?.wal_files_count || 0}</span>
              <span>{stats?.wal_total_bytes || 0} B</span>
            </div>
          </div>

          {/* Stage 2: Active MemTable */}
          <div className="bg-slate-950/80 border border-slate-800/80 rounded-lg p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-semibold text-slate-200">2. Active MemTable</span>
                <span className="font-mono text-amber-400">O(log N) SkipList</span>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs text-slate-300">
                <Cpu className="w-4 h-4 text-amber-400 shrink-0" />
                <span>Concurrent Skip-List (RAM)</span>
              </div>
              <p className="mt-2 text-xs text-slate-400 leading-relaxed">
                Pugh's probabilistic skip lanes with Read-Write lock concurrency. Sorts records in-memory instantly.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800/60 space-y-1.5">
              <div className="flex justify-between text-xs font-mono text-slate-400">
                <span>Threshold: {memtablePct}%</span>
                <span>{activeBytes} / {memtableLimit} B</span>
              </div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-amber-400 h-full transition-all duration-300"
                  style={{ width: `${memtablePct}%` }}
                />
              </div>
            </div>
          </div>

          {/* Stage 3: Immutable MemTable */}
          <div className="bg-slate-950/80 border border-slate-800/80 rounded-lg p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-semibold text-slate-200">3. Immutable Queue</span>
                <span className="font-mono text-indigo-400">Read-Only</span>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs text-slate-300">
                <Layers className="w-4 h-4 text-indigo-400 shrink-0" />
                <span>Frozen SkipLists</span>
              </div>
              <p className="mt-2 text-xs text-slate-400 leading-relaxed">
                Frozen snapshots accepting queries while a dedicated background daemon writes sorted records to an SSTable.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800/60 text-xs font-mono text-slate-400 flex justify-between">
              <span>Pending Flushes</span>
              <span className="text-white font-semibold">{stats?.immutable_memtables_count || 0}</span>
            </div>
          </div>

          {/* Stage 4: SSTables */}
          <div className="bg-slate-950/80 border border-slate-800/80 rounded-lg p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-semibold text-slate-200">4. SSTables (Disk)</span>
                <span className="font-mono text-sky-400">Immutable</span>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs text-slate-300">
                <ShieldCheck className="w-4 h-4 text-sky-400 shrink-0" />
                <span>Data + Index + Bloom + Footer</span>
              </div>
              <p className="mt-2 text-xs text-slate-400 leading-relaxed">
                Sorted byte frames sampled into Sparse Indexes with Bloom Filter checking for bounded disk seek lookups.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800/60 text-xs font-mono text-slate-400 flex justify-between">
              <span>SSTable Count</span>
              <span className="text-sky-400 font-semibold">{stats?.sstable_count || 0} files</span>
            </div>
          </div>
        </div>
      </div>

      {/* SSTable Disk Inventory */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-white">Active SSTable Disk Partitions</h3>
        <p className="text-xs text-slate-400 mt-0.5">
          Level-0 and Compacted SSTables currently mounted and indexed in memory
        </p>

        {(!stats?.sstables || stats.sstables.length === 0) ? (
          <div className="mt-4 py-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-lg">
            No SSTables flushed yet. Write keys and click "Freeze & Flush" or insert {'>'} 64 KB to trigger an automatic flush!
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-medium">
                  <th className="py-2.5 px-3">File Identifier</th>
                  <th className="py-2.5 px-3 text-right">Disk Size</th>
                  <th className="py-2.5 px-3 text-right">Key Count</th>
                  <th className="py-2.5 px-3 text-right">Sparse Samples</th>
                  <th className="py-2.5 px-3 text-right">Bloom Bits</th>
                  <th className="py-2.5 px-3 text-right">Hash Functions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono tabular-nums">
                {stats.sstables.map((sst, i) => (
                  <tr key={sst.filename} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-2.5 px-3 text-slate-200 flex items-center gap-2">
                      <FileCode className="w-3.5 h-3.5 text-sky-400" />
                      <span className="truncate">{sst.filename}</span>
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-300">
                      {(sst.size_bytes / 1024).toFixed(2)} KB
                    </td>
                    <td className="py-2.5 px-3 text-right text-emerald-400 font-medium">
                      {sst.key_count.toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-300">
                      {sst.sparse_samples} (1:{Math.max(1, Math.round(sst.key_count / Math.max(1, sst.sparse_samples)))})
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-300">
                      {sst.bloom_bits.toLocaleString()} bits
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-300">
                      k = {sst.bloom_hashes}
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
