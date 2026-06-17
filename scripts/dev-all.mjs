#!/usr/bin/env node
/**
 * 并行启动开发环境：前端 Vite + 后端 FastAPI（热重载）。
 * 一个进程退出则一并关闭；Ctrl+C 全部停止。跨平台。
 * 后端优先用 backend/.venv 的 python（没有则回退系统 python）。
 */
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const backend = join(root, 'backend');
const isWin = process.platform === 'win32';

const venvPy = isWin
  ? join(backend, '.venv', 'Scripts', 'python.exe')
  : join(backend, '.venv', 'bin', 'python');
const py = existsSync(venvPy) ? venvPy : isWin ? 'python' : 'python3';

const procs = [];
let shuttingDown = false;

function prefix(tag, buf) {
  return buf
    .toString()
    .split('\n')
    .map((line, i, arr) => (line || i < arr.length - 1 ? tag + line : line))
    .join('\n');
}

function start(name, cmd, args, opts = {}) {
  const tag = `[${name}] `;
  const p = spawn(cmd, args, { stdio: ['inherit', 'pipe', 'pipe'], shell: isWin, ...opts });
  p.stdout.on('data', (d) => process.stdout.write(prefix(tag, d)));
  p.stderr.on('data', (d) => process.stderr.write(prefix(tag, d)));
  p.on('exit', (code) => {
    console.log(`${tag}已退出（code ${code}）`);
    shutdown();
  });
  procs.push(p);
}

function shutdown() {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const p of procs) {
    try {
      p.kill();
    } catch {
      /* ignore */
    }
  }
  process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

start('web', 'pnpm', ['dev']);
start('api', py, ['-m', 'uvicorn', 'app:app', '--reload', '--host', '127.0.0.1', '--port', '8765'], {
  cwd: backend,
});

console.log('开发环境启动中：前端 http://localhost:5173 · 后端 http://127.0.0.1:8765（Ctrl+C 全部停止）');
