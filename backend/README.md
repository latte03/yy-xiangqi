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

## 打包（后续）

PyInstaller 打成单二进制，作 Tauri 2 sidecar 随桌面 App 分发：

```bash
pip install pyinstaller
pyinstaller -F app.py -n recognizer-$(uname -m) --add-data "models:models"
```

详见 `docs/OCR与桌面端技术选型分析.md`。
