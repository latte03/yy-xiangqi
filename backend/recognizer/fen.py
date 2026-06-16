"""
棋盘矩阵 → FEN 字符串。

严格对齐前端约定 (src/engine/fen.ts, src/types/index.ts):
  - board[rank][file]，rank 0 = 黑方底线 (图像最上一行)，rank 9 = 红方底线 (图像最下一行)
  - file 0..8 从红方左侧数
  - WXF 风格字符: K(帅/将) A(仕/士) E->B(相/象) H->N(马) R(车) C(炮) P(兵/卒)
  - 大写 = 红方, 小写 = 黑方
  - FEN board 部分: rank 0 → rank 9，每行 file 0 → file 8

棋子内部表示: (type, color)
  type ∈ {K, A, E, H, R, C, P}
  color ∈ {'red', 'black'}
  空格用 None
"""

from __future__ import annotations

from typing import List, Optional, Tuple

FILES = 9
RANKS = 10

# 内部 type → FEN 字符 (大写, WXF 风格)
_TYPE_TO_FEN = {
    "K": "K",
    "A": "A",
    "E": "B",  # 相/象
    "H": "N",  # 马
    "R": "R",
    "C": "C",
    "P": "P",
}

# 棋子: (type, color) 或 None
Piece = Optional[Tuple[str, str]]
Board = List[List[Piece]]


def empty_board() -> Board:
    return [[None for _ in range(FILES)] for _ in range(RANKS)]


def piece_char(piece: Tuple[str, str]) -> str:
    ptype, color = piece
    ch = _TYPE_TO_FEN[ptype]
    return ch if color == "red" else ch.lower()


def board_to_fen(
    board: Board,
    side: str = "red",
    halfmove: int = 0,
    fullmove: int = 1,
) -> str:
    """把 9x10 棋盘矩阵转成完整 FEN 串。"""
    if len(board) != RANKS or any(len(row) != FILES for row in board):
        raise ValueError(f"board 形状必须是 {RANKS}x{FILES}")

    rank_strings: List[str] = []
    for r in range(RANKS):
        row = ""
        empty = 0
        for f in range(FILES):
            sq = board[r][f]
            if sq is None:
                empty += 1
            else:
                if empty > 0:
                    row += str(empty)
                    empty = 0
                row += piece_char(sq)
        if empty > 0:
            row += str(empty)
        rank_strings.append(row)

    side_char = "w" if side == "red" else "b"
    return f"{'/'.join(rank_strings)} {side_char} - - {halfmove} {fullmove}"
