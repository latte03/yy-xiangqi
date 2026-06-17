#!/usr/bin/env bash
# Copy to scripts/local-release-env.sh and fill in local values.
# Do not commit scripts/local-release-env.sh.

export TAURI_UPDATER_PUBKEY="paste-public-key-here"
export TAURI_SIGNING_PRIVATE_KEY="$(cat "$HOME/.tauri/xiangqi-endgame.key")"
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD=""

# Optional overrides for local release builds.
export APP_UPDATE_ENDPOINT="https://github.com/latte03/yy-xiangqi/releases/download/app-latest/latest.json"
export XIANGQI_MODELS_MANIFEST="https://github.com/latte03/yy-xiangqi/releases/download/models-latest/models.json"
