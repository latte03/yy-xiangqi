#!/usr/bin/env node
/**
 * 初次 clone 后一键安装依赖：
 *   - 前端：pnpm install
 *   - 后端：创建 backend/.venv 并安装 requirements.txt（推理/运行依赖）
 * 训练依赖（torch 等）按需另装：见末尾提示。
 * 跨平台（macOS / Linux / Windows）。
 */
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const isWin = process.platform === 'win32';
const sysPy = isWin ? 'python' : 'python3';

function run(cmd, args, opts = {}) {
  console.log(`\n▶ ${cmd} ${args.join(' ')}${opts.cwd ? `  (cwd: ${opts.cwd})` : ''}`);
  const r = spawnSync(cmd, args, { stdio: 'inherit', shell: isWin, ...opts });
  if (r.status !== 0) {
    console.error(`\n✗ 失败：${cmd} ${args.join(' ')}`);
    process.exit(r.status ?? 1);
  }
}

// 1) 前端依赖
run('pnpm', ['install']);

// 2) 后端 venv + 依赖
const backend = join(root, 'backend');
const venv = join(backend, '.venv');
if (!existsSync(venv)) {
  run(sysPy, ['-m', 'venv', '.venv'], { cwd: backend });
}
const venvPy = isWin
  ? join(venv, 'Scripts', 'python.exe')
  : join(venv, 'bin', 'python');
run(venvPy, ['-m', 'pip', 'install', '--upgrade', 'pip'], { cwd: backend });
run(venvPy, ['-m', 'pip', 'install', '-r', 'requirements.txt'], { cwd: backend });

console.log('\n✅ 依赖安装完成。');
console.log('   启动开发：pnpm dev:all（同时起前端 + 后端热重载）');
console.log('   仅训练模型时另装：backend/.venv 下 pip install -r requirements-train.txt');
