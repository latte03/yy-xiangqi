<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { NButton, NConfigProvider, NMessageProvider, NTag, darkTheme } from 'naive-ui';
import ChessBoard from './components/board/ChessBoard.vue';
import Editor from './components/editor/Editor.vue';
import LoadingSplash from './components/common/LoadingSplash.vue';
import TitleBar from './components/layout/TitleBar.vue';
import StatusBar from './components/layout/StatusBar.vue';
import HomeScreen from './components/home/HomeScreen.vue';
import MatchPanel from './components/play/MatchPanel.vue';
import { useGameStore } from './stores/game';
import { useUiStore } from './stores/ui';
import { checkBackend } from './utils/recognize-api';
import { getModelStatus } from './utils/model-update-api';
import { endSummary } from './utils/end-state';
import { naiveThemeOverrides } from './theme/naive-theme';

// 训练工作台仅维护者/开发构建可见；分发给终端用户的构建不含训练入口。
// 开发环境 (vite dev) 默认开启；其它构建需显式设 VITE_ENABLE_TRAINING=true。
const TRAINING_ENABLED =
  import.meta.env.DEV || import.meta.env.VITE_ENABLE_TRAINING === 'true';
// 仅在启用时才按需加载训练组件，分发构建会被拆成不加载的独立 chunk。
const Training = TRAINING_ENABLED
  ? defineAsyncComponent(() => import('./components/training/Training.vue'))
  : null;

const game = useGameStore();
const ui = useUiStore();
const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

// 启动加载遮罩：探测本地识别后端 sidecar 是否就绪（冷启动有 1-3s）
const booting = ref(true);

async function probeBackend(retries = 8): Promise<void> {
  for (let i = 0; i < retries; i++) {
    const health = await checkBackend();
    if (health.online) {
      let version: number | null = null;
      try {
        version = (await getModelStatus()).active_version ?? null;
      } catch {
        version = null;
      }
      ui.setBackend(true, health.modelReady, version);
      return;
    }
    await new Promise((r) => setTimeout(r, 600));
  }
  ui.setBackend(false, false, null);
}

onMounted(async () => {
  const minSplash = new Promise((r) => setTimeout(r, 900)); // 至少展示一会，避免闪一下
  await Promise.all([probeBackend(), minSplash]);
  booting.value = false;
});

type Screen = 'home' | 'editor' | 'play' | 'training';
type Entry = 'standard' | 'custom';

const screen = ref<Screen>('home');
const activeEntry = ref<Entry>('standard');
const showCheckNotice = ref(false);

const entryTitle = computed(() => {
  if (screen.value === 'training') return '模型训练';
  return activeEntry.value === 'standard' ? '普通对战' : '自定义残局';
});
const currentTurnLabel = computed(() => {
  if (game.ended) return '本局已结束';
  const side = game.side === 'red' ? '红方' : '黑方';
  if (game.aiThinking) return 'AI 思考中';
  return `${side}${game.side === game.aiSide ? '（AI）' : '（玩家）'}`;
});
const statusTagType = computed(() => {
  if (game.ended) return 'error';
  return game.side === game.aiSide ? 'info' : 'success';
});
const restartActionLabel = computed(() => {
  if (activeEntry.value === 'custom') return '重新摆棋';
  return game.ended ? '再来一局' : '重新开局';
});
const resultSummary = computed(() => endSummary(game.endResult));

let checkNoticeTimer: ReturnType<typeof setTimeout> | null = null;

function flashCheckNotice() {
  if (checkNoticeTimer) clearTimeout(checkNoticeTimer);
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

function cancelAiIfAvailable() {
  if (typeof game.cancelPendingAiMove === 'function') {
    game.cancelPendingAiMove();
  }
}

function startStandardGame() {
  activeEntry.value = 'standard';
  game.startNewGame();
  screen.value = 'play';
}

function openCustomEditor() {
  cancelAiIfAvailable();
  hideCheckNotice();
  activeEntry.value = 'custom';
  screen.value = 'editor';
}

function openTraining() {
  if (!TRAINING_ENABLED) return;
  cancelAiIfAvailable();
  hideCheckNotice();
  screen.value = 'training';
}

function onCustomSubmitted() {
  activeEntry.value = 'custom';
  screen.value = 'play';
}

function goHome() {
  cancelAiIfAvailable();
  hideCheckNotice();
  screen.value = 'home';
}

function restartCurrent() {
  if (activeEntry.value === 'standard') {
    startStandardGame();
    return;
  }
  cancelAiIfAvailable();
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
    if (ended) hideCheckNotice();
  },
);

onBeforeUnmount(hideCheckNotice);
</script>

<template>
  <NConfigProvider :theme="darkTheme" :theme-overrides="naiveThemeOverrides">
    <NMessageProvider :max="3" placement="top">
      <div class="app-shell" :class="{ 'is-tauri': isTauri }">
        <TitleBar
          :screen="screen"
          :training-enabled="TRAINING_ENABLED"
          :is-tauri="isTauri"
          @open-editor="openCustomEditor"
          @open-training="openTraining"
          @go-home="goHome"
        />

        <main class="main-stage">
          <HomeScreen
            v-if="screen === 'home'"
            :training-enabled="TRAINING_ENABLED"
            @start-standard="startStandardGame"
            @open-editor="openCustomEditor"
            @open-training="openTraining"
          />

          <section v-else-if="screen === 'editor'" class="editor-screen workbench-screen">
            <Editor @submitted="onCustomSubmitted" />
          </section>

          <section v-else-if="screen === 'training' && TRAINING_ENABLED && Training" class="editor-screen">
            <div class="section-heading">
              <p class="eyebrow">model training</p>
              <h1>模型训练</h1>
              <p>用真实截图修正识别模型，完成后回到自定义残局上传截图测试。</p>
            </div>
            <Training />
          </section>

          <section v-else class="play-screen">
            <div class="table-header">
              <div>
                <p class="eyebrow">match table</p>
                <h1>{{ entryTitle }}</h1>
              </div>
              <div class="match-actions">
                <NButton :disabled="!game.canUndo" secondary @click="game.undoMove">
                  ↶ 悔棋
                </NButton>
                <NButton :type="game.ended ? 'primary' : 'default'" secondary @click="restartCurrent">
                  {{ restartActionLabel }}
                </NButton>
                <NButton v-if="!game.ended" class="resign-button" type="error" secondary @click="game.resignGame">
                  认输
                </NButton>
                <NButton tertiary @click="goHome">换入口</NButton>
              </div>
            </div>

            <div class="play-layout">
              <section class="board-panel">
                <div class="board-panel-head">
                  <NTag :bordered="false" :type="statusTagType">
                    当前：{{ currentTurnLabel }}
                  </NTag>
                  <NTag v-if="game.ended" :bordered="false" type="error">{{ resultSummary }}</NTag>
                  <NTag v-else-if="game.inCheck" :bordered="false" type="error">将军</NTag>
                </div>
                <ChessBoard />
              </section>

              <MatchPanel />
            </div>
          </section>
        </main>

        <Transition name="check-notice">
          <div v-if="showCheckNotice" class="check-notice" aria-live="assertive">
            <span>将军</span>
          </div>
        </Transition>

        <StatusBar :screen="screen" />

        <Transition name="splash-fade">
          <LoadingSplash v-if="booting" />
        </Transition>
      </div>
    </NMessageProvider>
  </NConfigProvider>
</template>

<style scoped>
.app-shell {
  position: relative;
  height: 100dvh;
  min-height: 100dvh;
  overflow: hidden;
  background:
    radial-gradient(circle at 18% 8%, rgba(184, 100, 59, 0.24), transparent 34rem),
    radial-gradient(circle at 85% 18%, rgba(210, 170, 112, 0.13), transparent 30rem),
    linear-gradient(140deg, #17110d 0%, var(--page-bg-deep) 62%, #1a100c 100%);
  color: #f6ead4;
  isolation: isolate;
}

.app-shell::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  opacity: 0.12;
  background-image:
    linear-gradient(90deg, rgba(255, 255, 255, 0.1) 1px, transparent 1px),
    linear-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: linear-gradient(to bottom, black, transparent 88%);
}

.app-shell.is-tauri {
  border-radius: 16px;
}

.splash-fade-leave-active {
  transition: opacity 0.35s ease;
}
.splash-fade-leave-to {
  opacity: 0;
}

.resign-button {
  --n-text-color: #ffb6a5 !important;
  --n-text-color-hover: #ffd0c5 !important;
  --n-text-color-pressed: #ffd0c5 !important;
  --n-text-color-focus: #ffd0c5 !important;
}

.main-stage {
  width: min(1560px, calc(100vw - 40px));
  height: calc(100dvh - 44px - 28px);
  margin: 0 auto;
  padding: 10px 0;
  overflow: hidden;
}

.eyebrow {
  margin: 0 0 10px;
  color: #d2aa70;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.section-heading {
  max-width: 720px;
}

h1,
p {
  margin: 0;
}

h1 {
  color: #fff5df;
  font-size: clamp(30px, 4vw, 48px);
  line-height: 1.02;
  text-wrap: balance;
}

.section-heading p {
  margin-top: 16px;
  max-width: 620px;
  color: #bba88a;
  font-size: 16px;
  line-height: 1.6;
}

.editor-screen {
  display: grid;
  gap: 24px;
  height: 100%;
  min-height: 0;
  overflow: auto;
}

.workbench-screen {
  gap: 14px;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.play-screen {
  display: grid;
  gap: 18px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.table-header {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
}

.table-header h1 {
  font-size: clamp(26px, 3vw, 40px);
}

.match-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  -webkit-app-region: no-drag;
}

.play-layout {
  display: grid;
  grid-template-columns: minmax(540px, auto) minmax(300px, 360px);
  gap: 22px;
  align-items: stretch;
}

.board-panel {
  border: 1px solid rgba(236, 202, 142, 0.18);
  border-radius: 22px;
  background: rgba(24, 18, 14, 0.76);
  box-shadow: 0 22px 70px rgba(0, 0, 0, 0.25);
  padding: 18px;
  overflow: auto;
}

.board-panel-head {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
  align-items: center;
  flex-wrap: wrap;
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

@media (max-width: 980px) {
  .play-layout {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

@media (max-width: 680px) {
  .main-stage {
    width: min(100vw - 24px, 1240px);
  }

  .table-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
