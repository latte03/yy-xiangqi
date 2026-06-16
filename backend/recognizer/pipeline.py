"""
识别主流程：图像 → FEN。

  load image → 定位四角 → 透视校正 → 切 90 格 → 每格分类 → 棋盘矩阵 → FEN

可选项:
  - corners: 外部传入手动四角 (前端拖角安全网)，跳过自动检测
  - side: 走子方，默认红先 (该游戏执红先行)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from .classify import build_classifier, classify_cell
from .fen import FILES, RANKS, board_to_fen, empty_board
from .locate import auto_detect_corners, warp_to_canonical
from .slice import slice_cells


@dataclass
class CellResult:
    rank: int
    file: int
    type: str  # K/A/E/H/R/C/P 或 '?'
    color: str  # 'red'/'black'
    confidence: float


@dataclass
class RecognizeResult:
    ok: bool
    fen: str = ""
    side: str = "red"
    cells: List[CellResult] = field(default_factory=list)
    low_confidence: List[Tuple[int, int]] = field(default_factory=list)  # (rank,file)
    needs_review: bool = False
    message: str = ""


# 进程内复用分类器 (加载一次 ONNX 模型)
_classifier = None


def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = build_classifier()
    return _classifier


def recognize(
    img: np.ndarray,
    corners: Optional[np.ndarray] = None,
    side: str = "red",
    conf_threshold: float = 0.55,
) -> RecognizeResult:
    clf = get_classifier()
    if not clf.ready:
        return RecognizeResult(
            ok=False,
            message=(clf.error or "CNN 模型未就绪，请先训练并放置 models/piece_classifier.onnx。"),
            needs_review=True,
        )

    if corners is None:
        corners = auto_detect_corners(img)
    if corners is None:
        return RecognizeResult(
            ok=False,
            message="未能自动定位棋盘，请手动框选四角或上传更清晰的截图。",
            needs_review=True,
        )

    warped = warp_to_canonical(img, np.asarray(corners, dtype=np.float32))
    cells = slice_cells(warped)

    board = empty_board()
    results: List[CellResult] = []
    low: List[Tuple[int, int]] = []
    for r in range(RANKS):
        for f in range(FILES):
            out = classify_cell(cells[r][f], clf)
            if out is None:
                continue
            ptype, color, conf = out
            results.append(CellResult(r, f, ptype, color, conf))
            if ptype != "?":
                board[r][f] = (ptype, color)
            if ptype == "?" or conf < conf_threshold:
                low.append((r, f))

    fen = board_to_fen(board, side=side)
    return RecognizeResult(
        ok=True,
        fen=fen,
        side=side,
        cells=results,
        low_confidence=low,
        needs_review=len(low) > 0,
        message="",
    )
