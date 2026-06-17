#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="${TAURI_TARGET:-$(rustc --print host-tuple)}"
app_endpoint="${APP_UPDATE_ENDPOINT:-https://github.com/latte03/yy-xiangqi/releases/download/app-latest/latest.json}"
pubkey="${TAURI_UPDATER_PUBKEY:-}"

if [[ -z "$pubkey" ]]; then
  echo "TAURI_UPDATER_PUBKEY is required for local release builds." >&2
  echo "Copy scripts/local-release-env.example.sh to scripts/local-release-env.sh, fill it in, then run:" >&2
  echo "  source scripts/local-release-env.sh" >&2
  exit 1
fi

if [[ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ]]; then
  echo "TAURI_SIGNING_PRIVATE_KEY is required for local release builds." >&2
  echo "Set it with: export TAURI_SIGNING_PRIVATE_KEY=\"\$(cat ~/.tauri/xiangqi-endgame.key)\"" >&2
  exit 1
fi

node "$root/scripts/prepare-tauri-release.mjs" \
  --app-endpoint="$app_endpoint" \
  --pubkey="$pubkey"

echo "Building sidecar for ${target}..."
"$root/scripts/build-sidecar.sh" "$target"

echo "Building Tauri release bundle..."
pnpm tauri build --config src-tauri/tauri.release.conf.json "$@"
