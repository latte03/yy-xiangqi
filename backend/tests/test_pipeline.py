"""
端到端流水线自测 (合成棋盘)：
  渲染已知布局 → 注入测试分类器 → recognize → 比对 FEN。
验证「定位 → 切格 → 判空/判色 → FEN」整条骨架。
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recognizer.fen import FILES, RANKS, board_to_fen, empty_board  # noqa: E402
from recognizer.locate import (  # noqa: E402
    CELL,
    MARGIN,
    auto_detect_corners,
)
from recognizer import pipeline  # noqa: E402
from synth import pad_scene, render_board  # noqa: E402

PAD = 80  # 与 pad_scene 默认一致


class QueueClassifier:
    """测试用分类器：按识别扫描顺序返回已知类型，模拟已加载的 CNN。"""

    ready = True
    error = ""

    def __init__(self, board):
        self.types = [
            board[r][f][0]
            for r in range(RANKS)
            for f in range(FILES)
            if board[r][f] is not None
        ]
        self.i = 0

    def classify_type(self, _crop, _color):
        t = self.types[self.i]
        self.i += 1
        return t, 0.99


class MissingClassifier:
    ready = False
    error = "测试模型未就绪"


def known_corners(pad: int = PAD) -> np.ndarray:
    """合成图中落子网格四角的真值 [左上,右上,右下,左下]。"""
    x0, y0 = pad + MARGIN, pad + MARGIN
    x1 = pad + MARGIN + (FILES - 1) * CELL
    y1 = pad + MARGIN + (RANKS - 1) * CELL
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32)


def _sample_board():
    b = empty_board()
    b[0][4] = ("K", "black")
    b[0][3] = ("A", "black")
    b[2][1] = ("C", "black")
    b[3][0] = ("P", "black")
    b[9][4] = ("K", "red")
    b[9][5] = ("A", "red")
    b[7][7] = ("C", "red")
    b[6][2] = ("P", "red")
    b[5][4] = ("R", "red")
    b[4][8] = ("H", "black")
    return b


def test_localization_only():
    img = pad_scene(render_board(_sample_board()))
    corners = auto_detect_corners(img)
    assert corners is not None
    assert corners.shape == (4, 2)


def test_end_to_end_fen():
    board = _sample_board()
    expected = board_to_fen(board, side="red")

    img = pad_scene(render_board(board))
    pipeline._classifier = QueueClassifier(board)
    assert pipeline._classifier.ready

    # 传入已知四角 (手动定位安全网路径)，隔离验证 切格→分类→FEN
    res = pipeline.recognize(img, corners=known_corners(), side="red")
    assert res.ok, res.message
    # 判子位置 (判空) 必须完全正确
    occ_expected = {(r, f) for r in range(10) for f in range(9) if board[r][f]}
    occ_got = {(c.rank, c.file) for c in res.cells}
    assert occ_got == occ_expected, f"判子位置不符: 多{occ_got-occ_expected} 缺{occ_expected-occ_got}"
    # FEN 完全一致
    assert res.fen == expected, f"\n got: {res.fen}\nwant: {expected}"


def test_recognize_fails_without_model():
    pipeline._classifier = MissingClassifier()
    res = pipeline.recognize(pad_scene(render_board(_sample_board())), corners=known_corners(), side="red")
    assert not res.ok
    assert res.needs_review
    assert "测试模型未就绪" in res.message


if __name__ == "__main__":
    test_localization_only()
    test_end_to_end_fen()
    test_recognize_fails_without_model()
    print("pipeline tests passed.")
