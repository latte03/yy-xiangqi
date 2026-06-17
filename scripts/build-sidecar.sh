#!/usr/bin/env bash
set -euo pipefail

target="${1:?target triple is required}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${PYTHON:-}" ]]; then
  python_bin="$PYTHON"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
else
  python_bin="python3"
fi

if [[ ! -f "$root/backend/models/piece_classifier.onnx" || ! -f "$root/backend/models/board_locator.onnx" ]]; then
  echo "backend/models must contain piece_classifier.onnx and board_locator.onnx before building the sidecar." >&2
  exit 1
fi

if ! "$python_bin" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "PyInstaller is required in the selected Python environment before building the sidecar." >&2
  echo "Install it with: $python_bin -m pip install pyinstaller" >&2
  exit 1
fi

staged_models="$(mktemp -d)"
cleanup() {
  rm -rf "$staged_models"
}
trap cleanup EXIT

cp "$root/backend/models/piece_classifier.onnx" "$staged_models/"
cp "$root/backend/models/board_locator.onnx" "$staged_models/"
cp "$root/backend/models/version.json" "$staged_models/"
if [[ -f "$root/backend/models/labels.txt" ]]; then
  cp "$root/backend/models/labels.txt" "$staged_models/"
fi

rm -rf "$root/backend/build" "$root/backend/recognizer.spec"
mkdir -p "$root/src-tauri/binaries"

sep=":"
app_path="$root/backend/app.py"
dist_path="$root/src-tauri/binaries"
work_path="$root/backend/build"
spec_path="$root/backend"
models_path="$staged_models"

if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  sep=";"
  if command -v cygpath >/dev/null 2>&1; then
    app_path="$(cygpath -w "$app_path")"
    dist_path="$(cygpath -w "$dist_path")"
    work_path="$(cygpath -w "$work_path")"
    spec_path="$(cygpath -w "$spec_path")"
    models_path="$(cygpath -w "$models_path")"
  fi
fi

"$python_bin" -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  "$app_path" \
  --name recognizer \
  --distpath "$dist_path" \
  --workpath "$work_path" \
  --specpath "$spec_path" \
  --add-data "${models_path}${sep}models"

if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  mv "$root/src-tauri/binaries/recognizer.exe" "$root/src-tauri/binaries/recognizer-${target}.exe"
else
  mv "$root/src-tauri/binaries/recognizer" "$root/src-tauri/binaries/recognizer-${target}"
  chmod +x "$root/src-tauri/binaries/recognizer-${target}"
fi
