/**
 * FEN (Forsyth-Edwards Notation) for Chinese Chess
 * 标准 WXF/UCCI 风格 FEN
 *
 * 格式: <board> <side> <en-passant> <halfmove> <fullmove>
 * 例: "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
 *
 * board: rank 9 (黑底线) → rank 0 (红底线)，每行从 file 0 开始
 * 大写 = 红方，小写 = 黑方
 */

import type { Board, Color, Piece, Square } from '@/types';
import { FILES, RANKS, emptyBoard, pieceChar } from '@/types';

const PIECE_CHARS: Record<string, Piece> = {
  K: { type: 'K', color: 'red' },
  A: { type: 'A', color: 'red' },
  E: { type: 'E', color: 'red' },
  B: { type: 'E', color: 'red' }, // 别名: 某些 FEN 用 B 表示相 (Bishop 风格)
  N: { type: 'H', color: 'red' }, // 别名: WXF 风格 FEN 用 N 表示马 (knight 风格)
  H: { type: 'H', color: 'red' },
  R: { type: 'R', color: 'red' },
  C: { type: 'C', color: 'red' },
  P: { type: 'P', color: 'red' },
  k: { type: 'K', color: 'black' },
  a: { type: 'A', color: 'black' },
  e: { type: 'E', color: 'black' },
  b: { type: 'E', color: 'black' }, // 别名
  n: { type: 'H', color: 'black' }, // 别名
  h: { type: 'H', color: 'black' },
  r: { type: 'R', color: 'black' },
  c: { type: 'C', color: 'black' },
  p: { type: 'P', color: 'black' },
};

export interface FenState {
  board: Board;
  side: Color;
  halfmove: number; // 自上次吃子/动兵以来的半回合数
  fullmove: number; // 总回合数
}

export function parseFen(fen: string): FenState {
  const [boardPart, sidePart = 'w', , , halfmovePart = '0', fullmovePart = '1'] =
    fen.trim().split(/\s+/);

  const board = emptyBoard();
  const ranks = boardPart.split('/');
  if (ranks.length !== RANKS) {
    throw new Error(`Invalid FEN: expected ${RANKS} ranks, got ${ranks.length}`);
  }

  for (let r = 0; r < RANKS; r++) {
    // FEN rank 0 是黑底线 → 我们内部 board 索引 0 也是黑底线
    const row = ranks[r];
    let file = 0;
    for (const ch of row) {
      if (/[1-9]/.test(ch)) {
        file += parseInt(ch, 10);
      } else if (PIECE_CHARS[ch]) {
        board[r][file] = PIECE_CHARS[ch];
        file++;
      } else {
        throw new Error(`Invalid FEN char at rank ${r}, file ${file}: ${ch}`);
      }
    }
    if (file !== FILES) {
      throw new Error(`Invalid FEN: rank ${r} has ${file} files, expected ${FILES}`);
    }
  }

  return {
    board,
    side: sidePart === 'b' ? 'black' : 'red',
    halfmove: parseInt(halfmovePart, 10) || 0,
    fullmove: parseInt(fullmovePart, 10) || 1,
  };
}

export function toFen(state: FenState): string {
  const rankStrings: string[] = [];
  for (let r = 0; r < RANKS; r++) {
    let row = '';
    let empty = 0;
    for (let f = 0; f < FILES; f++) {
      const sq = state.board[r][f];
      if (sq === null) {
        empty++;
      } else {
        if (empty > 0) {
          row += String(empty);
          empty = 0;
        }
        row += pieceChar(sq);
      }
    }
    if (empty > 0) row += String(empty);
    rankStrings.push(row);
  }
  return `${rankStrings.join('/')} ${state.side === 'red' ? 'w' : 'b'} - - ${state.halfmove} ${state.fullmove}`;
}

export function cloneBoard(board: Board): Board {
  return board.map((rank) => rank.map((sq) => (sq ? { ...sq } : null)));
}

export function squareAt(
  board: Board,
  file: number,
  rank: number,
): Square {
  return board[rank][file];
}