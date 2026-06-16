"""
从校正后的标准棋盘图切出 90 个交叉点的小图块 (cell crops)。
每个 crop 以交叉点为中心，边长约一格，供分类器判断。
"""

from __future__ import annotations

from typing import List

import numpy as np

from .locate import CELL, FILES, RANKS, grid_points

# 取稍大于一格的窗口，保证棋子圆盘完整 (圆盘直径常略大于格距)
CROP_HALF = int(CELL * 0.6)


def slice_cells(warped: np.ndarray) -> List[List[np.ndarray]]:
    """返回 cells[rank][file] = 以该交叉点为中心的图块 (BGR)。"""
    h, w = warped.shape[:2]
    pts = grid_points()
    cells: List[List[np.ndarray]] = []
    for r in range(RANKS):
        row = []
        for f in range(FILES):
            cx, cy = pts[r][f]
            x0 = max(0, cx - CROP_HALF)
            y0 = max(0, cy - CROP_HALF)
            x1 = min(w, cx + CROP_HALF)
            y1 = min(h, cy + CROP_HALF)
            crop = warped[y0:y1, x0:x1].copy()
            row.append(crop)
        cells.append(row)
    return cells


def normalize_cell(crop: np.ndarray, size: int = 48) -> np.ndarray:
    """统一尺寸，供调试或 CNN 输入。"""
    import cv2

    if crop.size == 0:
        return np.zeros((size, size, 3), dtype=np.uint8)
    return cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
