"""FEN 输出对齐前端约定的单元测试。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recognizer.fen import board_to_fen, empty_board  # noqa: E402


def test_empty_board_fen():
    b = empty_board()
    # 10 行全空 → 每行 "9"
    assert board_to_fen(b) == "9/9/9/9/9/9/9/9/9/9 w - - 0 1"


def test_initial_position_matches_frontend():
    """与 src/types/index.ts 的 INITIAL_FEN 一致。"""
    b = empty_board()
    back = ["R", "H", "E", "A", "K", "A", "E", "H", "R"]
    # rank 0 = 黑底线
    for f, t in enumerate(back):
        b[0][f] = (t, "black")
    b[2][1] = ("C", "black")
    b[2][7] = ("C", "black")
    for f in range(0, 9, 2):
        b[3][f] = ("P", "black")
    # rank 9 = 红底线
    for f, t in enumerate(back):
        b[9][f] = (t, "red")
    b[7][1] = ("C", "red")
    b[7][7] = ("C", "red")
    for f in range(0, 9, 2):
        b[6][f] = ("P", "red")

    expected = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    assert board_to_fen(b, side="red") == expected


def test_side_and_counters():
    b = empty_board()
    b[0][4] = ("K", "black")
    b[9][4] = ("K", "red")
    fen = board_to_fen(b, side="black", halfmove=3, fullmove=12)
    assert fen == "4k4/9/9/9/9/9/9/9/9/4K4 b - - 3 12"


if __name__ == "__main__":
    test_empty_board_fen()
    test_initial_position_matches_frontend()
    test_side_and_counters()
    print("FEN tests passed.")
