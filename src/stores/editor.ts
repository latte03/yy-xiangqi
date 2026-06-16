/**
 * 摆棋编辑器状态 (Pinia store)
 * 与对局 store 解耦: 摆棋完成后再把 board 提交到对局 store
 *
 * 设计:
 *  - 棋盘快照 (Piece[][]) — 摆棋临时状态
 *  - 历史栈 (history: Board[]) — 撤销/重做
 *  - 当前选中的"调色板棋子" (palette: Piece | null) — 拖放前预设
 *  - 校验 (validation) — 硬校验 + 软警告
 */

import { defineStore } from 'pinia';
import { ref, computed, shallowRef } from 'vue';
import type { Board, Piece, Position, Color, PieceType } from '@/types';
import { emptyBoard } from '@/types';
import { parseFen, cloneBoard } from '@/engine/fen';
import { findKing, kingsFaceToFace } from '@/engine/legal';

const HISTORY_LIMIT = 50;

/** 校验结果 */
export interface ValidationResult {
  hardErrors: string[]; // 阻止提交的硬错误
  warnings: string[]; // 提示但不阻止的警告
}

export const useEditorStore = defineStore('editor', () => {
  /** 当前编辑中的棋盘 */
  const board = ref<Board>(emptyBoard());

  /** 撤销/重做历史 */
  const history = ref<Board[]>([]);
  const redoStack = ref<Board[]>([]);

  /** 当前调色板选中的棋子 (用于点击放置或拖放放置) */
  const palette = shallowRef<Piece | null>(null);

  /** 校验结果 (自动响应式) */
  const validation = computed<ValidationResult>(() => validate(board.value));

  function pushHistory() {
    history.value.push(cloneBoard(board.value));
    if (history.value.length > HISTORY_LIMIT) {
      history.value.shift();
    }
    // 任何新操作清空 redo 栈
    redoStack.value = [];
  }

  /** 设置某格棋子 (拖放/点击放置) */
  function setSquare(pos: Position, piece: Piece | null) {
    pushHistory();
    if (piece === null) {
      board.value[pos.rank][pos.file] = null;
    } else {
      board.value[pos.rank][pos.file] = { type: piece.type, color: piece.color };
    }
  }

  /** 移动棋子 (从 from 到 to, 覆盖 to) */
  function movePiece(from: Position, to: Position) {
    pushHistory();
    const piece = board.value[from.rank][from.file];
    if (!piece) return;
    board.value[to.rank][to.file] = piece;
    board.value[from.rank][from.file] = null;
  }

  /** 删除棋子 (拖到棋盘外或点击删除) */
  function deletePiece(pos: Position) {
    if (!board.value[pos.rank][pos.file]) return;
    pushHistory();
    board.value[pos.rank][pos.file] = null;
  }

  /** 清空棋盘 */
  function clearBoard() {
    pushHistory();
    board.value = emptyBoard();
  }

  /** 加载初始局面 */
  function loadInitial() {
    pushHistory();
    const s = parseFen('rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1');
    board.value = cloneBoard(s.board);
  }

  /** 加载自定义 FEN */
  function loadFen(fen: string) {
    pushHistory();
    try {
      const s = parseFen(fen);
      board.value = cloneBoard(s.board);
    } catch (e) {
      console.error('Invalid FEN:', e);
    }
  }

  function undo() {
    if (history.value.length === 0) return;
    redoStack.value.push(cloneBoard(board.value));
    board.value = history.value.pop()!;
  }

  function redo() {
    if (redoStack.value.length === 0) return;
    history.value.push(cloneBoard(board.value));
    board.value = redoStack.value.pop()!;
  }

  function selectPalettePiece(piece: Piece | null) {
    palette.value = piece;
  }

  function countPiece(type: PieceType, color: Color): number {
    let n = 0;
    for (let r = 0; r < 10; r++) {
      for (let f = 0; f < 9; f++) {
        const p = board.value[r][f];
        if (p && p.type === type && p.color === color) n++;
      }
    }
    return n;
  }

  return {
    board,
    history,
    redoStack,
    palette,
    validation,
    setSquare,
    movePiece,
    deletePiece,
    clearBoard,
    loadInitial,
    loadFen,
    undo,
    redo,
    selectPalettePiece,
    countPiece,
  };
});

/** 校验函数 (导出便于测试) */
export function validate(board: Board): ValidationResult {
  const hardErrors: string[] = [];
  const warnings: string[] = [];

  // 硬校验: 必须有双方将/帅
  const redKing = findKing(board, 'red');
  const blackKing = findKing(board, 'black');
  if (!redKing) hardErrors.push('缺少红帅');
  if (!blackKing) hardErrors.push('缺少黑将');
  if (!redKing || !blackKing) {
    return { hardErrors, warnings };
  }

  // 硬校验: 将帅不能照面
  if (kingsFaceToFace(board)) {
    hardErrors.push('将帅照面');
  }

  // 硬校验: 棋子不能超过总数上限 (车 2/炮 2/马 2/相 2/仕 2/兵 5)
  const limits: Record<PieceType, number> = {
    K: 1,
    A: 2,
    E: 2,
    H: 2,
    R: 2,
    C: 2,
    P: 5,
  };
  for (const color of ['red', 'black'] as Color[]) {
    for (const type of Object.keys(limits) as PieceType[]) {
      const limit = limits[type];
      let n = 0;
      for (let r = 0; r < 10; r++) {
        for (let f = 0; f < 9; f++) {
          const p = board[r][f];
          if (p && p.type === type && p.color === color) n++;
        }
      }
      if (n > limit) {
        hardErrors.push(`${color === 'red' ? '红' : '黑'}${typeName(type)} 数量过多 (${n} > ${limit})`);
      }
    }
  }

  // 软警告: 缺士象 (残局可缺, 但建议补)
  for (const color of ['red', 'black'] as Color[]) {
    const advisors = countPieceInBoard(board, 'A', color);
    const elephants = countPieceInBoard(board, 'E', color);
    if (advisors === 0 && elephants === 0) {
      warnings.push(`${color === 'red' ? '红' : '黑'}方缺士象`);
    }
  }

  // 软警告: 棋盘为空 (玩家还没摆)
  let total = 0;
  for (let r = 0; r < 10; r++) {
    for (let f = 0; f < 9; f++) {
      if (board[r][f]) total++;
    }
  }
  if (total < 4) warnings.push(`棋盘上只有 ${total} 个子 (残局一般 4-20 个)`);

  return { hardErrors, warnings };
}

function countPieceInBoard(board: Board, type: PieceType, color: Color): number {
  let n = 0;
  for (let r = 0; r < 10; r++) {
    for (let f = 0; f < 9; f++) {
      const p = board[r][f];
      if (p && p.type === type && p.color === color) n++;
    }
  }
  return n;
}

function typeName(type: PieceType): string {
  const names: Record<PieceType, string> = {
    K: '将帅',
    A: '仕',
    E: '相',
    H: '马',
    R: '车',
    C: '炮',
    P: '兵',
  };
  return names[type];
}