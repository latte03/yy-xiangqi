"""
单格分类：判空 → 判红黑 → CNN 判棋子类型。

三步法：
  1. is_occupied: 格中是否有棋子圆盘 (亮色不透明圆盘 vs 半透明深色棋盘背景)
  2. detect_color: 圆盘上的字是红 (红字) 还是黑 (深字)
  3. OnnxClassifier: 小型 CNN (models/piece_classifier.onnx) 判 7 种类型

颜色 (detect_color) 与判空 (is_occupied) 独立，CNN 只判 7 类型。
运行时不再维护模板匹配回退；模型不存在或加载失败时，识别接口直接返回错误。
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import cv2
import numpy as np

from .model_io import TYPES, preprocess_gray
from .model_store import resolve_model

# 用户更新目录优先 → 回退打包内置（见 model_store）
MODEL_PATH = resolve_model("piece_classifier.onnx")


# ---------- 1. 判空 ----------
def is_occupied(crop: np.ndarray) -> bool:
    """
    判空逻辑：棋子是「亮色不透明圆盘」，棋盘是「半透明偏暗背景 + 细网格线」。
    在中心圆形区域内统计「明显亮于棋盘背景」的像素占比——
    有圆盘时占比高 (圆盘大片亮)，空格时占比极低 (只有暗背景和细线)。
    对深色字鲁棒：判的是圆盘亮区，而非中心亮度 (字可深可浅)。
    """
    if crop.size == 0:
        return False
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = g.shape
    cy, cx = h // 2, w // 2
    rad = int(min(h, w) * 0.42)
    yy, xx = np.ogrid[:h, :w]
    disk = (yy - cy) ** 2 + (xx - cx) ** 2 <= rad * rad
    region = g[disk]
    if region.size == 0:
        return False
    # 背景亮度参考：四角 (一定在圆盘外、是棋盘背景)
    corner = np.concatenate(
        [g[:6, :6].ravel(), g[:6, -6:].ravel(), g[-6:, :6].ravel(), g[-6:, -6:].ravel()]
    )
    bg = float(np.median(corner))
    # 阈值取背景与亮圆盘之间：背景之上 60 灰阶视为圆盘
    thr = bg + 60.0
    bright_ratio = float((region > thr).mean())
    # 实测：真子(含兵卒)亮区占比 ≥ 0.16，空格 ≤ 0.05，偶有纹理/高光约 0.10。
    # 阈值取 0.13，挡掉纹理假阳性又不误伤兵卒。
    return bright_ratio > 0.13


# ---------- 2. 判红黑 ----------
def detect_color(crop: np.ndarray) -> str:
    """
    红子：字为红色 (高 R、低 G/B)；黑子：字为深灰/黑。
    在圆盘内统计明显红色像素比例。
    """
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    # 红色 hue 在两端
    lower1 = cv2.inRange(hsv, (0, 70, 50), (12, 255, 255))
    lower2 = cv2.inRange(hsv, (168, 70, 50), (180, 255, 255))
    red_mask = cv2.bitwise_or(lower1, lower2)
    red_ratio = float(red_mask.sum()) / 255.0 / red_mask.size
    return "red" if red_ratio > 0.02 else "black"


class OnnxClassifier:
    """小型 CNN 类型分类器 (onnxruntime)。"""

    def __init__(self, model_path: Optional[str] = None):
        if model_path is None:
            model_path = resolve_model("piece_classifier.onnx")  # 每次构造重新解析，支持热更新
        self.session = None
        self.input_name = None
        self.model_path = model_path
        self.error = ""
        if not os.path.isfile(model_path):
            self.error = f"未找到模型文件: {model_path}"
            return
        try:
            import onnxruntime as ort  # 延迟导入

            so = ort.SessionOptions()
            so.log_severity_level = 3
            self.session = ort.InferenceSession(model_path, sess_options=so, providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
        except Exception as exc:
            self.session = None
            self.error = f"模型加载失败: {exc}"

    @property
    def ready(self) -> bool:
        return self.session is not None

    def classify_type(self, crop: np.ndarray, color: str) -> Tuple[str, float]:
        """返回 (type, prob)。color 不参与 (CNN 只判类型)。"""
        if self.session is None:
            return "?", 0.0
        x = preprocess_gray(crop)[None, :, :, :]  # (1,1,H,W)
        logits = self.session.run(None, {self.input_name: x})[0][0]
        e = np.exp(logits - logits.max())
        prob = e / e.sum()
        i = int(prob.argmax())
        return TYPES[i], float(prob[i])


def build_classifier() -> OnnxClassifier:
    """加载 CNN(ONNX) 分类器。无模型时返回 not-ready 分类器，不做模板回退。"""
    return OnnxClassifier()


def classify_cell(
    crop: np.ndarray, clf
) -> Optional[Tuple[str, str, float]]:
    """
    返回 (type, color, confidence)；空格返回 None。
    type 可能为 '?' (有子但无法判类型，需人工纠正)。
    """
    if not is_occupied(crop):
        return None
    color = detect_color(crop)
    if clf is None or not clf.ready:
        return "?", color, 0.0
    t, s = clf.classify_type(crop, color)
    return t, color, s
