/**
 * 合法性判定: 是否送将 / 是否困毙 / 终局判定
 */

import type { Board, Color, EndState, Move, Position } from '@/types';
import { generateMoves } from './rules/moves';
import { cloneBoard } from '@/engine/fen';

export function findKing(board: Board, color: Color): Position | null {
  for (let r = 0; r < 10; r++) {
    for (let f = 0; f < 9; f++) {
      const sq = board[r][f];
      if (sq && sq.type === 'K' && sq.color === color) return { file: f, rank: r };
    }
  }
  return null;
}

/** 双方将/帅是否"对脸" (同 file 且中间无子) */
export function kingsFaceToFace(board: Board): boolean {
  const rk = findKing(board, 'red');
  const bk = findKing(board, 'black');
  if (!rk || !bk) return false;
  if (rk.file !== bk.file) return false;
  const between = rk.rank > bk.rank ? bk.rank + 1 : rk.rank + 1;
  const end = rk.rank > bk.rank ? rk.rank - 1 : bk.rank - 1;
  for (let r = between; r <= end; r++) {
    if (board[r][rk.file] !== null) return false;
  }
  return true;
}

/** 走法是否送将 (走完后己方将/帅被攻击) */
export function isLegalMove(board: Board, move: Move, color: Color): boolean {
  const after = applyMove(board, move);
  // 走完后若己方将/帅被对方任何走法攻击 → 非法
  const myKing = findKing(after, color);
  if (!myKing) return false;
  // 如果走完后双方对脸, 也视为己方被将
  if (kingsFaceToFace(after)) return false;
  // 检查对方所有走法是否能吃到己方将/帅
  const oppMoves = generateMoves(after, color === 'red' ? 'black' : 'red');
  for (const m of oppMoves) {
    if (m.to.file === myKing.file && m.to.rank === myKing.rank) {
      return false;
    }
  }
  return true;
}

/** 应用走法, 返回新 board (不可变, 复用输入) */
export function applyMove(board: Board, move: Move): Board {
  const nb = cloneBoard(board);
  nb[move.to.rank][move.to.file] = nb[move.from.rank][move.from.file];
  nb[move.from.rank][move.from.file] = null;
  return nb;
}

/** 列出某方所有合法走法 (经过送将过滤) */
export function generateLegalMoves(board: Board, color: Color): Move[] {
  const all = generateMoves(board, color);
  return all.filter((m) => isLegalMove(board, m, color));
}

/**
 * 终局判定
 * @returns ended=true 时 winner/reason 有值
 */
export function checkEnd(board: Board, side: Color): EndState {
  const legal = generateLegalMoves(board, side);
  if (legal.length === 0) {
    // 无合法走法 → 看是否被将
    const oppMoves = generateMoves(board, side === 'red' ? 'black' : 'red');
    const myKing = findKing(board, side);
    if (myKing) {
      const inCheck = oppMoves.some(
        (m) => m.to.file === myKing.file && m.to.rank === myKing.rank,
      );
      return {
        ended: true,
        winner: side === 'red' ? 'black' : 'red',
        reason: inCheck ? 'checkmate' : 'stalemate',
      };
    }
  }
  return { ended: false };
}

/** 是否被将军 (用于 UI 提示红/黄边框) */
export function isInCheck(board: Board, color: Color): boolean {
  const king = findKing(board, color);
  if (!king) return false;
  const oppMoves = generateMoves(board, color === 'red' ? 'black' : 'red');
  return oppMoves.some((m) => m.to.file === king.file && m.to.rank === king.rank);
}