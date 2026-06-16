<script setup lang="ts">
/**
 * 棋盘组件 (Konva 10 + Vue 3.5)
 * 显示 9×10 棋盘 + 棋子 + 点击走棋
 */

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import Konva from 'konva';
import { useGameStore } from '@/stores/game';
import { generateLegalMoves } from '@/engine/legal';
import { endSummary as formatEndSummary } from '@/utils/end-state';
import {
  addPiece,
  CELL_SIZE,
  drawBoardLayer,
  FILES,
  HEIGHT,
  rankY,
  fileX,
  RANKS,
  screenToCell,
  WIDTH,
} from './board-drawing';

const game = useGameStore();

const containerRef = ref<HTMLDivElement | null>(null);
const selectedFrom = ref<{ file: number; rank: number } | null>(null);
const validTargets = ref<Array<{ file: number; rank: number }>>([]);
const lastAnimatedMoveCount = ref(0);
const endSummary = computed(() => formatEndSummary(game.endResult));

let stage: Konva.Stage | null = null;
let boardLayer: Konva.Layer | null = null;
let pieceLayer: Konva.Layer | null = null;
let hintLayer: Konva.Layer | null = null;

function drawBoard() {
  if (!boardLayer) return;
  drawBoardLayer(boardLayer);
}

function drawPieces() {
  if (!pieceLayer) return;
  pieceLayer.destroyChildren();
  for (let r = 0; r < RANKS; r++) {
    for (let f = 0; f < FILES; f++) {
      const p = game.board[r][f];
      if (!p) continue;
      const isSelected =
        selectedFrom.value?.file === f && selectedFrom.value?.rank === r;
      const pieceNode = addPiece(pieceLayer, p, f, r, isSelected);
      const lastMove = game.lastMove;
      const moveCount = game.moves.length;
      const shouldAnimate =
        lastMove &&
        moveCount > 0 &&
        moveCount !== lastAnimatedMoveCount.value &&
        lastMove.to.file === f &&
        lastMove.to.rank === r &&
        lastMove.piece.type === p.type &&
        lastMove.piece.color === p.color;

      if (shouldAnimate) {
        lastAnimatedMoveCount.value = moveCount;
        pieceNode.position({
          x: fileX(lastMove.from.file),
          y: rankY(lastMove.from.rank),
        });
        pieceNode.to({
          x: fileX(f),
          y: rankY(r),
          duration: 0.24,
          easing: Konva.Easings.EaseOut,
        });
      }
    }
  }
  pieceLayer.batchDraw();
}

function drawHints() {
  if (!hintLayer) return;
  hintLayer.destroyChildren();
  for (const t of validTargets.value) {
    hintLayer.add(new Konva.Circle({
      x: fileX(t.file),
      y: rankY(t.rank),
      radius: 9,
      fill: 'rgba(40, 116, 86, 0.72)',
      stroke: '#e7c56d',
      strokeWidth: 2,
    }));
  }
  // 被将军提示: 给将/帅加红圈
  if (game.inCheck) {
    for (let r = 0; r < RANKS; r++) {
      for (let f = 0; f < FILES; f++) {
        const p = game.board[r][f];
        if (p && p.type === 'K') {
          hintLayer.add(new Konva.Circle({
            x: fileX(f),
            y: rankY(r),
            radius: CELL_SIZE * 0.45,
            stroke: '#d84c38',
            strokeWidth: 4,
            fill: 'transparent',
          }));
        }
      }
    }
  }
  hintLayer.batchDraw();
}

function onBoardClick(evt: Konva.KonvaEventObject<MouseEvent>) {
  if (game.aiThinking) return;
  if (game.ended) return;
  const stage = evt.target.getStage();
  if (!stage) return;
  const pos = stage.getPointerPosition();
  if (!pos) return;
  const cell = screenToCell(pos.x, pos.y);
  if (!cell) return;
  const { file: f, rank: r } = cell;

  const piece = game.board[r][f];

  // 1) 如果已选起点 + 点击合法目标 → 走棋
  if (selectedFrom.value) {
    const isValidTarget = validTargets.value.some(
      (t) => t.file === f && t.rank === r,
    );
    if (isValidTarget) {
      game.playerMove(selectedFrom.value, { file: f, rank: r });
      selectedFrom.value = null;
      validTargets.value = [];
      return;
    }
  }

  // 2) 否则: 选中己方棋子 → 计算可走点
  if (piece && piece.color === game.side && game.side !== game.aiSide) {
    selectedFrom.value = { file: f, rank: r };
    const legal = generateLegalMoves(game.board, game.side);
    validTargets.value = legal
      .filter((m) => m.from.file === f && m.from.rank === r)
      .map((m) => ({ file: m.to.file, rank: m.to.rank }));
  } else {
    selectedFrom.value = null;
    validTargets.value = [];
  }
  drawPieces();
  drawHints();
}

onMounted(() => {
  if (!containerRef.value) return;
  stage = new Konva.Stage({
    container: containerRef.value,
    width: WIDTH,
    height: HEIGHT,
  });
  boardLayer = new Konva.Layer();
  pieceLayer = new Konva.Layer();
  hintLayer = new Konva.Layer();
  stage.add(boardLayer);
  stage.add(pieceLayer);
  stage.add(hintLayer);
  stage.on('click', onBoardClick);
  drawBoard();
  drawPieces();
  drawHints();
});

watch(
  () => game.board,
  () => {
    drawPieces();
    drawHints();
  },
  { deep: true },
);

watch(
  () => game.inCheck,
  () => {
    drawHints();
  },
);

watch(
  () => game.ended,
  (ended) => {
    if (!ended) return;
    selectedFrom.value = null;
    validTargets.value = [];
    drawPieces();
    drawHints();
  },
);

onBeforeUnmount(() => {
  stage?.destroy();
});
</script>

<template>
  <div class="board-wrapper" :class="{ 'is-ended': game.ended }">
    <div ref="containerRef" class="board-canvas" :style="{ width: WIDTH + 'px', height: HEIGHT + 'px' }" />
    <div v-if="game.aiThinking && !game.ended" class="ai-badge">
      <span>AI 思考中…</span>
    </div>
    <div v-if="game.ended" class="end-overlay" aria-live="polite">
      <strong>本局结束</strong>
      <span>{{ endSummary }}</span>
    </div>
    <div v-if="game.lastAiError" class="ai-error">
      AI 错误：{{ game.lastAiError }}
    </div>
  </div>
</template>

<style scoped>
.board-wrapper {
  position: relative;
  display: inline-block;
  max-width: 100%;
}
.board-canvas {
  max-width: 100%;
  overflow: hidden;
  border: 1px solid rgba(245, 203, 128, 0.32);
  border-radius: 20px;
  cursor: pointer;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.36);
  transition: filter 200ms ease, opacity 200ms ease;
}
.board-wrapper.is-ended .board-canvas {
  filter: grayscale(0.9) saturate(0.15) brightness(0.62);
  opacity: 0.72;
  cursor: default;
}
.ai-badge {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 2;
  padding: 8px 11px;
  border: 1px solid rgba(88, 220, 175, 0.28);
  border-radius: 999px;
  background: rgba(25, 55, 45, 0.82);
  color: #f7e8c7;
  font-size: 13px;
  font-weight: 700;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(8px);
  pointer-events: none;
}
.end-overlay {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: grid;
  place-content: center;
  gap: 10px;
  border-radius: 20px;
  background: rgba(10, 10, 10, 0.42);
  color: #f6ead4;
  text-align: center;
  pointer-events: none;
}
.end-overlay strong {
  display: block;
  font-family: "Songti SC", "STSong", serif;
  font-size: clamp(38px, 7vw, 72px);
  line-height: 1;
  letter-spacing: 0;
}
.end-overlay span {
  justify-self: center;
  max-width: min(360px, calc(100% - 48px));
  padding: 8px 12px;
  border: 1px solid rgba(255, 232, 184, 0.24);
  border-radius: 999px;
  background: rgba(20, 18, 16, 0.76);
  color: #ffe9bd;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
}
.ai-error {
  margin-top: 8px;
  padding: 8px;
  background: rgba(155, 51, 35, 0.18);
  color: #ffb29e;
  border: 1px solid rgba(255, 127, 102, 0.28);
  border-radius: 8px;
  font-size: 13px;
}
</style>
