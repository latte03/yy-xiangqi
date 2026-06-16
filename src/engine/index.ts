/**
 * 棋规引擎对外的统一入口
 * 这是 §3.3.3 "棋规引擎 API" 描述的对外接口
 */

import type { Color, EndState, Move } from '@/types';
import {
  applyMove,
  checkEnd,
  generateLegalMoves,
  isInCheck,
} from './legal';
import type { FenState } from './fen';
import { parseFen, toFen } from './fen';
import { generateMoves } from './rules/moves';

export {
  applyMove,
  checkEnd,
  generateLegalMoves,
  isInCheck,
  parseFen,
  toFen,
  generateMoves,
};

export type { FenState };

/** 走棋函数: 返回新 FenState, 若走法非法返回 null */
export function makeMove(state: FenState, move: Move): FenState | null {
  const newBoard = applyMove(state.board, move);
  // 检查是否送将
  const legal = generateLegalMoves(state.board, state.side);
  if (!legal.some((m) => m.from === move.from && m.to === move.to && m.piece.type === move.piece.type)) {
    return null;
  }
  const isCapture = move.captured !== undefined || move.piece.type === 'P';
  return {
    board: newBoard,
    side: state.side === 'red' ? 'black' : 'red',
    halfmove: isCapture ? 0 : state.halfmove + 1,
    fullmove: state.side === 'black' ? state.fullmove + 1 : state.fullmove,
  };
}

/** 便捷: 给定 FEN + 当前方, 求终局 */
export function endFromFen(fen: string, side: Color): EndState {
  const s = parseFen(fen);
  return checkEnd(s.board, side);
}