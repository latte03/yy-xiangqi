#!/usr/bin/env bash
set -euo pipefail

target="${1:?target triple is required}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$root/backend/models/piece_classifier.onnx" || ! -f "$root/backend/models/board_locator.onnx" ]]; then
  echo "backend/models must contain piece_classifier.onnx and board_locator.onnx before building the sidecar." >&2
  exit 1
fi

rm -rf "$root/backend/build" "$root/backend/recognizer.spec"
mkdir -p "$root/src-tauri/binaries"

sep=":"
if [[ "$RUNNER_OS" == "Windows" ]]; then
  sep=";"
fi

python -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  "$root/backend/app.py" \
  --name recognizer \
  --distpath "$root/src-tauri/binaries" \
  --workpath "$root/backend/build" \
  --specpath "$root/backend" \
  --add-data "$root/backend/models${sep}models"

if [[ "$RUNNER_OS" == "Windows" ]]; then
  mv "$root/src-tauri/binaries/recognizer.exe" "$root/src-tauri/binaries/recognizer-${target}.exe"
else
  mv "$root/src-tauri/binaries/recognizer" "$root/src-tauri/binaries/recognizer-${target}"
  chmod +x "$root/src-tauri/binaries/recognizer-${target}"
fi
