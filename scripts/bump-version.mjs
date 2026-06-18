#!/usr/bin/env node
/**
 * 版本升级脚本。
 *
 * App 版本（SemVer，单一来源 VERSION，再同步到 package.json / tauri.conf.json / Cargo.toml）:
 *   node scripts/bump-version.mjs patch            # 0.1.0 -> 0.1.1
 *   node scripts/bump-version.mjs minor            # 0.1.0 -> 0.2.0
 *   node scripts/bump-version.mjs major            # 0.1.0 -> 1.0.0
 *   node scripts/bump-version.mjs 1.2.3            # 指定版本
 *   node scripts/bump-version.mjs 1.2.3-beta.1     # 预发布
 *
 * 模型版本（整数，backend/models/version.json，App 内模型更新用）:
 *   node scripts/bump-version.mjs --model          # version + 1
 *   node scripts/bump-version.mjs --model=5        # 指定整数版本
 *
 * 选项:
 *   --commit   写完后 git add 改动文件并提交
 *   --tag      创建 git tag（App: v<x.y.z>；模型: models-v<n>），隐含 --commit
 *   --dry      只打印将要做的改动，不写文件、不动 git
 *   -h, --help 帮助
 */
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { syncVersion } from './sync-version.mjs';

const root = path.resolve(import.meta.dirname, '..');
const semverPattern = /^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/;

const argv = process.argv.slice(2);
const hasFlag = (name) => argv.includes(`--${name}`);
const flagValue = (name) => {
  const hit = argv.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.slice(name.length + 3) : undefined;
};
const positionals = argv.filter((a) => !a.startsWith('-'));

if (hasFlag('help') || argv.includes('-h')) {
  printHelp();
  process.exit(0);
}

const isModel = hasFlag('model') || flagValue('model') !== undefined;
const dry = hasFlag('dry');
const doTag = hasFlag('tag');
const doCommit = hasFlag('commit') || doTag;

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8');
}
function write(file, value) {
  fs.writeFileSync(path.join(root, file), value);
}

function git(args) {
  return execFileSync('git', args, { cwd: root, stdio: 'pipe' }).toString().trim();
}

function ensureCleanTree() {
  const status = git(['status', '--porcelain']);
  if (status) {
    throw new Error(
      '工作区有未提交改动，--commit/--tag 前请先提交或暂存。\n' + status,
    );
  }
}

function commitAndTag(files, message, tag) {
  if (dry) {
    console.log(`[dry] git add ${files.join(' ')}`);
    console.log(`[dry] git commit -m "${message}"`);
    if (tag) console.log(`[dry] git tag ${tag}`);
    return;
  }
  git(['add', ...files]);
  git(['commit', '-m', message]);
  console.log(`✓ 已提交: ${message}`);
  if (tag) {
    git(['tag', tag]);
    console.log(`✓ 已打标签: ${tag}（推送: git push origin ${tag}）`);
  }
}

function bumpApp() {
  const bump = positionals[0];
  if (!bump) {
    throw new Error('请提供 patch | minor | major | 具体版本号。用 --help 查看用法。');
  }
  const current = read('VERSION').trim();
  const next = nextAppVersion(current, bump);
  console.log(`App 版本: ${current} -> ${next}`);

  if (dry) {
    console.log('[dry] 同步到 VERSION / package.json / tauri.conf.json / Cargo.toml');
  } else {
    syncVersion(next);
    console.log('✓ 已同步到 VERSION / package.json / tauri.conf.json / Cargo.toml');
  }

  if (doCommit) {
    const files = ['VERSION', 'package.json', 'src-tauri/tauri.conf.json', 'src-tauri/Cargo.toml'];
    commitAndTag(files, `chore(release): v${next}`, doTag ? `v${next}` : undefined);
  }
  return next;
}

function nextAppVersion(current, bump) {
  if (semverPattern.test(bump)) return bump;
  const m = current.match(/^(\d+)\.(\d+)\.(\d+)/);
  if (!m) throw new Error(`当前 VERSION 非法: "${current}"`);
  let [major, minor, patch] = [Number(m[1]), Number(m[2]), Number(m[3])];
  switch (bump) {
    case 'major':
      major += 1;
      minor = 0;
      patch = 0;
      break;
    case 'minor':
      minor += 1;
      patch = 0;
      break;
    case 'patch':
      patch += 1;
      break;
    default:
      throw new Error(`无法识别的版本参数 "${bump}"。用 patch|minor|major 或 x.y.z。`);
  }
  return `${major}.${minor}.${patch}`;
}

function bumpModel() {
  const file = 'backend/models/version.json';
  const data = JSON.parse(read(file));
  const explicit = flagValue('model');
  const current = Number(data.version);
  if (!Number.isInteger(current)) {
    throw new Error(`${file} 中 version 非整数: ${data.version}`);
  }
  const next = explicit !== undefined ? Number(explicit) : current + 1;
  if (!Number.isInteger(next) || next <= 0) {
    throw new Error(`模型版本必须为正整数，得到: ${explicit}`);
  }
  console.log(`模型版本: ${current} -> ${next}`);

  if (dry) {
    console.log(`[dry] 写入 ${file}`);
  } else {
    data.version = next;
    write(file, `${JSON.stringify(data, null, 2)}\n`);
    console.log(`✓ 已写入 ${file}`);
  }

  if (doCommit) {
    commitAndTag([file], `chore(models): v${next}`, doTag ? `models-v${next}` : undefined);
  }
  return next;
}

function printHelp() {
  console.log(
    [
      '版本升级脚本',
      '',
      'App 版本:',
      '  node scripts/bump-version.mjs patch|minor|major',
      '  node scripts/bump-version.mjs 1.2.3',
      '',
      '模型版本(整数):',
      '  node scripts/bump-version.mjs --model        # +1',
      '  node scripts/bump-version.mjs --model=5      # 指定',
      '',
      '选项: --commit  --tag(隐含 --commit)  --dry  --help',
    ].join('\n'),
  );
}

try {
  if (doCommit && !dry) ensureCleanTree();
  if (isModel) bumpModel();
  else bumpApp();
} catch (err) {
  console.error(`✗ ${err instanceof Error ? err.message : err}`);
  process.exit(1);
}
