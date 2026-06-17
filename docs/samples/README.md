# 样例截图

《燕云十六声》象棋盘样例，用于定位调参与 CNN 训练数据来源。

## 命名约定
- `screenshot_*` —— 游戏原生截图（PC/手机，清晰、近正对）
- `photo_*` —— 手机翻拍屏幕（透视/反光/摩尔纹，难度高）

## 当前样例
| 文件 | 类型 | 分辨率 | 说明 |
|---|---|---|---|
| `screenshot_1.jpg` | 游戏截图 | 1440×648 | 燕荧的棋局，含右侧说明面板 |
| `screenshot_2.jpg` | 游戏截图 | 1440×648 | 同分辨率残局 |
| `screenshot_3.jpg` | 游戏截图 | 1440×648 | 同分辨率残局 |
| `screenshot_4.png` | 游戏截图 | 1600×878 | 较大分辨率残局 |

> 注：棋盘为半透明叠层，面板有轻微 3D 倾斜，网格线偏淡——这是
> `auto_detect_corners` 自动定位的主要难点；难图可用前端「手动框选四角」兜底。

## 用途
1. **CNN 训练**：经 `tools/extract_crops.py` 提取真实棋子裁剪 → `backend/crops/`，
   与合成数据一起训练 `models/piece_classifier.onnx`。
2. **定位调参**：作为 `auto_detect_corners` 的回归基准。
