# 发布说明

本文记录维护者发布桌面 App 和模型包需要的配置。普通本地开发不需要这些密钥。

## GitHub Actions

仓库包含三条工作流：

- `ci`: 常规检查
- `release-models`: 发布模型包到 `models-latest`
- `release-app`: 发布桌面包到 `app-latest`

首次发布建议顺序：

1. 确认 `backend/models/*.onnx` 和 `backend/models/version.json` 已更新。
2. 运行 `release-models`，生成并上传 `models.json`。`version` 可留空，默认读取 `backend/models/version.json`。
3. 运行 `release-app`，构建 Tauri 桌面包。

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

后续若要消除系统安全提示，还需要另外接入 macOS Developer ID 签名/公证和 Windows 代码签名。
