/**
 * ChronoKV: Academic-Grade In-Memory and On-Disk LSM-Tree Storage Engine
 * Research Workbench & Systems Visualizer
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { ArchitectureView } from './components/ArchitectureView';
import { ConsoleView } from './components/ConsoleView';
import { WalInspector } from './components/WalInspector';
import { SSTableInspector } from './components/SSTableInspector';
import { ChaosLab } from './components/ChaosLab';
import { BenchmarkView } from './components/BenchmarkView';
import { PaperCodeView } from './components/PaperCodeView';

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('architecture');
  const [stats, setStats] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch('/api/status');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Failed to fetch engine stats', err);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 4000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const handleSeed = async () => {
    setIsLoading(true);
    try {
      await fetch('/api/kv/seed', { method: 'POST' });
      await fetchStats();
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFlush = async () => {
    setIsLoading(true);
    try {
      await fetch('/api/flush', { method: 'POST' });
      await fetchStats();
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCompact = async () => {
    setIsLoading(true);
    try {
      await fetch('/api/compact', { method: 'POST' });
      await fetchStats();
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePut = async (key: string, value: string) => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/kv/put', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value }),
      });
      if (!res.ok) throw new Error('PUT failed');
      await fetchStats();
    } finally {
      setIsLoading(false);
    }
  };

  const handleGet = async (key: string) => {
    const res = await fetch(`/api/kv/get?key=${encodeURIComponent(key)}`);
    if (!res.ok) throw new Error('GET failed');
    return await res.json();
  };

  const handleDelete = async (key: string) => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/kv/delete', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      });
      if (!res.ok) throw new Error('DELETE failed');
      await fetchStats();
    } finally {
      setIsLoading(false);
    }
  };

  const handleScan = async (start: string, end: string) => {
    const res = await fetch(`/api/kv/scan?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`);
    if (!res.ok) throw new Error('SCAN failed');
    return await res.json();
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col antialiased selection:bg-emerald-500/30 selection:text-emerald-200">
      {/* Top Navigation */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onSeed={handleSeed}
        onRefresh={fetchStats}
        isLoading={isLoading}
      />

      {/* Main Viewport Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8">
        {activeTab === 'architecture' && (
          <ArchitectureView
            stats={stats}
            onFlush={handleFlush}
            onCompact={handleCompact}
            isLoading={isLoading}
          />
        )}

        {activeTab === 'console' && (
          <ConsoleView
            onPut={handlePut}
            onGet={handleGet}
            onDelete={handleDelete}
            onScan={handleScan}
            isLoading={isLoading}
          />
        )}

        {activeTab === 'wal' && <WalInspector />}

        {activeTab === 'sstables' && <SSTableInspector />}

        {activeTab === 'chaos' && <ChaosLab />}

        {activeTab === 'benchmark' && <BenchmarkView />}

        {activeTab === 'paper' && <PaperCodeView />}
      </main>

      {/* Quiet Academic Systems Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 px-6 py-4 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-slate-400">ChronoKV Storage Engine</span>
            <span aria-hidden="true">·</span>
            <span>Project by Siddhant Bhandare</span>
            <span aria-hidden="true">·</span>
            <a
              href="mailto:siddhantbhandare1@gmail.com"
              className="text-slate-400 hover:text-emerald-400 transition-colors"
            >
              siddhantbhandare1@gmail.com
            </a>
            <span aria-hidden="true">·</span>
            <span>Zero Third-Party Dependencies</span>
          </div>
          <div className="flex items-center gap-4 text-slate-400 font-mono text-[11px]">
            <span>Pugh SkipList</span>
            <span aria-hidden="true">/</span>
            <span>Kirsch-Mitzenmacher Bloom</span>
            <span aria-hidden="true">/</span>
            <span>K-Way Compaction</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
