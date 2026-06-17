# 发布说明

本文记录维护者发布桌面 App 和模型包需要的配置。普通本地开发不需要这些密钥。

## GitHub Actions

仓库包含三条工作流：

- `ci`: 常规检查
- `release-models`: 发布模型包到 `models-latest`
- `release-app`: 发布桌面包到 `app-latest`

首次发布建议顺序：

1. 确认 `backend/models/*.onnx` 和 `backend/models/version.json` 已更新。
2. 运行 `release-models`，生成并上传 `models.json`。模型版本读取 `backend/models/version.json`。
3. 运行 `release-app`，构建 Tauri 桌面包。App 版本读取根目录 `VERSION`。

## 本地 release 构建

本地构建 release 包时需要先生成 Tauri sidecar 二进制；直接运行 `tauri build --config ...` 会因为缺少 `src-tauri/binaries/recognizer-<target>` 失败。

使用封装脚本：

```bash
pnpm tauri:build:release
```

脚本会自动：

1. 读取当前 Rust target triple。
2. 用 PyInstaller 生成 `src-tauri/binaries/recognizer-<target>`。
3. 运行 `tauri build --config src-tauri/tauri.release.conf.json`。

如需指定 Python，可设置：

```bash
PYTHON=backend/.venv/bin/python pnpm tauri:build:release
```

指定的 Python 环境需要先安装后端依赖和 PyInstaller：

```bash
backend/.venv/bin/python -m pip install -r backend/requirements.txt pyinstaller
```

release 构建会生成 updater artifacts，因此还需要先配置下方的 Tauri updater signing key 环境变量。

本地推荐复制模板：

```bash
cp scripts/local-release-env.example.sh scripts/local-release-env.sh
```

填写 `scripts/local-release-env.sh` 后加载：

```bash
source scripts/local-release-env.sh
pnpm tauri:build:release
```

`scripts/local-release-env.sh` 已被 `.gitignore` 忽略，不要提交真实私钥。

## Tauri Updater Keys

Tauri updater 需要一对更新签名密钥。它们只用于验证更新包是不是可信来源，不等同于 macOS/Windows 代码签名证书。

生成密钥：

```bash
pnpm tauri signer generate --write-keys ~/.tauri/xiangqi-endgame.key
```

可选：无交互并设置密码：

```bash
pnpm tauri signer generate \
  --write-keys ~/.tauri/xiangqi-endgame.key \
  --password "你的密码" \
  --ci
```

需要配置到 GitHub：

- Repository variable `TAURI_UPDATER_PUBKEY`: 生成时输出的 public key 内容。它会写进 Tauri 配置，可以公开。
- Repository secret `TAURI_PRIVATE_KEY`: 私钥文件内容，必须保密，丢失后无法继续给已安装用户发布可验证更新。
- Repository secret `TAURI_KEY_PASSWORD`: 生成私钥时设置的密码。若生成时没设密码，可留空或设为空字符串。

官方要求：构建更新包时私钥必须通过环境变量 `TAURI_SIGNING_PRIVATE_KEY` 提供，密码通过 `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` 提供；`.env` 文件不会被 Tauri updater 签名流程读取。

本地环境变量对应关系：

- `TAURI_UPDATER_PUBKEY`: public key，传给 `scripts/prepare-tauri-release.mjs` 写入 Tauri release 配置。
- `TAURI_SIGNING_PRIVATE_KEY`: 私钥内容，例如 `$(cat ~/.tauri/xiangqi-endgame.key)`。
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`: 私钥密码；无密码可留空。
- `APP_UPDATE_ENDPOINT`: 可选，默认 `https://github.com/latte03/yy-xiangqi/releases/download/app-latest/latest.json`。

后续若要消除系统安全提示，还需要另外接入 macOS Developer ID 签名/公证和 Windows 代码签名。
