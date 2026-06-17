"""
棋盘四角定位 CNN 的共享定义：输入尺寸、letterbox 预处理、四角编解码。
训练 (tools/train_locator.py)、数据生成 (tools/gen_locate_data.py)、
推理 (recognizer/locate.py) 三处共用，保证一致。

设计：
  - 输入：整张截图 → letterbox 到 LOC_INPUT×LOC_INPUT 灰度 (保持长宽比，补零)。
  - 输出：8 个值 = 落子网格四角 (左上,右上,右下,左下) 在 letterbox 图中的归一化坐标 [0,1]。
  - 回归而非分类；推理后用 decode_corners 映射回原图像素。
  - 覆盖截图路 (近正对) 与翻拍路 (透视/反光/摩尔纹) —— 同一模型，靠数据增强区分。
"""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

LOC_INPUT = 256  # 定位网络输入边长
MODEL_PATH_DEFAULT = "models/board_locator.onnx"
NUM_COORDS = 8  # 4 角 × (x, y)
CORNER_ORDER = ("TL", "TR", "BR", "BL")  # 左上, 右上, 右下, 左下


def letterbox_params(w: int, h: int, size: int = LOC_INPUT) -> Tuple[float, int, int, int, int]:
    """返回 (scale, pad_x, pad_y, new_w, new_h)：等比缩放到 size 内并居中补零。"""
    scale = size / max(w, h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    px, py = (size - nw) // 2, (size - nh) // 2
    return scale, px, py, nw, nh


def preprocess_locate(img: np.ndarray, size: int = LOC_INPUT):
    """
    整图 BGR/灰度 → ((1, size, size) float32 [0,1], params)。
    params=(scale, px, py, w, h) 供 decode_corners 反映射。
    """
    if img.ndim == 3:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        g = img
    h, w = g.shape[:2]
    scale, px, py, nw, nh = letterbox_params(w, h, size)
    resized = cv2.resize(g, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((size, size), dtype=np.uint8)
    canvas[py : py + nh, px : px + nw] = resized
    x = (canvas.astype(np.float32) / 255.0)[None, :, :]
    return x, (scale, px, py, w, h)


def encode_corners(corners_px: np.ndarray, w: int, h: int, size: int = LOC_INPUT) -> np.ndarray:
    """原图像素四角 (4,2) → letterbox 归一化 8 向量 [0,1]。"""
    scale, px, py, _, _ = letterbox_params(w, h, size)
    out = np.empty(NUM_COORDS, dtype=np.float32)
    for i, (x, y) in enumerate(corners_px):
        out[2 * i] = (x * scale + px) / size
        out[2 * i + 1] = (y * scale + py) / size
    return out


def decode_corners(pred: np.ndarray, params: Tuple[float, int, int, int, int], size: int = LOC_INPUT) -> np.ndarray:
    """letterbox 归一化 8 向量 → 原图像素四角 (4,2)。"""
    scale, px, py, w, h = params
    pred = np.asarray(pred, dtype=np.float32).reshape(4, 2)
    out = np.empty((4, 2), dtype=np.float32)
    for i, (nx, ny) in enumerate(pred):
        out[i, 0] = (nx * size - px) / scale
        out[i, 1] = (ny * size - py) / scale
    # 夹到图像范围内，避免越界
    out[:, 0] = np.clip(out[:, 0], 0, w - 1)
    out[:, 1] = np.clip(out[:, 1], 0, h - 1)
    return out
