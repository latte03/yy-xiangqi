/**
 * AI 引擎对外入口
 *
 * 引擎: Stockfish.js (Fairy-Stockfish 多变体支持)
 * 通信: Vue composable (主线程) → ai/worker.ts → stockfish.wasm.js 子 worker
 */

export { parseXiangqiiMove } from './engine';
export type { AiEngine, AiEngineOptions, AiMoveResult } from './engine';
export { useAiEngine } from './use-ai-engine';