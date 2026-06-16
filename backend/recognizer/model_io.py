"""
CNN 棋子类型分类器的共享定义：类别、输入尺寸、预处理。
训练 (tools/train_classifier.py)、数据生成 (tools/gen_training_data.py)、
推理 (recognizer/classify.py) 三处共用，保证一致。

设计：
  - CNN 只判「类型」7 类 (K/A/E/H/R/C/P)，输入为灰度棋格。
    红黑同型字形不同 (帅/将)，但都映射到同一类型；颜色由 detect_color 另判，
    所以同一型的红、黑字都作为该类训练样本。
  - 马/车/炮 红黑字形相同，靠颜色区分，对类型分类无歧义。
"""

from __future__ import annotations

import cv2
import numpy as np

TYPES = ["K", "A", "E", "H", "R", "C", "P"]
NUM_CLASSES = len(TYPES)
INPUT_SIZE = 64  # 模型输入 64x64 灰度
MODEL_PATH_DEFAULT = "models/piece_classifier.onnx"


def preprocess_gray(crop_bgr: np.ndarray) -> np.ndarray:
    """
    棋格 BGR/灰度裁剪 → (1, INPUT_SIZE, INPUT_SIZE) float32, [0,1]。
    训练与推理必须用同一函数。
    """
    if crop_bgr.ndim == 3:
        g = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    else:
        g = crop_bgr
    g = cv2.resize(g, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)
    return (g.astype(np.float32) / 255.0)[None, :, :]
