#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { syncVersion } from './sync-version.mjs';

const root = path.resolve(import.meta.dirname, '..');

function arg(name, fallback = '') {
  const prefix = `--${name}=`;
  const found = process.argv.find((item) => item.startsWith(prefix));
  return found ? found.slice(prefix.length) : fallback;
}

function writeJson(file, data) {
  fs.writeFileSync(path.join(root, file), `${JSON.stringify(data, null, 2)}\n`);
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
}

const version = arg('version', fs.readFileSync(path.join(root, 'VERSION'), 'utf8').trim());
const appEndpoint = arg('app-endpoint');
const pubkey = arg('pubkey');

if (!version || !/^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/.test(version)) {
  throw new Error('Usage: prepare-tauri-release.mjs --version=1.2.3 --app-endpoint=https://.../latest.json --pubkey=...');
}
if (!appEndpoint) throw new Error('--app-endpoint is required');
if (!pubkey) throw new Error('--pubkey is required');

syncVersion(version);

const release = readJson('src-tauri/tauri.release.conf.json');
release.plugins ??= {};
release.plugins.updater ??= {};
release.plugins.updater.pubkey = pubkey;
release.plugins.updater.endpoints = [appEndpoint];
writeJson('src-tauri/tauri.release.conf.json', release);

console.log(`Prepared Tauri release config for ${version}`);
