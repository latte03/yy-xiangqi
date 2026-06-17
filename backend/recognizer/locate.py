"""
棋盘定位：从输入图像中找到棋盘「落子网格」的四个角，做透视校正，
并生成 90 个交叉点坐标。

设计原则 (见项目记忆 CLAUDE.md):
  - 禁止写死像素坐标，靠检测外框/网格线。
  - 截图路：棋盘基本正对，自动检测最大矩形即可。
  - 难图/翻拍：支持外部传入手动四角 (前端拖角安全网)。

坐标约定：网格 9 列 (file) × 10 行 (rank)。
  - 落子网格的「角点矩形」宽:高 = 8:9 (8 个横向间隔, 9 个纵向间隔)。
  - 校正后输出图：列间距 = 行间距 = CELL，左上角为 (file=0, rank=0)=黑方左角。
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

import cv2
import numpy as np

FILES = 9
RANKS = 10
CELL = 64  # 校正后每格像素间距
MARGIN = CELL // 2  # 校正图四周留半格，保证边线棋子完整


def order_corners(pts: np.ndarray) -> np.ndarray:
    """把 4 个点排序为 [左上, 右上, 右下, 左下]。"""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)
    return np.array(
        [
            pts[np.argmin(s)],  # 左上: x+y 最小
            pts[np.argmin(d)],  # 右上: x-y 最大 → -(x-y) 最小... 用下式更稳
            pts[np.argmax(s)],  # 右下: x+y 最大
            pts[np.argmax(d)],  # 左下: x-y 最小
        ],
        dtype=np.float32,
    )


def warped_size() -> Tuple[int, int]:
    """校正后图像尺寸 (w, h)。"""
    w = (FILES - 1) * CELL + 2 * MARGIN
    h = (RANKS - 1) * CELL + 2 * MARGIN
    return w, h


def grid_points() -> List[List[Tuple[int, int]]]:
    """校正图中的 90 个交叉点像素坐标 points[rank][file] = (x, y)。"""
    pts: List[List[Tuple[int, int]]] = []
    for r in range(RANKS):
        row = []
        for f in range(FILES):
            x = MARGIN + f * CELL
            y = MARGIN + r * CELL
            row.append((x, y))
        pts.append(row)
    return pts


def warp_to_canonical(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """给定落子网格四角 (任意顺序)，透视校正到标准棋盘图。"""
    src = order_corners(corners)
    w, h = warped_size()
    # 目标四角 = 网格角点位置 (含 MARGIN)
    dst = np.array(
        [
            [MARGIN, MARGIN],
            [MARGIN + (FILES - 1) * CELL, MARGIN],
            [MARGIN + (FILES - 1) * CELL, MARGIN + (RANKS - 1) * CELL],
            [MARGIN, MARGIN + (RANKS - 1) * CELL],
        ],
        dtype=np.float32,
    )
    m = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, m, (w, h))


def _aspect_ok(quad: np.ndarray, target=8 / 9, tol=0.35) -> bool:
    """判断四边形长宽比是否接近落子网格 8:9。"""
    q = order_corners(quad)
    wtop = np.linalg.norm(q[1] - q[0])
    wbot = np.linalg.norm(q[2] - q[3])
    hleft = np.linalg.norm(q[3] - q[0])
    hright = np.linalg.norm(q[2] - q[1])
    w = (wtop + wbot) / 2
    h = (hleft + hright) / 2
    if h <= 1:
        return False
    ratio = w / h
    return abs(ratio - target) / target <= tol


def auto_detect_corners(img: np.ndarray) -> Optional[np.ndarray]:
    """
    自动检测落子网格四角。返回 [左上,右上,右下,左下] 或 None。

    策略 (适用于截图路：高对比、近正对)：
      1. 灰度 + 自适应/Otsu 边缘
      2. 找轮廓，筛选近似四边形、面积够大、长宽比接近 8:9 的候选
      3. 取面积最大者
    难图建议改用手动四角。
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    img_area = img.shape[0] * img.shape[1]
    best = None
    best_area = 0.0
    for c in contours:
        area = cv2.contourArea(c)
        if area < img_area * 0.05:  # 太小忽略
            continue
        if area > img_area * 0.92:  # 几乎占满整图 → 多半是画面外框，非棋盘
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) != 4:
            continue
        quad = approx.reshape(4, 2).astype(np.float32)
        if not _aspect_ok(quad):
            continue
        if area > best_area:
            best_area = area
            best = quad
    return order_corners(best) if best is not None else None


# ---------------- 学习式定位 (关键点 CNN, 截图+翻拍统一) ----------------

from .locate_model import decode_corners, preprocess_locate  # noqa: E402
from .model_store import resolve_model  # noqa: E402


class CnnLocator:
    """棋盘四角定位 CNN (onnxruntime)。无模型/加载失败时 ready=False。"""

    def __init__(self, model_path: Optional[str] = None):
        if model_path is None:
            model_path = resolve_model("board_locator.onnx")  # 每次构造重新解析，支持热更新
        self.session = None
        self.input_name = None
        self.model_path = model_path
        self.error = ""
        if not os.path.isfile(model_path):
            self.error = f"未找到定位模型: {model_path}"
            return
        try:
            import onnxruntime as ort

            so = ort.SessionOptions()
            so.log_severity_level = 3
            self.session = ort.InferenceSession(model_path, sess_options=so, providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
        except Exception as exc:  # pragma: no cover
            self.session = None
            self.error = f"定位模型加载失败: {exc}"

    @property
    def ready(self) -> bool:
        return self.session is not None

    def detect(self, img: np.ndarray) -> Optional[np.ndarray]:
        if self.session is None:
            return None
        x, params = preprocess_locate(img)
        pred = self.session.run(None, {self.input_name: x[None, :, :, :]})[0][0]
        corners = decode_corners(pred, params)
        return order_corners(corners)


_locator: Optional[CnnLocator] = None


def get_locator() -> CnnLocator:
    global _locator
    if _locator is None:
        _locator = CnnLocator()
    return _locator


def reset_locator() -> None:
    """清缓存，下次 get_locator 重新加载（模型热更新后调用）。"""
    global _locator
    _locator = None


def locate_corners(img: np.ndarray) -> Optional[np.ndarray]:
    """
    统一定位入口：优先用定位 CNN (鲁棒，覆盖截图+翻拍)，
    模型缺失/未就绪时回退经典轮廓检测。都失败返回 None (前端手动框选兜底)。
    """
    loc = get_locator()
    if loc.ready:
        c = loc.detect(img)
        if c is not None:
            return c
    return auto_detect_corners(img)
