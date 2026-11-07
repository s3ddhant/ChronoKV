import React, { useState } from 'react';
import { Search, Plus, Trash2, ListFilter, CheckCircle, XCircle, ArrowRight, CornerDownRight } from 'lucide-react';

interface ConsoleViewProps {
  onPut: (key: string, value: string) => Promise<void>;
  onGet: (key: string) => Promise<any>;
  onDelete: (key: string) => Promise<void>;
  onScan: (start: string, end: string) => Promise<any[]>;
  isLoading: boolean;
}

export const ConsoleView: React.FC<ConsoleViewProps> = ({
  onPut,
  onGet,
  onDelete,
  onScan,
  isLoading,
}) => {
  const [putKey, setPutKey] = useState('');
  const [putValue, setPutValue] = useState('');
  const [getKey, setGetKey] = useState('');
  const [getResult, setGetResult] = useState<any | null>(null);
  const [deleteKey, setDeleteKey] = useState('');
  const [scanStart, setScanStart] = useState('');
  const [scanEnd, setScanEnd] = useState('');
  const [scanResults, setScanResults] = useState<any[]>([]);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handlePutSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!putKey.trim()) return;
    try {
      await onPut(putKey.trim(), putValue);
      setFeedback(`PUT committed: "${putKey}" -> WAL & Active SkipList`);
      setPutKey('');
      setPutValue('');
      setTimeout(() => setFeedback(null), 3000);
    } catch (err: any) {
      setFeedback(`Error: ${err.message}`);
    }
  };

  const handleGetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!getKey.trim()) return;
    try {
      const res = await onGet(getKey.trim());
      setGetResult(res);
    } catch (err: any) {
      setFeedback(`Error: ${err.message}`);
    }
  };

  const handleDeleteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deleteKey.trim()) return;
    try {
      await onDelete(deleteKey.trim());
      setFeedback(`DELETE tombstone appended for "${deleteKey}"`);
      setDeleteKey('');
      setTimeout(() => setFeedback(null), 3000);
    } catch (err: any) {
      setFeedback(`Error: ${err.message}`);
    }
  };

  const handleScanSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const results = await onScan(scanStart.trim(), scanEnd.trim());
      setScanResults(results);
      setFeedback(`Scan returned ${results.length} active live records`);
      setTimeout(() => setFeedback(null), 3000);
    } catch (err: any) {
      setFeedback(`Error: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast Feedback */}
      {feedback && (
        <div className="bg-slate-900 border border-emerald-500/30 text-emerald-300 px-4 py-2.5 rounded-lg text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {/* Main Operations Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* PUT Card */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <Plus className="w-4 h-4 text-emerald-400" />
            <span>PUT(key, value)</span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Appends binary record to WAL then inserts into concurrent SkipList
          </p>

          <form onSubmit={handlePutSubmit} className="mt-4 space-y-3">
            <div>
              <label className="text-xs font-mono text-slate-400">Key (bytes)</label>
              <input
                type="text"
                value={putKey}
                onChange={(e) => setPutKey(e.target.value)}
                placeholder="e.g. user:482:metadata"
                className="mt-1 w-full px-3 py-2 text-xs font-mono bg-slate-950 border border-slate-800 rounded-md text-white focus:outline-hidden focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="text-xs font-mono text-slate-400">Value (bytes/JSON)</label>
              <textarea
                value={putValue}
                onChange={(e) => setPutValue(e.target.value)}
                placeholder='e.g. {"status": "active", "quota": 1000}'
                rows={2}
                className="mt-1 w-full px-3 py-2 text-xs font-mono bg-slate-950 border border-slate-800 rounded-md text-white focus:outline-hidden focus:border-emerald-500"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || !putKey.trim()}
              className="px-4 py-2 text-xs font-medium text-slate-950 bg-emerald-400 hover:bg-emerald-300 disabled:opacity-50 rounded-md transition-colors"
            >
              Commit Write (Append WAL)
            </button>
          </form>
        </div>

        {/* DELETE Card */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <Trash2 className="w-4 h-4 text-rose-400" />
            <span>DELETE(key) — Tombstone Marker</span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Appends Flag=0x01 Tombstone to WAL. Purged permanently during L0 compaction.
          </p>

          <form onSubmit={handleDeleteSubmit} className="mt-4 space-y-3">
            <div>
              <label className="text-xs font-mono text-slate-400">Target Key</label>
              <input
                type="text"
                value={deleteKey}
                onChange={(e) => setDeleteKey(e.target.value)}
                placeholder="e.g. user:482:metadata"
                className="mt-1 w-full px-3 py-2 text-xs font-mono bg-slate-950 border border-slate-800 rounded-md text-white focus:outline-hidden focus:border-rose-500"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || !deleteKey.trim()}
              className="px-4 py-2 text-xs font-medium text-white bg-rose-600 hover:bg-rose-500 disabled:opacity-50 rounded-md transition-colors"
            >
              Append Tombstone
            </button>
          </form>
        </div>
      </div>

      {/* Point Lookup GET with Diagnostic Trace */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <Search className="w-4 h-4 text-sky-400" />
          <span>GET(key) with Deep Multi-Layer Diagnostic Trace</span>
        </div>
        <p className="text-xs text-slate-400 mt-0.5">
          Inspects Active MemTable {'->'} Immutable Queue {'->'} Bloom Filter {'->'} Sparse Index {'->'} SSTable Disk Block
        </p>

        <form onSubmit={handleGetSubmit} className="mt-4 flex gap-2">
          <input
            type="text"
            value={getKey}
            onChange={(e) => setGetKey(e.target.value)}
            placeholder="Query key (e.g. user:001:profile)"
            className="flex-1 px-3 py-2 text-xs font-mono bg-slate-950 border border-slate-800 rounded-md text-white focus:outline-hidden focus:border-sky-500"
          />
          <button
            type="submit"
            disabled={isLoading || !getKey.trim()}
            className="px-4 py-2 text-xs font-medium text-white bg-sky-600 hover:bg-sky-500 disabled:opacity-50 rounded-md transition-colors"
          >
            Trace Lookup
          </button>
        </form>

        {getResult && (
          <div className="mt-5 space-y-4 pt-4 border-t border-slate-800">
            {/* Value outcome */}
            <div className="flex items-center justify-between bg-slate-950 p-3 rounded-lg border border-slate-800">
              <div className="flex items-center gap-2">
                {getResult.found ? (
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                ) : (
                  <XCircle className="w-4 h-4 text-slate-500" />
                )}
                <span className="text-xs font-semibold text-slate-200">
                  {getResult.found ? 'Key Found' : 'Key Not Found / Tombstoned'}
                </span>
              </div>
              {getResult.found && (
                <div className="text-xs font-mono text-emerald-400 truncate max-w-md">
                  Value: {getResult.value}
                </div>
              )}
            </div>

            {/* Step-by-Step Traversal Trace */}
            <div>
              <div className="text-xs font-medium text-slate-400 mb-2">Diagnostic Execution Steps:</div>
              <div className="space-y-2">
                {getResult.trace?.map((step: any, idx: number) => (
                  <div
                    key={idx}
                    className="flex items-start gap-3 p-2.5 rounded-md bg-slate-950/60 border border-slate-800/80 text-xs font-mono"
                  >
                    <div className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 text-xs shrink-0">
                      {idx + 1}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-300 font-semibold">{step.layer}</span>
                        <span
                          className={`font-semibold ${
                            step.result === 'HIT'
                              ? 'text-emerald-400'
                              : step.result === 'TOMBSTONE'
                              ? 'text-rose-400'
                              : 'text-slate-500'
                          }`}
                        >
                          {step.result}
                        </span>
                      </div>
                      {step.bloom_check && (
                        <div className="text-slate-400 mt-1">
                          Bloom Filter Check: <span className="text-sky-300">{step.bloom_check}</span>
                        </div>
                      )}
                      {step.sparse_index && (
                        <div className="text-slate-400">
                          Sparse Index: <span className="text-slate-300">{step.sparse_index}</span>
                        </div>
                      )}
                      {step.record && (
                        <div className="text-slate-400 mt-1">
                          Timestamp: {step.record.ts} ns · Tombstone: {step.record.tombstone ? 'YES' : 'NO'}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* SCAN Range Query */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <ListFilter className="w-4 h-4 text-indigo-400" />
          <span>SCAN(start_key, end_key) — Ordered Multi-Layer Range Query</span>
        </div>
        <p className="text-xs text-slate-400 mt-0.5">
          Merges in-memory SkipList and SSTable disk iterators, filtering out tombstones
        </p>

        <form onSubmit={handleScanSubmit} className="mt-4 flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={scanStart}
            onChange={(e) => setScanStart(e.target.value)}
            placeholder="Start key (inclusive, empty for all)"
            className="flex-1 px-3 py-2 text-xs font-mono bg-slate-950 border border-slate-800 rounded-md text-white focus:outline-hidden focus:border-indigo-500"
          />
          <input
            type="text"
            value={scanEnd}
            onChange={(e) => setScanEnd(e.target.value)}
            placeholder="End key (exclusive, empty for all)"
            className="flex-1 px-3 py-2 text-xs font-mono bg-slate-950 border border-slate-800 rounded-md text-white focus:outline-hidden focus:border-indigo-500"
          />
          <button
            type="submit"
            disabled={isLoading}
            className="px-4 py-2 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-md transition-colors"
          >
            Execute Range Scan
          </button>
        </form>

        {scanResults.length > 0 && (
          <div className="mt-4 border border-slate-800 rounded-lg overflow-hidden">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-950 text-slate-400">
                <tr className="border-b border-slate-800">
                  <th className="py-2 px-3">Key</th>
                  <th className="py-2 px-3">Value</th>
                  <th className="py-2 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {scanResults.map((r, i) => (
                  <tr key={i} className="hover:bg-slate-800/40">
                    <td className="py-2 px-3 text-emerald-400 font-medium">{r.key}</td>
                    <td className="py-2 px-3 text-slate-300 truncate max-w-xs">{r.value}</td>
                    <td className="py-2 px-3 text-right">
                      <button
                        onClick={() => {
                          setGetKey(r.key);
                          onGet(r.key).then(setGetResult);
                        }}
                        className="text-sky-400 hover:underline mr-3"
                      >
                        Trace
                      </button>
                      <button
                        onClick={() => {
                          onDelete(r.key);
                          setScanResults((prev) => prev.filter((item) => item.key !== r.key));
                        }}
                        className="text-rose-400 hover:underline"
                      >
                        Delete
                      </button>
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
