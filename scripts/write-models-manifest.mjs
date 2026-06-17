#!/usr/bin/env node
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

function arg(name, fallback = '') {
  const prefix = `--${name}=`;
  const found = process.argv.find((item) => item.startsWith(prefix));
  return found ? found.slice(prefix.length) : fallback;
}

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

const version = Number.parseInt(arg('version'), 10);
const repo = arg('repo');
const tag = arg('tag', 'models-latest');
const dir = path.resolve(arg('dir', 'backend/models'));

function readVersion() {
  if (Number.isInteger(version) && version > 0) return version;
  const versionPath = path.join(dir, 'version.json');
  if (!fs.existsSync(versionPath)) {
    throw new Error('--version is required when version.json does not exist');
  }
  const value = Number.parseInt(JSON.parse(fs.readFileSync(versionPath, 'utf8')).version, 10);
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(`${versionPath} must contain a positive integer version`);
  }
  return value;
}

const packageVersion = readVersion();

if (!Number.isInteger(packageVersion) || packageVersion <= 0) {
  throw new Error('--version must be a positive integer');
}
if (!repo) throw new Error('--repo is required, for example latte03/yy-xiangqi');

const files = ['piece_classifier.onnx', 'board_locator.onnx'];
for (const file of files) {
  const full = path.join(dir, file);
  if (!fs.existsSync(full)) throw new Error(`Missing ${full}`);
}

const manifest = {
  version: packageVersion,
  files: files.map((name) => ({
    name,
    url: `https://github.com/${repo}/releases/download/${tag}/${name}`,
    sha256: sha256(path.join(dir, name)),
  })),
};

fs.writeFileSync(path.join(dir, 'models.json'), `${JSON.stringify(manifest, null, 2)}\n`);
fs.writeFileSync(path.join(dir, 'version.json'), `${JSON.stringify({ version: packageVersion }, null, 2)}\n`);

console.log(`Wrote models.json/version.json for model package ${packageVersion}`);
