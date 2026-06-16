"""
合成棋盘图工具：用于自测流水线 (无真实截图时)。
模拟《燕云十六声》关键特征：半透明偏暗棋盘背景 + 亮色圆盘 + 红/黑字。
字形用程序化图案代替真实汉字 (仅用于验证定位/切格/匹配骨架)。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

from recognizer.locate import CELL, FILES, MARGIN, RANKS, grid_points, warped_size

PIECE_TYPES = ["K", "A", "E", "H", "R", "C", "P"]
Board = List[List[Optional[Tuple[str, str]]]]


def _glyph(canvas, cx, cy, ptype, color_bgr):
    """
    用「空间上互相区分的实心图案」代替真实汉字。
    真实汉字稠密且笔画分布各异；这里用占据不同区域的实心块作代理，
    验证「定位→切格→分类→FEN」整条逻辑。
    """
    idx = PIECE_TYPES.index(ptype)
    r = CELL // 4
    if idx == 0:  # K 大实心圆 (满)
        cv2.circle(canvas, (cx, cy), r, color_bgr, -1)
    elif idx == 1:  # A 圆环 (空心)
        cv2.circle(canvas, (cx, cy), r, color_bgr, 5)
    elif idx == 2:  # E 实心三角
        pts = np.array([[cx, cy - r], [cx - r, cy + r], [cx + r, cy + r]])
        cv2.fillPoly(canvas, [pts], color_bgr)
    elif idx == 3:  # H 左半
        cv2.rectangle(canvas, (cx - r, cy - r), (cx, cy + r), color_bgr, -1)
    elif idx == 4:  # R 右半
        cv2.rectangle(canvas, (cx, cy - r), (cx + r, cy + r), color_bgr, -1)
    elif idx == 5:  # C 上半
        cv2.rectangle(canvas, (cx - r, cy - r), (cx + r, cy), color_bgr, -1)
    else:  # P 下半
        cv2.rectangle(canvas, (cx - r, cy), (cx + r, cy + r), color_bgr, -1)


def render_board(board: Board, scene_shift=0, noise=0) -> np.ndarray:
    """
    渲染一张标准朝向 (红下黑上) 的合成棋盘图。
    noise>0 时叠加随机底噪 (模拟透出场景)；单元测试用 noise=0 保证可复现。
    """
    w, h = warped_size()
    # 半透明偏暗背景 (模拟透出场景, scene_shift 改变底色)
    img = np.full((h, w, 3), 40 + scene_shift, dtype=np.uint8)
    if noise > 0:
        img = cv2.add(img, np.random.randint(0, noise, (h, w, 3), dtype=np.uint8))

    # 网格线
    pts = grid_points()
    line = (110, 110, 110)
    for r in range(RANKS):
        cv2.line(img, pts[r][0], pts[r][FILES - 1], line, 1)
    for f in range(FILES):
        cv2.line(img, pts[0][f], pts[RANKS - 1][f], line, 1)
    # 外框 (供 auto_detect_corners 检测)
    cv2.rectangle(img, pts[0][0], pts[RANKS - 1][FILES - 1], (200, 200, 200), 2)

    # 棋子
    for r in range(RANKS):
        for f in range(FILES):
            piece = board[r][f]
            if piece is None:
                continue
            ptype, color = piece
            cx, cy = pts[r][f]
            cv2.circle(img, (cx, cy), CELL // 2 - 4, (235, 235, 235), -1)  # 亮圆盘
            cv2.circle(img, (cx, cy), CELL // 2 - 4, (120, 120, 120), 2)
            glyph_bgr = (40, 40, 210) if color == "red" else (30, 30, 30)
            _glyph(img, cx, cy, ptype, glyph_bgr)
    return img


def pad_scene(img: np.ndarray, pad=80) -> np.ndarray:
    """四周加暗色边，模拟棋盘在更大画面里 (考验定位)。"""
    h, w = img.shape[:2]
    canvas = np.full((h + 2 * pad, w + 2 * pad, 3), 20, dtype=np.uint8)
    canvas[pad : pad + h, pad : pad + w] = img
    return canvas
