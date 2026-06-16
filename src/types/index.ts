/**
 * 中国象棋核心类型定义
 *
 * 棋盘坐标: file 0-8 (从红方左侧数, 红方在下、视角 = "我方在下方"),
 *          rank 0-9 (0 = 黑方底线, 9 = 红方底线)
 * 颜色: red (下、先手) / black (上、后手)
 * 棋子类型: K(帅/将) A(仕/士) E(相/象) H(马) R(车) C(炮) P(兵/卒)
 */

export type Color = 'red' | 'black';
export type PieceType = 'K' | 'A' | 'E' | 'H' | 'R' | 'C' | 'P';

export interface Piece {
  type: PieceType;
  color: Color;
}

export type Square = Piece | null;

/** Board is 9 files × 10 ranks, indexed board[rank][file] */
export type Board = Square[][];

export interface Position {
  file: number; // 0..8
  rank: number; // 0..9
}

export interface Move {
  from: Position;
  to: Position;
  piece: Piece;
  captured?: Piece;
}

/** 终局原因 */
export type EndReason =
  | 'checkmate' // 将死
  | 'stalemate' // 困毙 (无子可走)
  | 'repetition' // 重复局面
  | 'fifty-move' // 60 回合自然限着
  | 'resign' // 认输
  | 'timeout'; // 超时

export interface EndState {
  ended: boolean;
  winner?: Color;
  reason?: EndReason;
}

export const FILES = 9;
export const RANKS = 10;

export const INITIAL_FEN =
  'rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1';

export function inBounds(file: number, rank: number): boolean {
  return file >= 0 && file < FILES && rank >= 0 && rank < RANKS;
}

export function emptyBoard(): Board {
  return Array.from({ length: RANKS }, () => Array<Square>(FILES).fill(null));
}

export function pieceChar(p: Piece): string {
  // WXF 风格 FEN: K(将) A(仕) B(相) N(马) R(车) C(炮) P(兵)
  // 大写 = 红方, 小写 = 黑方
  const map: Record<PieceType, string> = {
    K: 'K',
    A: 'A',
    E: 'B',
    H: 'N',
    R: 'R',
    C: 'C',
    P: 'P',
  };
  return p.color === 'red' ? map[p.type] : map[p.type].toLowerCase();
}

export function opponent(c: Color): Color {
  return c === 'red' ? 'black' : 'red';
}