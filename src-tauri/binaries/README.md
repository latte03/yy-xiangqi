# Sidecar binaries

Place PyInstaller output here before running a Tauri desktop build.

Tauri resolves `externalBin: ["binaries/recognizer"]` by target triple, so a local
Apple Silicon build expects:

```bash
src-tauri/binaries/recognizer-aarch64-apple-darwin
```

Windows and Linux builds need the matching target suffix, for example:

```bash
src-tauri/binaries/recognizer-x86_64-pc-windows-msvc.exe
src-tauri/binaries/recognizer-x86_64-unknown-linux-gnu
```

The sidecar inherits `XIANGQI_MODELS_MANIFEST` and `XIANGQI_MODEL_DIR` when those
environment variables are present at Rust compile time.
