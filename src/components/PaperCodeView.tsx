import React, { useEffect, useState } from 'react';
import { BookOpen, Code2, Copy, Check, FileCode, CheckCircle2 } from 'lucide-react';

export const PaperCodeView: React.FC = () => {
  const [subTab, setSubTab] = useState<'paper' | 'code'>('paper');
  const [selectedModule, setSelectedModule] = useState<string>('skiplist.py');
  const [codeContent, setCodeContent] = useState<string>('');
  const [copied, setCopied] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);

  const modules = [
    { id: 'skiplist.py', name: 'SkipList (MemTable)', desc: 'Pugh 1990 SkipList with RWLock Concurrency' },
    { id: 'wal.py', name: 'Binary WAL', desc: 'Append-Only Log with CRC32 Checksums' },
    { id: 'bloom.py', name: 'Bloom Filter', desc: 'Kirsch-Mitzenmacher Double-Hashing' },
    { id: 'sstable.py', name: 'SSTable Writer/Reader', desc: 'Data Block, Sparse Index & 44B Footer' },
    { id: 'compactor.py', name: 'K-Way Compactor', desc: 'Multi-Way Merge Sort & Tombstone Purge' },
    { id: 'memtable.py', name: 'MemTable Manager', desc: 'Freeze Lifecycle & Flush Orchestration' },
    { id: 'engine.py', name: 'ChronoKV Engine', desc: 'Unified Engine with Multi-Layer Paths' },
    { id: 'chaos_test.py', name: 'Chaos Crash Harness', desc: '10,000 Keys Abrupt Sever & Recovery' },
    { id: 'benchmark.py', name: 'Benchmark Suite', desc: 'IOPS, p50-p99 Latencies, WAF & SAF' },
    { id: 'types.py', name: 'Types & Constants', desc: 'Dataclasses, Magic Sentinels & Records' },
  ];

  const fetchCode = async (mod: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/source/${mod}`);
      const data = await res.json();
      setCodeContent(data.code || '');
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (subTab === 'code') {
      fetchCode(selectedModule);
    }
  }, [subTab, selectedModule]);

  const handleCopy = () => {
    navigator.clipboard.writeText(codeContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Sub-navigation */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSubTab('paper')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
              subTab === 'paper'
                ? 'bg-slate-800 text-emerald-400 border border-slate-700/80 shadow-xs'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Academic Architecture Report</span>
          </button>
          <button
            onClick={() => setSubTab('code')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
              subTab === 'code'
                ? 'bg-slate-800 text-sky-400 border border-slate-700/80 shadow-xs'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>Python 3.10+ Source Code Explorer</span>
          </button>
        </div>

        {subTab === 'code' && (
          <button
            onClick={handleCopy}
            className="px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-md transition-colors flex items-center gap-1.5"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy Source'}</span>
          </button>
        )}
      </div>

      {subTab === 'paper' ? (
        /* Academic Paper Document */
        <article className="bg-slate-900/40 border border-slate-800 rounded-xl p-8 max-w-4xl mx-auto space-y-8 text-slate-300 leading-relaxed text-sm">
          {/* Header Block */}
          <div className="border-b border-slate-800 pb-6 text-center space-y-2">
            <div className="text-xs font-mono uppercase tracking-widest text-emerald-400">
              Systems Engineering & Distributed Data Structures Portfolio
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              ChronoKV: Design, Concurrency, and Disk I/O Semantics of a Lightweight Log-Structured Merge Storage Engine
            </h1>
            <div className="text-xs text-slate-400 pt-1">
              <span>Project by Siddhant Bhandare</span>
              <span className="mx-2">·</span>
              <a
                href="mailto:siddhantbhandare1@gmail.com"
                className="hover:text-emerald-400 transition-colors"
              >
                siddhantbhandare1@gmail.com
              </a>
              <span className="mx-2">·</span>
              <span>Systems & Distributed Software Engineering</span>
              <span className="mx-2">·</span>
              <span>November 2026</span>
            </div>
          </div>

          {/* Abstract */}
          <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-xs">
            <span className="font-bold text-white uppercase tracking-wider">Abstract — </span>
            In-place update storage systems (e.g. traditional B+ Trees) suffer severe write amplification and disk fragmentation under write-intensive ingestion workloads due to random head seeks and copy-on-write page splits. Log-Structured Merge-Trees (LSM-Trees) resolve this bottleneck by decoupling volatile in-memory staging from append-only disk files. This work presents <em>ChronoKV</em>, a zero-dependency, production-grade key-value storage engine engineered in Python 3.10+. ChronoKV combines a concurrent SkipList MemTable synchronized with a Readers-Writer lock, an IEEE 802.3 CRC32-guarded binary Write-Ahead Log (WAL), Kirsch-Mitzenmacher double-hashed Bloom filters, binary sparse-indexed SSTables, and a $K$-Way merge compactor with tombstone eviction. Under simulated kernel panic and abrupt power severing across 10,000 transactions, the engine guarantees 100% crash consistency and byte-exact state recovery in sub-second time.
          </div>

          {/* Section 1 */}
          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">
              01. Introduction & Theoretical Motivation
            </h2>
            <p>
              Under the Mechanical Sympathy doctrine of systems programming, storage engines must optimize for the physical characteristics of persistent media. Random writes to SSDs trigger internal flash garbage collection cycles, elevating Write Amplification Factors (WAF) to unviable levels. In accordance with O'Neil et al. (1996), ChronoKV models all data mutations (both inserts and deletes) as immutable append-only events.
            </p>
          </section>

          {/* Section 2 */}
          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">
              02. In-Memory SkipList Concurrency
            </h2>
            <p>
              Rather than employing balanced binary search trees (e.g., Red-Black or AVL trees) which require complex global pointer rotations under high lock contention, ChronoKV uses Pugh's (1990) probabilistic SkipList. Each node's height is determined by a geometric distribution:
            </p>
            <div className="bg-slate-950 p-3 rounded-md font-mono text-xs text-emerald-400 text-center">
              P(Level = k) = p^(k-1) * (1 - p), with p = 0.5, L_max = 16
            </div>
            <p>
              Expected search, insertion, and deletion complexity is bounded by O(log N) with expected node pointer overhead E[L] = 1 / (1 - p) = 2. Concurrency is governed by a fair Readers-Writer Lock (RWLock) utilizing Python condition variables, enabling parallel point queries and range scans without reader starvation.
            </p>
          </section>

          {/* Section 3 */}
          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">
              03. Binary Write-Ahead Log (WAL) & Durability Invariants
            </h2>
            <p>
              Durability (the 'D' in ACID) is established by serializing every mutation to an append-only binary log before modifying volatile RAM. The framing layout is strictly 21 bytes:
            </p>
            <div className="bg-slate-950 p-3 rounded-md font-mono text-xs text-sky-300 overflow-x-auto">
              [CRC32: 4B (uint32) | Timestamp_ns: 8B (uint64) | KeyLen: 4B (uint32) | ValLen: 4B (uint32) | Flag: 1B (uint8)]
            </div>
            <p>
              On cold restart, <code>WALReader.recover_into()</code> sequentially parses frames. If an abrupt crash terminates the process mid-write, the truncated tail record triggers a CRC32 mismatch; recovery halts gracefully at the last atomic checkpoint without corrupting previous transactions.
            </p>
          </section>

          {/* Section 4 */}
          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">
              04. Bloom Filter & SSTable Binary Layout
            </h2>
            <p>
              To circumvent the Read Amplification inherent to multi-level LSM architectures, each SSTable incorporates an in-memory Bloom filter. Given $n$ expected keys and target false-positive probability $\epsilon = 0.01$, optimal bitarray size $m$ and hash count $k$ are computed as:
            </p>
            <div className="bg-slate-950 p-3 rounded-md font-mono text-xs text-amber-300 text-center">
              m = - (n * ln(ε)) / (ln 2)^2 ≈ 9.58 * n bits  |  k = (m / n) * ln 2 ≈ 7 hashes
            </div>
            <p>
              Following Kirsch and Mitzenmacher (2006), $k$ hash positions are derived from two base hashes via $g_i(x) = (h_1(x) + i \cdot h_2(x)) \pmod m$, yielding identical asymptotic bounds without the CPU overhead of cryptographic hashes.
            </p>
          </section>

          {/* Section 5 */}
          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">
              05. Multi-Way Merge Compaction & Tombstone Eviction
            </h2>
            <p>
              Compaction reconciles multi-version records across SSTables into a single canonical SSTable using a Min-Heap priority queue in $O(N \log K)$ time. Deletions are represented as tombstone markers; during bottom-level compaction, tombstones are permanently purged from persistent media, reclaiming physical disk sectors.
            </p>
          </section>
        </article>
      ) : (
        /* Code Explorer View */
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {/* Module Selector List */}
          <div className="space-y-1.5 md:col-span-1">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Engine Modules
            </div>
            {modules.map((m) => (
              <button
                key={m.id}
                onClick={() => setSelectedModule(m.id)}
                className={`w-full text-left p-2.5 rounded-lg border transition-colors ${
                  selectedModule === m.id
                    ? 'bg-slate-800 text-white border-slate-700'
                    : 'bg-slate-900/40 text-slate-400 border-slate-800/80 hover:text-slate-200 hover:bg-slate-900'
                }`}
              >
                <div className="text-xs font-mono font-semibold text-emerald-400">{m.id}</div>
                <div className="text-xs text-slate-200 mt-0.5">{m.name}</div>
                <div className="text-[10px] text-slate-400 mt-1 truncate">{m.desc}</div>
              </button>
            ))}
          </div>

          {/* Code Viewer Panel */}
          <div className="md:col-span-3 bg-slate-950 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
            <div className="px-4 py-3 bg-slate-900/60 border-b border-slate-800 flex items-center justify-between text-xs font-mono">
              <span className="text-slate-300">chronokv/{selectedModule}</span>
              <span className="text-slate-500">Python 3.10+ · Zero Dependencies</span>
            </div>
            <pre className="p-4 text-xs font-mono text-emerald-400/95 overflow-x-auto leading-relaxed max-h-[600px] overflow-y-auto">
              {loading ? 'Loading source file...' : codeContent}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
