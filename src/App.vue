<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue';
import {
  NButton,
  NConfigProvider,
  NSelect,
  NStatistic,
  NTag,
  darkTheme,
} from 'naive-ui';
import ChessBoard from './components/board/ChessBoard.vue';
import Editor from './components/editor/Editor.vue';
import { useGameStore } from './stores/game';
import type { Color, EndReason } from './types';

const game = useGameStore();

type Screen = 'home' | 'editor' | 'play';
type Entry = 'standard' | 'custom';

const screen = ref<Screen>('home');
const activeEntry = ref<Entry>('standard');
const showCheckNotice = shallowRef(false);

const difficultyOptions = [
  { label: '入门 depth 2', value: 'easy' },
  { label: '业余 depth 4', value: 'medium' },
  { label: '进阶 depth 6', value: 'hard' },
  { label: '挑战 depth 8', value: 'expert' },
];

const sideOptions = [
  { label: '玩家执红，AI 执黑', value: 'human-red' },
  { label: '玩家执黑，AI 执红', value: 'ai-red' },
];

const entryTitle = computed(() => (activeEntry.value === 'standard' ? '普通对战' : '自定义残局'));
const humanSideLabel = computed(() => (game.humanSide === 'red' ? '红方' : '黑方'));
const aiSideLabel = computed(() => (game.aiSide === 'red' ? '红方' : '黑方'));
const currentTurnLabel = computed(() => {
  if (game.ended) return '本局已结束';
  const side = game.side === 'red' ? '红方' : '黑方';
  if (game.aiThinking) return 'AI 思考中';
  return `${side}${game.side === game.aiSide ? '（AI）' : '（玩家）'}`;
});
const movePairs = computed(() => game.moves.map((move, index) => ({
  index,
  label: `${index % 2 === 0 ? `${Math.floor(index / 2) + 1}. ` : ''}${move}`,
})));
const endReasonLabels: Record<EndReason, string> = {
  checkmate: '将死',
  stalemate: '困毙',
  repetition: '重复局面',
  'fifty-move': '自然限着',
  resign: '认输',
  timeout: '超时',
};
const resultReasonLabel = computed(() => {
  const reason = game.endResult?.reason;
  return reason ? endReasonLabels[reason] : '终局';
});
const resultWinnerLabel = computed(() => {
  const winner = game.endResult?.winner;
  if (!winner) return '和棋';
  return `${sideLabel(winner)}胜`;
});

let checkNoticeTimer: ReturnType<typeof setTimeout> | null = null;

function sideLabel(side: Color) {
  return side === 'red' ? '红方' : '黑方';
}

function flashCheckNotice() {
  if (checkNoticeTimer) {
    clearTimeout(checkNoticeTimer);
  }
  showCheckNotice.value = true;
  checkNoticeTimer = setTimeout(() => {
    showCheckNotice.value = false;
    checkNoticeTimer = null;
  }, 1000);
}

function hideCheckNotice() {
  if (checkNoticeTimer) {
    clearTimeout(checkNoticeTimer);
    checkNoticeTimer = null;
  }
  showCheckNotice.value = false;
}

function startStandardGame() {
  activeEntry.value = 'standard';
  game.startNewGame();
  screen.value = 'play';
}

function openCustomEditor() {
  game.cancelPendingAiMove();
  hideCheckNotice();
  activeEntry.value = 'custom';
  screen.value = 'editor';
}

function onCustomSubmitted() {
  activeEntry.value = 'custom';
  screen.value = 'play';
}

function goHome() {
  game.cancelPendingAiMove();
  hideCheckNotice();
  screen.value = 'home';
}

function restartCurrent() {
  if (activeEntry.value === 'standard') {
    startStandardGame();
    return;
  }
  game.cancelPendingAiMove();
  hideCheckNotice();
  screen.value = 'editor';
}

watch(
  () => game.inCheck,
  (isInCheck) => {
    if (isInCheck && screen.value === 'play' && !game.ended) {
      flashCheckNotice();
    }
  },
);

watch(
  () => game.ended,
  (ended) => {
    if (ended) {
      hideCheckNotice();
    }
  },
);

onBeforeUnmount(() => {
  hideCheckNotice();
});
</script>

<template>
  <NConfigProvider :theme="darkTheme">
    <div class="app-shell">
      <header class="topbar">
        <button class="brand" type="button" @click="goHome">
          <span class="brand-mark">象</span>
          <span>
            <strong>残局工坊</strong>
            <small>xiangqi lab</small>
          </span>
        </button>

        <div v-if="screen !== 'home'" class="topbar-actions">
          <NTag :bordered="false" type="warning">{{ entryTitle }}</NTag>
          <NButton size="small" secondary @click="goHome">返回入口</NButton>
        </div>
      </header>

      <main class="main-stage">
        <section v-if="screen === 'home'" class="entry-screen">
          <div class="entry-copy">
            <p class="eyebrow">中国象棋 · 人机练习</p>
            <h1>选择一种开局方式</h1>
            <p class="lead">直接下完整棋局，或者先摆出目标残局，再交给 AI 和你对弈。</p>
          </div>

          <div class="entry-grid">
            <article class="entry-card standard-entry">
              <span class="entry-number">01</span>
              <h2>普通对战</h2>
              <p>从标准初始局面开始，按执方设置决定玩家或 AI 执红。</p>
              <div class="entry-settings">
                <label>
                  <span>AI 难度</span>
                  <NSelect v-model:value="game.settings.difficulty" :options="difficultyOptions" />
                </label>
                <label>
                  <span>执方</span>
                  <NSelect v-model:value="game.settings.side" :options="sideOptions" />
                </label>
              </div>
              <NButton type="primary" size="large" block @click="startStandardGame">
                进入普通对战
              </NButton>
            </article>

            <article class="entry-card custom-entry">
              <span class="entry-number">02</span>
              <h2>自定义残局</h2>
              <p>先摆棋、校验局面，再选择玩家执方和首手归属。</p>
              <div class="entry-notes">
                <span>支持撤销重做</span>
                <span>自动校验将帅</span>
                <span>提交后接入 AI</span>
              </div>
              <NButton type="primary" size="large" block @click="openCustomEditor">
                进入摆棋工坊
              </NButton>
            </article>
          </div>
        </section>

        <section v-else-if="screen === 'editor'" class="editor-screen">
          <div class="section-heading">
            <p class="eyebrow">setup board</p>
            <h1>摆棋工坊</h1>
            <p>放置或删除棋子，检查合法性后进入对战。</p>
          </div>
          <Editor @submitted="onCustomSubmitted" />
        </section>

        <section v-else class="play-screen">
          <div class="table-header">
            <div>
              <p class="eyebrow">match table</p>
              <h1>{{ entryTitle }}</h1>
            </div>
            <div class="match-actions">
              <NButton secondary @click="restartCurrent">
                {{ activeEntry === 'standard' ? '重新开局' : '重新摆棋' }}
              </NButton>
              <NButton type="error" secondary :disabled="game.ended" @click="game.resignGame">
                认输
              </NButton>
              <NButton tertiary @click="goHome">换入口</NButton>
            </div>
          </div>

          <div class="play-layout">
            <section class="board-panel">
              <div class="board-panel-head">
                <NTag :bordered="false" :type="game.side === game.aiSide ? 'info' : 'success'">
                  当前：{{ currentTurnLabel }}
                </NTag>
                <NTag v-if="game.inCheck" :bordered="false" type="error">将军</NTag>
              </div>
              <ChessBoard />
            </section>

            <aside class="match-panel">
              <div class="stats-grid">
                <NStatistic label="玩家执方" :value="humanSideLabel" />
                <NStatistic label="AI 执方" :value="aiSideLabel" />
                <NStatistic label="回合数" :value="game.fullmove" />
                <NStatistic label="限着" :value="game.halfmove" />
              </div>

              <div v-if="game.ended" class="result-box">
                <strong>终局</strong>
                <span>
                  {{ resultReasonLabel }} · {{ resultWinnerLabel }}
                </span>
              </div>

              <section class="move-log">
                <div class="panel-title">
                  <h2>走法记录</h2>
                  <span>{{ game.moves.length }} 手</span>
                </div>
                <div class="moves">
                  <span v-if="movePairs.length === 0" class="empty">等待第一手</span>
                  <span v-for="move in movePairs" :key="move.index" class="move">
                    {{ move.label }}
                  </span>
                </div>
              </section>

              <details class="fen-panel">
                <summary>FEN</summary>
                <code>{{ game.fen }}</code>
              </details>
            </aside>
          </div>
        </section>
      </main>

      <Transition name="check-notice">
        <div v-if="showCheckNotice" class="check-notice" aria-live="assertive">
          <span>将军</span>
        </div>
      </Transition>
    </div>
  </NConfigProvider>
</template>

<style scoped>
.app-shell {
  min-height: 100dvh;
  color: #f6ead4;
}

.topbar {
  width: min(1240px, calc(100vw - 40px));
  margin: 0 auto;
  padding: 24px 0 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.brand-mark {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: linear-gradient(145deg, #bd7041, #ecd097);
  color: #351b0e;
  font-family: "Songti SC", serif;
  font-size: 28px;
  font-weight: 800;
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28);
}

.brand strong {
  display: block;
  font-size: 17px;
  letter-spacing: 0;
}

.brand small {
  display: block;
  margin-top: 2px;
  color: #ac9b80;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.topbar-actions,
.match-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.main-stage {
  width: min(1240px, calc(100vw - 40px));
  margin: 0 auto;
  padding: 28px 0 54px;
}

.entry-screen {
  min-height: calc(100dvh - 150px);
  display: grid;
  align-content: center;
  gap: 34px;
}

.entry-copy,
.section-heading {
  max-width: 720px;
}

.eyebrow {
  margin: 0 0 10px;
  color: #d2aa70;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  color: #fff5df;
  font-size: clamp(36px, 6vw, 72px);
  line-height: 0.96;
  letter-spacing: 0;
  text-wrap: balance;
}

h2 {
  color: #fff0d3;
  font-size: 28px;
  line-height: 1.1;
  letter-spacing: 0;
}

.lead,
.section-heading p {
  margin-top: 16px;
  max-width: 620px;
  color: #bba88a;
  font-size: 17px;
  line-height: 1.7;
}

.entry-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 18px;
}

.entry-card {
  position: relative;
  min-height: 330px;
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  border: 1px solid rgba(236, 202, 142, 0.18);
  border-radius: 18px;
  background:
    linear-gradient(150deg, rgba(255, 244, 214, 0.11), rgba(255, 244, 214, 0.03)),
    rgba(27, 20, 16, 0.76);
  box-shadow: 0 22px 70px rgba(0, 0, 0, 0.24);
  overflow: hidden;
}

.entry-card::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(90deg, rgba(255, 255, 255, 0.06) 1px, transparent 1px),
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 58px 58px;
  opacity: 0.18;
  pointer-events: none;
}

.entry-card > * {
  position: relative;
}

.entry-number {
  color: #d2aa70;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
}

.entry-card p {
  max-width: 480px;
  color: #bda98b;
  line-height: 1.65;
}

.entry-settings {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: auto;
}

.entry-settings label {
  display: grid;
  gap: 6px;
}

.entry-settings span,
.entry-notes span {
  color: #d8c4a2;
  font-size: 12px;
}

.entry-notes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: auto;
}

.entry-notes span {
  padding: 6px 9px;
  border: 1px solid rgba(236, 202, 142, 0.18);
  border-radius: 8px;
  background: rgba(255, 244, 214, 0.07);
}

.editor-screen {
  display: grid;
  gap: 24px;
}

.play-screen {
  display: grid;
  gap: 18px;
}

.table-header {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
}

.table-header h1 {
  font-size: clamp(32px, 4vw, 52px);
}

.play-layout {
  display: grid;
  grid-template-columns: minmax(540px, auto) minmax(300px, 360px);
  gap: 22px;
  align-items: start;
}

.board-panel,
.match-panel {
  border: 1px solid rgba(236, 202, 142, 0.18);
  border-radius: 22px;
  background: rgba(24, 18, 14, 0.76);
  box-shadow: 0 22px 70px rgba(0, 0, 0, 0.25);
}

.board-panel {
  padding: 18px;
  overflow: auto;
}

.board-panel-head {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
  align-items: center;
}

.match-panel {
  padding: 18px;
  display: grid;
  gap: 18px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.result-box {
  display: grid;
  gap: 4px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(49, 96, 67, 0.2);
  color: #dff0c4;
}

.check-notice {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  background: rgba(24, 9, 7, 0.38);
  pointer-events: none;
}

.check-notice span {
  width: min(280px, calc(100vw - 64px));
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  border: 2px solid rgba(255, 211, 138, 0.52);
  border-radius: 50%;
  background:
    radial-gradient(circle at 50% 38%, rgba(255, 236, 182, 0.24), transparent 56%),
    rgba(122, 31, 22, 0.9);
  color: #fff2d4;
  font-family: "Songti SC", "STSong", serif;
  font-size: clamp(56px, 10vw, 96px);
  font-weight: 900;
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.45);
}

.check-notice-enter-active,
.check-notice-leave-active {
  transition: opacity 160ms ease, transform 160ms ease;
}

.check-notice-enter-from,
.check-notice-leave-to {
  opacity: 0;
}

.check-notice-enter-from span,
.check-notice-leave-to span {
  transform: scale(0.92);
}

.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.panel-title h2 {
  font-size: 18px;
}

.panel-title span {
  color: #a99472;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}

.moves {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.move,
.empty {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
}

.move {
  padding: 5px 8px;
  border-radius: 8px;
  background: rgba(255, 244, 214, 0.08);
  color: #f1dcae;
}

.empty {
  color: #8d7b62;
}

.fen-panel {
  color: #bca78a;
}

.fen-panel code {
  display: block;
  margin-top: 10px;
  white-space: normal;
  word-break: break-all;
}

@media (max-width: 980px) {
  .entry-grid,
  .play-layout {
    grid-template-columns: 1fr;
  }

  .play-layout {
    gap: 16px;
  }
}

@media (max-width: 680px) {
  .topbar,
  .main-stage {
    width: min(100vw - 24px, 1240px);
  }

  .topbar,
  .table-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .entry-settings,
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
