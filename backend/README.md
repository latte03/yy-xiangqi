# 截图识别后端 (recognizer)

《燕云十六声》象棋残局截图 → FEN 的本地识别服务。运行时只走
**CNN/ONNX 模型推理**；无模型时服务会明确提示模型未就绪，不再回退模板匹配。

## 流水线

```
图像 → 棋盘定位(四角) → 透视校正 → 切 90 个交叉点 → 每格分类(判空/判色/判字) → FEN
```

对应模块（`recognizer/`）：

| 文件 | 职责 |
|---|---|
| `locate.py` | 棋盘定位（自动检测四角 / 接受手动四角）、透视校正、生成 90 交叉点 |
| `slice.py` | 从校正图切出每格小图 |
| `classify.py` | 判空 → 判红黑 → ONNX 模型判类型 |
| `fen.py` | 棋盘矩阵 → FEN（严格对齐前端 `src/engine/fen.ts`） |
| `pipeline.py` | 串联整条流程，输出 `RecognizeResult` |
| `app.py` | FastAPI：`/health`、`/recognize` |

## 运行

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py          # 监听 127.0.0.1:8765

# 开发模式（改代码自动热重载，免手动重启）：
XIANGQI_DEV=1 python app.py
# 可选：XIANGQI_HOST / XIANGQI_PORT 覆盖监听地址与端口
```

前端默认请求 `http://127.0.0.1:8765`，可用环境变量 `VITE_RECOGNIZE_API` 覆盖。

## 棋子类型识别：ONNX 模型唯一入口

`recognizer/classify.py` 加载 `models/piece_classifier.onnx`。颜色（红/黑）与判空独立判定，
CNN 只判 7 个类型（K/A/E/H/R/C/P）。

训练与导出：

```bash
pip install -r requirements-train.txt
# 如果之前已经装过旧依赖，补装即可：
# pip install onnxscript

# 可选：从真实截图收集训练裁剪，提升真实场景准确率
python tools/extract_crops.py path/to/screenshot.png "<那张图的FEN>"
# 自动定位失败时手动给四角(落子网格 左上,右上,右下,左下):
python tools/extract_crops.py shot.png "<FEN>" --corners 112,112;624,112;624,688;112,688

# 生成合成训练数据；有 crops/ 时混入真实裁剪
python tools/gen_training_data.py --clean --per-class 1000 --real-crops crops
python tools/train_classifier.py --epochs 20

# 导出后自检
python tools/check_model.py
python tools/check_model.py --data dataset --split val
# 产物: models/piece_classifier.onnx (+ labels.txt)，约 1–3MB
```

如果训练中途已经生成 `models/piece_classifier.pt`，但因为缺依赖或 ONNX 导出问题失败，可直接重新导出，不必重训：

```bash
python tools/train_classifier.py --export-only
python tools/check_model.py
```

默认导出 `opset=17`，并显式使用 PyTorch legacy exporter，避免 PyTorch 2.12 新 exporter 回转 `opset=11` 时触发 ONNX version converter 报错。需要指定版本时可传 `--opset 17`。
导出时如果看到 PyTorch 的 legacy exporter `DeprecationWarning`，可以忽略；这里是为了避开当前新 exporter 的版本转换问题而有意使用。

推荐自举循环：

1. 在编辑器手动摆好截图对应局面，复制 FEN 预览。
2. 用「截图 + 正确 FEN」跑 `extract_crops.py`，把真实棋子裁剪追加到 `crops/`。
3. 跑 `gen_training_data.py --clean --real-crops crops` 生成训练集。
4. 跑 `train_classifier.py` 导出 `models/piece_classifier.onnx`。
5. 跑 `check_model.py --data dataset --split val` 检查准确率、混淆矩阵和推理耗时。
6. 启动后端，`/health` 返回 `model_ready: true` 后即可识别。

无模型或模型加载失败时，`/health` 返回 `model_ready: false`，`/recognize` 直接返回失败信息。

## 测试

```bash
python tests/test_fen.py        # FEN 输出对齐前端约定
python tests/test_pipeline.py   # 合成棋盘端到端：定位→切格→判空/判色→FEN
```

> 说明：合成测试注入测试分类器模拟已加载模型，验证整条骨架；
> 端到端用例走「已知四角」路径（即前端手动定位安全网），隔离验证
> 切格→判空/判色→FEN。自动定位 (`auto_detect_corners`) 为尽力而为，需用真实
> 截图进一步调参；难图始终可由前端手动框选四角兜底。

## 已知边界 / 待办

- `auto_detect_corners` 需用真实《燕云十六声》截图调参（边缘棋子可能干扰外框检测）。
- 翻拍路（透视/反光/摩尔纹）未实现：计划增强四角透视校正 + CNN 训练数据增强。
- 前端已有「手动框选四角」交互，作为自动定位失败时的兜底，并把四角传给 `/recognize` 的 `corners` 参数。
- 首次使用前必须先训练并生成 `models/piece_classifier.onnx`。

## ONNX 模型工具

| 脚本 | 用途 |
|---|---|
| `tools/extract_crops.py` | 从「截图 + 正确 FEN」提取真实棋子裁剪到 `crops/` |
| `tools/gen_training_data.py` | 生成合成训练集，并可混入真实裁剪 |
| `tools/train_classifier.py` | 训练小型 CNN，导出 ONNX，并校验 PyTorch/ONNX 输出一致性 |
| `tools/check_model.py` | 不启动后端，直接检查 ONNX 是否可加载、单图预测、数据集准确率和混淆矩阵 |

前端首页也提供了「模型训练」入口，会调用 `/training/*` API 完成同样流程：

1. 选择真实截图，粘贴正确 FEN，可手动框选四角。
2. 提取 crops。
3. 生成 dataset。
4. 训练或从 checkpoint 导出 ONNX。
5. 检查模型并查看日志。

## 棋盘四角定位 CNN（截图 + 翻拍统一）

经典轮廓/Hough 定位对真实截图不稳（半透明、线淡、面板倾斜、背景干扰），
翻拍图更难。改用学习式定位：一个小 CNN 直接回归落子网格四角，
**同一模型覆盖截图与翻拍**，靠合成数据增强区分两种 régime。

推理优先级：`locate_corners()` → 定位 CNN（若 `models/board_locator.onnx` 就绪）
→ 回退经典轮廓检测 → 都失败则前端「手动框选四角」兜底。

### 训练（本机，需 PyTorch）
```bash
pip install -r requirements-train.txt
# 1) 合成数据（截图+翻拍混合；photo-frac 控制翻拍占比）
python tools/gen_locate_data.py --num 4000 --photo-frac 0.5
#    有真实标注时自动混入：见下「真实标注」
# 2) 训练 → 导出 models/board_locator.onnx
python tools/train_locator.py --epochs 40
```
验证集报「四角平均像素误差(@256)」，越小越准。就绪后 `/health` 返回 `locator_ready: true`。

### 真实标注（一举两得）
前端做截图识别时若用「手动框选四角」并走 `extract-crops`（piece 训练流程），
后端会把该「图 + 四角」同时存进 `locate_labels/` 作为定位训练标注。
下次 `gen_locate_data.py --real-labels locate_labels`（或 API `use_real_labels=true`）
会把真实样本强增强混入，定位精度随使用提升。

### 训练 API（供前端 Training 页）
- `POST /training/gen-locate-data`  {num, val_frac, photo_frac, clean, use_real_labels}
- `POST /training/train-locator`    {epochs, batch, lr, export_only}
- 进度轮询同 `GET /training/status`

## 软件内模型更新（走 GitHub Releases）

模型当数据资产单独更新，不必发整包（onnx 仅 ~100KB–3MB）。

**加载优先级**：用户数据目录 `appData/models/`（下载的更新）→ 回退打包内置。
内置模型永远在，离线/下载失败都能用。

**接口**：
- `GET /model/status`        当前各模型来源(user/bundled) + 已装版本
- `GET /model/check-update`  拉远端 manifest 比对版本
- `POST /model/apply-update` 下载 → 校验 sha256 + onnxruntime 试加载 → 通过才热替换 + 热重载

**发布侧**：建一个模型 Release（如 tag `models-vN`），挂这些资产：
- `piece_classifier.onnx`、`board_locator.onnx`
- `models.json`：
  ```json
  {"version": 3, "files": [
    {"name":"piece_classifier.onnx","url":"https://github.com/<org>/<repo>/releases/download/models-v3/piece_classifier.onnx","sha256":"<sha256>"},
    {"name":"board_locator.onnx","url":"https://github.com/<org>/<repo>/releases/download/models-v3/board_locator.onnx","sha256":"<sha256>"}]}
  ```

**配置**（环境变量，均可选）：
- `XIANGQI_MODELS_MANIFEST`：manifest 地址。**默认值是占位 `your-org/xiangqi-endgame`，发布前必须改成你的仓库**（改 `recognizer/model_store.py` 的 `DEFAULT_MANIFEST_URL` 或设此 env）。
- `XIANGQI_MODEL_DIR`：自定义用户模型目录（默认平台标准 appData）。

> 安全：sha256 + onnxruntime 试加载双校验，任一步失败保留旧模型，绝不变砖。

## 打包（PyInstaller → Tauri sidecar）

由 `scripts/build-sidecar.sh <target-triple>` 完成（CI `release-app.yml` 已调用）：
1. 把 `models/` 下的 onnx + labels + version 暂存到临时目录（**不含 .pt 训练 checkpoint**）。
2. `pyinstaller --onefile app.py --add-data <staged>:models`，并 `--exclude-module` 掉
   torch 等仅训练依赖（瘦身）、`--collect-submodules uvicorn`（补隐藏导入）。
3. 产物按 `recognizer-<target-triple>` 命名搬进 `src-tauri/binaries/`，供 Tauri 作 externalBin。

本地手动构建某平台：
```bash
pip install -r requirements.txt pyinstaller
scripts/build-sidecar.sh aarch64-apple-darwin   # 或对应的 target triple
```

要点：
- **不需要手写/提交 `.spec`**：脚本用 CLI 参数完成，且每次构建会重建临时 spec（`.gitignore` 已忽略 `backend/recognizer.spec`、`backend/dist`、`backend/build`）。
- 二进制不入库（`.gitignore` 忽略 `src-tauri/binaries/*`），CI 现构建。
- CI 只装 `requirements.txt`（不装 `requirements-train.txt`），配合 `--exclude-module` 体积更小。
- macOS 分发需对二进制做代码签名/公证（在 tauri build 阶段处理）。

详见 `docs/OCR与桌面端技术选型分析.md` 与 `docs/release.md`。
