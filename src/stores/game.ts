/**
 * 对局状态 Pinia store
 * 把棋规引擎 + AI 引擎 + UI 状态串起来
 */

import { defineStore } from 'pinia';
import { ref, computed, shallowRef } from 'vue';
import { INITIAL_FEN, type Color, type EndReason, type Move } from '@/types';
import { parseFen, toFen, cloneBoard } from '@/engine/fen';
import {
  applyMove,
  checkEnd,
  generateLegalMoves,
  isInCheck,
} from '@/engine/legal';
import { useAiEngine } from '@/ai/use-ai-engine';
import { parseXiangqiiMove } from '@/ai/engine';

export interface Settings {
  difficulty: 'easy' | 'medium' | 'hard' | 'expert';
  side: 'ai-red' | 'human-red';
}

const MOVE_ANIMATION_DELAY_MS = 280;

export const useGameStore = defineStore('game', () => {
  const initialState = parseFen(INITIAL_FEN);

  const board = ref(cloneBoard(initialState.board));
  const side = ref<Color>(initialState.side);
  const halfmove = ref(initialState.halfmove);
  const fullmove = ref(initialState.fullmove);
  const moves = ref<string[]>([]);
  const lastMove = shallowRef<Move | null>(null);
  const lastAiError = shallowRef<string | null>(null);
  const aiThinking = ref(false);
  const ended = ref(false);
  const endResult = shallowRef<{ winner?: Color; reason?: EndReason } | null>(null);
  const inCheck = ref(false);

  const settings = ref<Settings>({
    difficulty: 'medium',
    side: 'human-red',
  });

  const fen = computed(() =>
    toFen({
      board: board.value,
      side: side.value,
      halfmove: halfmove.value,
      fullmove: fullmove.value,
    }),
  );

  const aiSide = computed<Color>(() => (settings.value.side === 'ai-red' ? 'red' : 'black'));
  const humanSide = computed<Color>(() => (aiSide.value === 'red' ? 'black' : 'red'));

  const ai = useAiEngine();
  let aiDelayTimer: ReturnType<typeof setTimeout> | null = null;
  let aiRequestId = 0;

  function clearAiDelayTimer() {
    if (!aiDelayTimer) return;
    clearTimeout(aiDelayTimer);
    aiDelayTimer = null;
  }

  function cancelPendingAiWork() {
    clearAiDelayTimer();
    aiRequestId += 1;
    aiThinking.value = false;
  }

  function maybeRequestAiMove() {
    if (!ended.value && side.value === aiSide.value) {
      void requestAiMove();
    }
  }

  function scheduleAiMoveAfterAnimation() {
    clearAiDelayTimer();
    aiDelayTimer = setTimeout(() => {
      aiDelayTimer = null;
      maybeRequestAiMove();
    }, MOVE_ANIMATION_DELAY_MS);
  }

  function applyMoveAndCheck(move: Move): boolean {
    const legal = generateLegalMoves(board.value, side.value);
    const isLegal = legal.some(
      (m) =>
        m.from.file === move.from.file &&
        m.from.rank === move.from.rank &&
        m.to.file === move.to.file &&
        m.to.rank === move.to.rank &&
        m.piece.type === move.piece.type,
    );
    if (!isLegal) return false;
    lastMove.value = move;
    board.value = applyMove(board.value, move);
    const isCapture = !!move.captured || move.piece.type === 'P';
    if (isCapture) {
      halfmove.value = 0;
    } else {
      halfmove.value += 1;
    }
    if (side.value === 'black') fullmove.value += 1;
    side.value = side.value === 'red' ? 'black' : 'red';
    moves.value.push(formatMove(move));
    inCheck.value = isInCheck(board.value, side.value);
    const end = checkEnd(board.value, side.value);
    if (end.ended) {
      ended.value = true;
      endResult.value = { winner: end.winner, reason: end.reason };
    }
    return true;
  }

  function formatMove(m: Move): string {
    const fromFile = String.fromCharCode(97 + m.from.file);
    const fromRank = m.from.rank + 1;
    const toFile = String.fromCharCode(97 + m.to.file);
    const toRank = m.to.rank + 1;
    return `${fromFile}${fromRank}${toFile}${toRank}`;
  }

  async function requestAiMove() {
    if (ended.value) return;
    if (side.value !== aiSide.value) return;
    const requestId = ++aiRequestId;
    aiThinking.value = true;
    lastAiError.value = null;
    const depthMap: Record<Settings['difficulty'], number> = {
      easy: 2,
      medium: 4,
      hard: 6,
      expert: 8,
    };
    try {
      const result = await ai.askBestMove({
        fen: fen.value,
        depth: depthMap[settings.value.difficulty],
      });
      if (requestId !== aiRequestId || ended.value || side.value !== aiSide.value) return;
      const parsed = parseXiangqiiMove(result.move, side.value);
      if (!parsed) throw new Error(`AI returned invalid move: ${result.move}`);
      const piece = board.value[parsed.fromRank][parsed.fromFile];
      if (!piece) throw new Error(`AI returned move from empty square: ${result.move}`);
      const move: Move = {
        from: { file: parsed.fromFile, rank: parsed.fromRank },
        to: { file: parsed.toFile, rank: parsed.toRank },
        piece,
        captured: board.value[parsed.toRank][parsed.toFile] ?? undefined,
      };
      applyMoveAndCheck(move);
    } catch (err) {
      if (requestId !== aiRequestId) return;
      lastAiError.value = err instanceof Error ? err.message : String(err);
    } finally {
      if (requestId === aiRequestId) {
        aiThinking.value = false;
      }
    }
  }

  function startNewGame() {
    resetToInitial();
    maybeRequestAiMove();
  }

  /**
   * 应用自定义摆棋结果 (从 editor 提交)
   * FEN 字符串包含棋盘和当前走子方。
   * 走法历史清空, 再根据当前走子方决定是否触发 AI。
   */
  function applyCustomPosition(fen: string) {
    cancelPendingAiWork();
    const s = parseFen(fen);
    board.value = cloneBoard(s.board);
    side.value = s.side;
    halfmove.value = s.halfmove;
    fullmove.value = s.fullmove;
    moves.value = [];
    lastMove.value = null;
    ended.value = false;
    endResult.value = null;
    inCheck.value = isInCheck(board.value, side.value);
    maybeRequestAiMove();
  }

  function resetToInitial() {
    cancelPendingAiWork();
    const s = parseFen(INITIAL_FEN);
    board.value = cloneBoard(s.board);
    side.value = s.side;
    halfmove.value = s.halfmove;
    fullmove.value = s.fullmove;
    moves.value = [];
    lastMove.value = null;
    ended.value = false;
    endResult.value = null;
    inCheck.value = false;
  }

  function playerMove(from: { file: number; rank: number }, to: { file: number; rank: number }) {
    if (ended.value) return;
    if (side.value === aiSide.value) return; // 玩家不能在 AI 回合走棋
    const piece = board.value[from.rank][from.file];
    if (!piece) return;
    const move: Move = {
      from,
      to,
      piece,
      captured: board.value[to.rank][to.file] ?? undefined,
    };
    if (applyMoveAndCheck(move)) {
      // 玩家走完后, 触发 AI 走棋
      if (!ended.value && side.value === aiSide.value) {
        scheduleAiMoveAfterAnimation();
      }
    }
  }

  function resignGame() {
    if (ended.value) return;
    cancelPendingAiWork();
    ended.value = true;
    endResult.value = { winner: aiSide.value, reason: 'resign' };
    lastAiError.value = null;
  }

  return {
    board,
    side,
    halfmove,
    fullmove,
    moves,
    lastMove,
    settings,
    fen,
    aiSide,
    humanSide,
    aiThinking,
    ended,
    endResult,
    inCheck,
    lastAiError,
    startNewGame,
    resetToInitial,
    applyCustomPosition,
    playerMove,
    requestAiMove,
    resignGame,
  };
});
