#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');

function arg(name, fallback = '') {
  const prefix = `--${name}=`;
  const found = process.argv.find((item) => item.startsWith(prefix));
  return found ? found.slice(prefix.length) : fallback;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
}

function writeJson(file, data) {
  fs.writeFileSync(path.join(root, file), `${JSON.stringify(data, null, 2)}\n`);
}

function replaceTomlVersion(file, version) {
  const full = path.join(root, file);
  const text = fs.readFileSync(full, 'utf8');
  fs.writeFileSync(full, text.replace(/^version = ".+"/m, `version = "${version}"`));
}

const version = arg('version');
const appEndpoint = arg('app-endpoint');
const pubkey = arg('pubkey');

if (!version || !/^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/.test(version)) {
  throw new Error('Usage: prepare-tauri-release.mjs --version=1.2.3 --app-endpoint=https://.../latest.json --pubkey=...');
}
if (!appEndpoint) throw new Error('--app-endpoint is required');
if (!pubkey) throw new Error('--pubkey is required');

const pkg = readJson('package.json');
pkg.version = version;
writeJson('package.json', pkg);

const tauri = readJson('src-tauri/tauri.conf.json');
tauri.version = version;
writeJson('src-tauri/tauri.conf.json', tauri);

const release = readJson('src-tauri/tauri.release.conf.json');
release.plugins ??= {};
release.plugins.updater ??= {};
release.plugins.updater.pubkey = pubkey;
release.plugins.updater.endpoints = [appEndpoint];
writeJson('src-tauri/tauri.release.conf.json', release);

replaceTomlVersion('src-tauri/Cargo.toml', version);

console.log(`Prepared Tauri release config for ${version}`);
