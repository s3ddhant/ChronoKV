import React, { useEffect, useState } from 'react';
import { ShieldCheck, HardDrive, Binary, Search, RefreshCw, FileText, CornerDownRight } from 'lucide-react';

interface SparseSample {
  key: string;
  offset: number;
}

interface SSTableDetail {
  filename: string;
  file_size: number;
  key_count: number;
  sparse_samples: SparseSample[];
  sparse_index_offset: number;
  sparse_index_length: number;
  bloom_offset: number;
  bloom_length: number;
  bloom_num_bits: number;
  bloom_bits_set: number;
  bloom_num_hashes: number;
  bloom_fp_rate: number;
}

export const SSTableInspector: React.FC = () => {
  const [tables, setTables] = useState<SSTableDetail[]>([]);
  const [selectedIdx, setSelectedIdx] = useState<number>(0);
  const [searchKey, setSearchKey] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  const fetchTables = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/sstable/inspect');
      const data = await res.json();
      setTables(data);
      if (data.length > 0 && selectedIdx >= data.length) {
        setSelectedIdx(0);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTables();
  }, []);

  const activeTable = tables[selectedIdx] || null;

  // Simulate binary search over sparse index
  let searchResult: { lowerIdx: number; startOffset: number; endOffset: number } | null = null;
  if (activeTable && searchKey.trim() && activeTable.sparse_samples.length > 0) {
    const samples = activeTable.sparse_samples;
    let low = -1;
    for (let i = 0; i < samples.length; i++) {
      if (samples[i].key <= searchKey) {
        low = i;
      } else {
        break;
      }
    }
    const startOffset = low >= 0 ? samples[low].offset : 0;
    const endOffset =
      low + 1 < samples.length ? samples[low + 1].offset : activeTable.sparse_index_offset;

    searchResult = {
      lowerIdx: low,
      startOffset,
      endOffset,
    };
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Binary className="w-5 h-5 text-sky-400" />
              <h2 className="text-base font-semibold text-white">
                SSTable Binary File Architecture & Sparse Indexing
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Immutable on-disk format combining sorted Data Blocks, Sparse Key Sampling, and Kirsch-Mitzenmacher Bloom Filters.
            </p>
          </div>
          <button
            onClick={fetchTables}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-medium text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-md transition-colors flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-sky-400' : ''}`} />
            <span>Rescan SSTables</span>
          </button>
        </div>

        {/* SSTable File Selector Tabs */}
        {tables.length > 0 && (
          <div className="mt-5 flex items-center gap-2 overflow-x-auto pb-1">
            {tables.map((t, idx) => (
              <button
                key={t.filename}
                onClick={() => setSelectedIdx(idx)}
                className={`px-3 py-1.5 text-xs font-mono rounded-md border transition-colors whitespace-nowrap ${
                  selectedIdx === idx
                    ? 'bg-sky-950/60 text-sky-300 border-sky-700/80'
                    : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                }`}
              >
                {t.filename} ({(t.file_size / 1024).toFixed(1)} KB)
              </button>
            ))}
          </div>
        )}
      </div>

      {tables.length === 0 ? (
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-12 text-center text-xs text-slate-500">
          No SSTable files on disk. Insert keys in the Console and click "Freeze & Flush" to construct an SSTable.
        </div>
      ) : activeTable ? (
        <div className="space-y-6">
          {/* Binary Disk File Layout Diagram */}
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-2">On-Disk Block Layout</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs font-mono">
              {/* Block 1 */}
              <div className="p-3 bg-slate-950 border border-emerald-800/40 rounded-lg">
                <div className="text-emerald-400 font-bold">1. Data Block</div>
                <div className="text-slate-400 mt-1">Offset: 0 B</div>
                <div className="text-slate-400">Length: {activeTable.sparse_index_offset} B</div>
                <div className="text-[11px] text-slate-400 mt-2">
                  Sorted key-values with record headers [TS: 8B | Flag: 1B | KLen: 4B | VLen: 4B]
                </div>
              </div>

              {/* Block 2 */}
              <div className="p-3 bg-slate-950 border border-indigo-800/40 rounded-lg">
                <div className="text-indigo-400 font-bold">2. Sparse Index Block</div>
                <div className="text-slate-400 mt-1">Offset: {activeTable.sparse_index_offset} B</div>
                <div className="text-slate-400">Length: {activeTable.sparse_index_length} B</div>
                <div className="text-[11px] text-slate-400 mt-2">
                  Sampled boundaries every 8-16 records with byte offsets
                </div>
              </div>

              {/* Block 3 */}
              <div className="p-3 bg-slate-950 border border-sky-800/40 rounded-lg">
                <div className="text-sky-400 font-bold">3. Bloom Filter Block</div>
                <div className="text-slate-400 mt-1">Offset: {activeTable.bloom_offset} B</div>
                <div className="text-slate-400">Length: {activeTable.bloom_length} B</div>
                <div className="text-[11px] text-slate-400 mt-2">
                  {activeTable.bloom_num_bits} bits, {activeTable.bloom_num_hashes} hash functions (FNV-1a + CRC32)
                </div>
              </div>

              {/* Block 4 */}
              <div className="p-3 bg-slate-950 border border-amber-800/40 rounded-lg">
                <div className="text-amber-400 font-bold">4. Fixed Footer (44 B)</div>
                <div className="text-slate-400 mt-1">Offset: {activeTable.file_size - 44} B</div>
                <div className="text-slate-400">Magic: b"CKVSST01"</div>
                <div className="text-[11px] text-slate-400 mt-2">
                  Fixed metadata table: Index Offset/Len, Bloom Offset/Len, Key Count
                </div>
              </div>
            </div>
          </div>

          {/* Interactive Sparse Index Binary Search Simulator */}
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white">
              Sparse Index Binary Search Simulator (O(log S))
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Enter any search key to visualize how in-memory binary search isolates the exact disk block byte range
            </p>

            <div className="mt-4 flex gap-2">
              <input
                type="text"
                value={searchKey}
                onChange={(e) => setSearchKey(e.target.value)}
                placeholder="Type target key to simulate binary search (e.g. user:002)"
                className="flex-1 px-3 py-2 text-xs font-mono bg-slate-950 border border-slate-800 rounded-md text-white focus:outline-hidden focus:border-sky-500"
              />
            </div>

            {searchResult && (
              <div className="mt-3 p-3.5 bg-sky-950/30 border border-sky-800/60 rounded-lg text-xs font-mono text-sky-200">
                <div className="font-semibold text-sky-300">Binary Search Result:</div>
                <div className="mt-1">
                  Matched Sparse Boundary Sample:{' '}
                  <span className="text-emerald-400">
                    {searchResult.lowerIdx >= 0
                      ? activeTable.sparse_samples[searchResult.lowerIdx].key
                      : '[Before First Sample]'}
                  </span>
                </div>
                <div>
                  Disk Seek Window: [{searchResult.startOffset} B .. {searchResult.endOffset} B] (
                  {searchResult.endOffset - searchResult.startOffset} bytes to read)
                </div>
                <div className="text-slate-400 mt-1 text-[11px]">
                  Disk I/O savings: Read {searchResult.endOffset - searchResult.startOffset} bytes instead of loading entire {activeTable.file_size} byte file!
                </div>
              </div>
            )}

            {/* Sparse Index Sample Table */}
            <div className="mt-4 border border-slate-800 rounded-lg overflow-hidden">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-950 text-slate-400 font-medium">
                  <tr className="border-b border-slate-800">
                    <th className="py-2 px-3">Sample Index</th>
                    <th className="py-2 px-3">Boundary Key Sample</th>
                    <th className="py-2 px-3 text-right">Disk Byte Offset</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono tabular-nums">
                  {activeTable.sparse_samples.map((s, i) => (
                    <tr
                      key={i}
                      className={
                        searchResult && searchResult.lowerIdx === i
                          ? 'bg-sky-900/30 text-sky-200'
                          : 'hover:bg-slate-800/40'
                      }
                    >
                      <td className="py-2 px-3 text-slate-400">Sample #{i}</td>
                      <td className="py-2 px-3 text-slate-200 font-medium">{s.key}</td>
                      <td className="py-2 px-3 text-right text-emerald-400">+{s.offset} B</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Bloom Filter Mathematical Analysis */}
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white">Bloom Filter Bitarray Analysis</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-3">
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-xs text-slate-400">Total Filter Bits (m)</div>
                <div className="mt-1 text-lg font-mono font-semibold text-sky-400">
                  {activeTable.bloom_num_bits} bits
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">{(activeTable.bloom_num_bits / 8).toFixed(0)} bytes in RAM</div>
              </div>
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-xs text-slate-400">Hash Functions (k)</div>
                <div className="mt-1 text-lg font-mono font-semibold text-indigo-400">
                  {activeTable.bloom_num_hashes}
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">k = (m/n) * ln(2)</div>
              </div>
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-xs text-slate-400">Bits Set to 1</div>
                <div className="mt-1 text-lg font-mono font-semibold text-emerald-400">
                  {activeTable.bloom_bits_set} / {activeTable.bloom_num_bits}
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">
                  {((activeTable.bloom_bits_set / activeTable.bloom_num_bits) * 100).toFixed(1)}% fill factor
                </div>
              </div>
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-xs text-slate-400">False-Positive Rate</div>
                <div className="mt-1 text-lg font-mono font-semibold text-amber-400">
                  {(activeTable.bloom_fp_rate * 100).toFixed(2)}%
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">Zero false negatives</div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};
