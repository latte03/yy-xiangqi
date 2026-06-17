# 开发说明

## 模型文件

发布基线模型会进入 Git：

- `backend/models/piece_classifier.onnx`
- `backend/models/board_locator.onnx`
- `backend/models/labels.txt`
- `backend/models/version.json`

不要提交训练 checkpoint、dataset、crops 或发布时生成的 `models.json`。

模型版本是整数，记录在 `backend/models/version.json`。App 版本和模型版本是两条线：App 代码更新走整包；模型变好走模型 Release。
`release-models` 固定读取这里的版本号，不在 workflow 里手动输入版本。

## 版本控制

App 版本的单一来源是根目录 `VERSION`，必须是 SemVer，例如 `0.2.0`。

同步版本到 `package.json`、`src-tauri/tauri.conf.json` 和 `src-tauri/Cargo.toml`：

```bash
pnpm version:sync -- --version=0.2.0
```

检查版本是否一致：

```bash
pnpm version:check
```

CI 会运行 `pnpm version:check`，避免多处版本号漂移。
