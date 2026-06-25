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

is_windows=false
case "${RUNNER_OS:-}" in
  Windows) is_windows=true ;;
esac
case "$target" in
  *windows* | *-pc-windows-*) is_windows=true ;;
esac
case "$(uname -s 2>/dev/null || true)" in
  MINGW* | MSYS* | CYGWIN*) is_windows=true ;;
esac

to_pyinstaller_path() {
  local path="$1"
  if [[ "$is_windows" == true && -n "$(command -v cygpath 2>/dev/null)" ]]; then
    # Mixed style avoids backslash escaping surprises in PyInstaller spec files.
    cygpath -m "$path"
  else
    printf '%s\n' "$path"
  fi
}

if [[ ! -f "$root/backend/models/piece_classifier.onnx" || ! -f "$root/backend/models/board_locator.onnx" || ! -f "$root/backend/models/version.json" ]]; then
  echo "backend/models must contain piece_classifier.onnx, board_locator.onnx, and version.json before building the sidecar." >&2
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

if [[ "$is_windows" == true ]]; then
  sep=";"
fi

app_path="$(to_pyinstaller_path "$app_path")"
dist_path="$(to_pyinstaller_path "$dist_path")"
work_path="$(to_pyinstaller_path "$work_path")"
spec_path="$(to_pyinstaller_path "$spec_path")"
models_path="$(to_pyinstaller_path "$models_path")"

echo "Building recognizer sidecar for $target"
echo "Using model bundle: $models_path"

# 仅训练/无关的大依赖，排除以瘦身（推理端 app.py 不导入这些）
exclude_modules=(
  torch torchvision onnx onnxscript
  matplotlib scipy pandas
  tkinter PyQt5 PyQt6 PySide2 PySide6
  IPython notebook pytest
  # torch 的传递依赖 + 仅训练用，运行时（cv2/numpy/fastapi/onnxruntime）不需要
  sympy networkx mpmath PIL Pillow
)
exclude_args=()
for m in "${exclude_modules[@]}"; do
  exclude_args+=(--exclude-module "$m")
done

"$python_bin" -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  "$app_path" \
  --name recognizer \
  --distpath "$dist_path" \
  --workpath "$work_path" \
  --specpath "$spec_path" \
  --collect-submodules uvicorn \
  "${exclude_args[@]}" \
  --add-data "${models_path}${sep}models"

if [[ "$is_windows" == true ]]; then
  mv "$root/src-tauri/binaries/recognizer.exe" "$root/src-tauri/binaries/recognizer-${target}.exe"
else
  mv "$root/src-tauri/binaries/recognizer" "$root/src-tauri/binaries/recognizer-${target}"
  chmod +x "$root/src-tauri/binaries/recognizer-${target}"
fi
