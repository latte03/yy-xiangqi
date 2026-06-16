/**
 * AI 引擎适配层 — Stockfish.js (Fairy-Stockfish 多变体)
 *
 * 通信模式: use-ai-engine.ts 把搜索请求 postMessage 给 worker,
 *           worker 内部 spawn stockfish.wasm.js 子 worker 通信。
 *
 * 走法字符串格式: Fairy-Stockfish Xiangqi UCI 坐标, e.g. "b1c3"。
 */

import type { Color } from '@/types';

export interface AiEngineOptions {
  fen: string;
  depth?: number;
  /** 暂未使用, Stockfish 用 'go depth' 而非 movetime */
  movetime?: number;
}

export interface AiMoveResult {
  move: string; // WXF 坐标, e.g. "h2e2"
  depth?: number;
  timeUsed: number;
}

/** 引擎无关接口 */
export interface AiEngine {
  search(options: AiEngineOptions): Promise<AiMoveResult>;
  readonly name: string;
}

/**
 * Fairy-Stockfish Xiangqi UCI 坐标 → 内部坐标
 *
 * Fairy-Stockfish 在 10 行棋盘上使用 1-10 的 rank, 且 rank 1 是红方底线。
 * 项目内部 board[0] 是黑方底线, board[9] 是红方底线, 所以 rank 需要翻转。
 *
 * 例: 引擎 "b1c3" = 红马 b10 到 c8 → 内部 (1, 9) 到 (2, 7)。
 */
export function parseXiangqiiMove(
  moveStr: string,
  _side: Color,
): { fromFile: number; fromRank: number; toFile: number; toRank: number } | null {
  const match = /^([a-i])([1-9]|10)([a-i])([1-9]|10)$/.exec(moveStr);
  if (!match) return null;

  const ff = match[1].charCodeAt(0) - 'a'.charCodeAt(0);
  const fr = 10 - Number(match[2]);
  const tf = match[3].charCodeAt(0) - 'a'.charCodeAt(0);
  const tr = 10 - Number(match[4]);

  if (ff < 0 || ff > 8 || tf < 0 || tf > 8) return null;
  if (fr < 0 || fr > 9 || tr < 0 || tr > 9) return null;
  return { fromFile: ff, fromRank: fr, toFile: tf, toRank: tr };
}
