#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const semverPattern = /^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/;

function arg(name, fallback = '') {
  const prefix = `--${name}=`;
  const found = process.argv.find((item) => item.startsWith(prefix));
  return found ? found.slice(prefix.length) : fallback;
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8');
}

function write(file, value) {
  fs.writeFileSync(path.join(root, file), value);
}

function readJson(file) {
  return JSON.parse(read(file));
}

function writeJson(file, data) {
  write(file, `${JSON.stringify(data, null, 2)}\n`);
}

function readVersion() {
  const version = arg('version', read('VERSION').trim());
  if (!semverPattern.test(version)) {
    throw new Error(`Invalid app version "${version}". Expected SemVer like 1.2.3.`);
  }
  return version;
}

function replaceTomlVersion(file, version) {
  const text = read(file);
  const next = text.replace(/^version = ".+"/m, `version = "${version}"`);
  if (next === text) throw new Error(`Could not find version field in ${file}`);
  write(file, next);
}

function currentVersions() {
  return {
    versionFile: read('VERSION').trim(),
    packageJson: readJson('package.json').version,
    tauriConfig: readJson('src-tauri/tauri.conf.json').version,
    cargoToml: read('src-tauri/Cargo.toml').match(/^version = "(.+)"/m)?.[1] ?? '',
  };
}

export function syncVersion(version = readVersion()) {
  write('VERSION', `${version}\n`);

  const pkg = readJson('package.json');
  pkg.version = version;
  writeJson('package.json', pkg);

  const tauri = readJson('src-tauri/tauri.conf.json');
  tauri.version = version;
  writeJson('src-tauri/tauri.conf.json', tauri);

  replaceTomlVersion('src-tauri/Cargo.toml', version);
}

export function checkVersionSync() {
  const versions = currentVersions();
  const unique = new Set(Object.values(versions));
  if (unique.size === 1 && semverPattern.test(versions.versionFile)) {
    console.log(`App version is in sync: ${versions.versionFile}`);
    return;
  }
  console.error('App version mismatch:');
  for (const [file, version] of Object.entries(versions)) {
    console.error(`  ${file}: ${version || '<missing>'}`);
  }
  process.exit(1);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  if (hasFlag('check')) {
    checkVersionSync();
  } else {
    const version = readVersion();
    syncVersion(version);
    console.log(`Synced app version: ${version}`);
  }
}
