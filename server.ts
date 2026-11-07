import express from 'express';
import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import fs from 'fs';
import { createServer as createViteServer } from 'vite';

const execFileAsync = promisify(execFile);
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// Helper to run python bridge commands
async function runBridgeCommand(args: string[]): Promise<any> {
  try {
    const { stdout } = await execFileAsync('python3', ['-m', 'chronokv.bridge', ...args], {
      cwd: process.cwd(),
      timeout: 30000,
    });
    return JSON.parse(stdout.trim());
  } catch (err: any) {
    console.error('Bridge execution error:', err);
    throw new Error(err.stderr || err.message || 'Execution error');
  }
}

// -------------------------------------------------------------
// REST API Endpoints
// -------------------------------------------------------------

// Engine status and metrics
app.get('/api/status', async (_req, res) => {
  try {
    const data = await runBridgeCommand(['status']);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Key-Value operations
app.post('/api/kv/put', async (req, res) => {
  const { key, value } = req.body;
  if (!key) return res.status(400).json({ error: 'Key is required' });
  try {
    const data = await runBridgeCommand(['put', String(key), String(value || '')]);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/kv/get', async (req, res) => {
  const key = req.query.key as string;
  if (!key) return res.status(400).json({ error: 'Key is required' });
  try {
    const data = await runBridgeCommand(['get', String(key)]);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.delete('/api/kv/delete', async (req, res) => {
  const { key } = req.body;
  if (!key) return res.status(400).json({ error: 'Key is required' });
  try {
    const data = await runBridgeCommand(['delete', String(key)]);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/kv/scan', async (req, res) => {
  const startKey = (req.query.start as string) || '';
  const endKey = (req.query.end as string) || '';
  try {
    const data = await runBridgeCommand(['scan', startKey, endKey]);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/kv/seed', async (_req, res) => {
  try {
    const data = await runBridgeCommand(['seed']);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Lifecycle actions
app.post('/api/flush', async (_req, res) => {
  try {
    const data = await runBridgeCommand(['flush']);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/compact', async (_req, res) => {
  try {
    const data = await runBridgeCommand(['compact']);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Deep disk inspection
app.get('/api/wal/dump', async (_req, res) => {
  try {
    const data = await runBridgeCommand(['wal_dump']);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/sstable/inspect', async (_req, res) => {
  try {
    const data = await runBridgeCommand(['sst_inspect']);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Performance Benchmark
app.post('/api/benchmark/run', async (req, res) => {
  const keys = req.body.keys || 3000;
  try {
    const data = await runBridgeCommand(['benchmark', String(keys)]);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Chaos Crash Recovery
app.post('/api/chaos/run', async (req, res) => {
  const keys = req.body.keys || 10000;
  try {
    const data = await runBridgeCommand(['chaos', String(keys)]);
    res.json(data);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Academic source code viewer endpoint
app.get('/api/source/:module', async (req, res) => {
  const allowed = [
    'skiplist.py',
    'wal.py',
    'bloom.py',
    'sstable.py',
    'memtable.py',
    'compactor.py',
    'engine.py',
    'benchmark.py',
    'chaos_test.py',
    'types.py',
  ];
  const mod = req.params.module;
  if (!allowed.includes(mod)) {
    return res.status(404).json({ error: 'File not permitted' });
  }

  const filePath = path.join(process.cwd(), 'chronokv', mod);
  if (fs.existsSync(filePath)) {
    const content = fs.readFileSync(filePath, 'utf-8');
    res.json({ filename: mod, code: content });
  } else {
    res.status(404).json({ error: 'File not found' });
  }
});

// -------------------------------------------------------------
// Vite middleware in dev / static in prod
// -------------------------------------------------------------
async function bootstrap() {
  if (process.env.NODE_ENV === 'production' && fs.existsSync(path.resolve(__dirname, 'dist'))) {
    app.use(express.static(path.resolve(__dirname, 'dist')));
    app.get('*', (_req, res) => {
      res.sendFile(path.resolve(__dirname, 'dist', 'index.html'));
    });
  } else {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  }

  app.listen(PORT, () => {
    console.log(`ChronoKV Server listening on http://0.0.0.0:${PORT}`);
  });
}

bootstrap();
