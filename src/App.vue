<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import {
  NButton,
  NConfigProvider,
  NMessageProvider,
  NSelect,
  NStatistic,
  NTag,
  darkTheme,
} from 'naive-ui';
import type { GlobalThemeOverrides } from 'naive-ui';
import ChessBoard from './components/board/ChessBoard.vue';
import Editor from './components/editor/Editor.vue';
import LoadingSplash from './components/common/LoadingSplash.vue';
import { useGameStore } from './stores/game';
import { useUiStore } from './stores/ui';
import { checkBackend } from './utils/recognize-api';
import { getModelStatus } from './utils/model-update-api';

// 训练工作台仅维护者/开发构建可见；分发给终端用户的构建不含训练入口。
// 开发环境 (vite dev) 默认开启；其它构建需显式设 VITE_ENABLE_TRAINING=true。
const TRAINING_ENABLED =
  import.meta.env.DEV || import.meta.env.VITE_ENABLE_TRAINING === 'true';
// 仅在启用时才按需加载训练组件，分发构建会被拆成不加载的独立 chunk。
const Training = TRAINING_ENABLED
  ? defineAsyncComponent(() => import('./components/training/Training.vue'))
  : null;
import { endReasonLabel, endSummary, winnerLabel } from './utils/end-state';

const game = useGameStore();
const ui = useUiStore();

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

const backendLabel = computed(() => {
  if (!ui.backendOnline) return '识别服务：离线';
  if (!ui.modelReady) return '识别服务：在线（模型未就绪）';
  return `识别服务：在线${ui.modelVersion != null ? ` · 模型 v${ui.modelVersion}` : ''}`;
});

type Screen = 'home' | 'editor' | 'play' | 'training';
type Entry = 'standard' | 'custom';

const screen = ref<Screen>('home');
const activeEntry = ref<Entry>('standard');
const showCheckNotice = shallowRef(false);

const palette = {
  bg: '#120f0c',
  panel: 'rgba(24, 18, 14, 0.92)',
  panelSoft: 'rgba(255, 244, 214, 0.07)',
  panelHover: 'rgba(255, 244, 214, 0.11)',
  border: 'rgba(236, 202, 142, 0.22)',
  borderStrong: 'rgba(236, 202, 142, 0.42)',
  text: '#f6ead4',
  textSoft: '#d8c4a2',
  muted: '#a99472',
  gold: '#d2aa70',
  goldHover: '#e4c184',
  goldPressed: '#b98b4c',
  clay: '#b8643b',
  clayHover: '#cf7b4d',
  clayPressed: '#964b2e',
  green: '#5fae7a',
  greenHover: '#78c791',
  greenPressed: '#478a5c',
  teal: '#58c7a2',
  tealHover: '#78d8ba',
  tealPressed: '#3d9879',
  red: '#c85f4a',
  redHover: '#df765f',
  redPressed: '#9f4336',
};

const naiveThemeOverrides: GlobalThemeOverrides = {
  common: {
    baseColor: palette.bg,
    bodyColor: palette.bg,
    popoverColor: 'rgba(24, 18, 14, 0.98)',
    cardColor: palette.panel,
    modalColor: palette.panel,
    inputColor: 'rgba(16, 12, 9, 0.72)',
    tableColor: palette.panel,
    primaryColor: palette.gold,
    primaryColorHover: palette.goldHover,
    primaryColorPressed: palette.goldPressed,
    primaryColorSuppl: palette.clay,
    infoColor: palette.teal,
    infoColorHover: palette.tealHover,
    infoColorPressed: palette.tealPressed,
    infoColorSuppl: palette.teal,
    successColor: palette.green,
    successColorHover: palette.greenHover,
    successColorPressed: palette.greenPressed,
    successColorSuppl: palette.green,
    warningColor: palette.gold,
    warningColorHover: palette.goldHover,
    warningColorPressed: palette.goldPressed,
    warningColorSuppl: palette.gold,
    errorColor: palette.red,
    errorColorHover: palette.redHover,
    errorColorPressed: palette.redPressed,
    errorColorSuppl: palette.red,
    textColorBase: palette.text,
    textColor1: palette.text,
    textColor2: palette.textSoft,
    textColor3: palette.muted,
    placeholderColor: 'rgba(216, 196, 162, 0.52)',
    borderColor: palette.border,
    dividerColor: 'rgba(236, 202, 142, 0.14)',
    hoverColor: palette.panelHover,
    pressedColor: 'rgba(184, 100, 59, 0.18)',
    borderRadius: '10px',
    borderRadiusSmall: '8px',
    fontFamily:
      '"Avenir Next", "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    fontWeightStrong: '700',
  },
  Button: {
    borderRadiusTiny: '8px',
    borderRadiusSmall: '9px',
    borderRadiusMedium: '10px',
    borderRadiusLarge: '12px',
    fontWeight: '650',
    color: 'rgba(255, 244, 214, 0.06)',
    colorHover: 'rgba(255, 244, 214, 0.11)',
    colorPressed: 'rgba(184, 100, 59, 0.18)',
    colorFocus: 'rgba(255, 244, 214, 0.11)',
    textColor: palette.textSoft,
    textColorHover: palette.text,
    textColorPressed: palette.text,
    border: `1px solid ${palette.border}`,
    borderHover: `1px solid ${palette.borderStrong}`,
    borderPressed: `1px solid ${palette.clay}`,
    borderFocus: `1px solid ${palette.gold}`,
    colorPrimary: palette.gold,
    colorHoverPrimary: palette.goldHover,
    colorPressedPrimary: palette.goldPressed,
    colorFocusPrimary: palette.goldHover,
    textColorPrimary: '#1e1209',
    textColorHoverPrimary: '#1e1209',
    textColorPressedPrimary: '#1e1209',
    textColorFocusPrimary: '#1e1209',
    borderPrimary: '1px solid transparent',
    borderHoverPrimary: '1px solid transparent',
    borderPressedPrimary: '1px solid transparent',
    borderFocusPrimary: `1px solid ${palette.goldHover}`,
    colorError: 'rgba(200, 95, 74, 0.18)',
    colorHoverError: 'rgba(200, 95, 74, 0.26)',
    colorPressedError: 'rgba(200, 95, 74, 0.32)',
    colorFocusError: 'rgba(200, 95, 74, 0.26)',
    textColorError: '#ffb6a5',
    textColorHoverError: '#ffd0c5',
    textColorPressedError: '#ffd0c5',
    textColorFocusError: '#ffd0c5',
    textColorTextError: '#ffb6a5',
    textColorTextHoverError: '#ffd0c5',
    textColorTextPressedError: '#ffd0c5',
    textColorTextFocusError: '#ffd0c5',
    textColorGhostError: '#ffb6a5',
    textColorGhostHoverError: '#ffd0c5',
    textColorGhostPressedError: '#ffd0c5',
    textColorGhostFocusError: '#ffd0c5',
    borderError: '1px solid rgba(200, 95, 74, 0.38)',
    borderHoverError: '1px solid rgba(223, 118, 95, 0.62)',
    borderPressedError: '1px solid rgba(223, 118, 95, 0.72)',
    borderFocusError: '1px solid rgba(223, 118, 95, 0.72)',
  },
  Select: {
    menuBoxShadow: '0 18px 48px rgba(0, 0, 0, 0.42)',
    peers: {
      InternalSelection: {
        borderRadius: '10px',
        color: 'rgba(16, 12, 9, 0.72)',
        colorActive: 'rgba(28, 20, 14, 0.94)',
        textColor: palette.text,
        placeholderColor: 'rgba(216, 196, 162, 0.52)',
        border: `1px solid ${palette.border}`,
        borderHover: `1px solid ${palette.borderStrong}`,
        borderActive: `1px solid ${palette.gold}`,
        borderFocus: `1px solid ${palette.gold}`,
        boxShadowFocus: '0 0 0 2px rgba(210, 170, 112, 0.18)',
        caretColor: palette.gold,
        arrowColor: palette.gold,
      },
      InternalSelectMenu: {
        borderRadius: '12px',
        color: 'rgba(24, 18, 14, 0.98)',
        optionTextColor: palette.textSoft,
        optionTextColorActive: '#fff4d4',
        optionColorPending: palette.panelHover,
        optionColorActive: 'rgba(210, 170, 112, 0.18)',
        optionColorActivePending: 'rgba(210, 170, 112, 0.24)',
        optionCheckColor: palette.gold,
      },
    },
  },
  Tag: {
    borderRadius: '8px',
    fontWeightStrong: '700',
    color: 'rgba(255, 244, 214, 0.08)',
    textColor: palette.textSoft,
    border: `1px solid ${palette.border}`,
    colorPrimary: 'rgba(210, 170, 112, 0.18)',
    textColorPrimary: '#ffe7b1',
    borderPrimary: '1px solid rgba(210, 170, 112, 0.38)',
    colorInfo: 'rgba(88, 199, 162, 0.18)',
    textColorInfo: '#9fe8cf',
    borderInfo: '1px solid rgba(88, 199, 162, 0.34)',
    colorSuccess: 'rgba(95, 174, 122, 0.18)',
    textColorSuccess: '#b9edc7',
    borderSuccess: '1px solid rgba(95, 174, 122, 0.34)',
    colorWarning: 'rgba(210, 170, 112, 0.18)',
    textColorWarning: '#ffe2a7',
    borderWarning: '1px solid rgba(210, 170, 112, 0.34)',
    colorError: 'rgba(200, 95, 74, 0.2)',
    textColorError: '#ffc1b2',
    borderError: '1px solid rgba(200, 95, 74, 0.38)',
  },
  Statistic: {
    labelTextColor: palette.muted,
    valueTextColor: '#f5e5c8',
    labelFontWeight: '600',
    valueFontWeight: '650',
  },
};

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

const entryTitle = computed(() => {
  if (screen.value === 'training') return '模型训练';
  return activeEntry.value === 'standard' ? '普通对战' : '自定义残局';
});
const humanSideLabel = computed(() => (game.humanSide === 'red' ? '红方' : '黑方'));
const aiSideLabel = computed(() => (game.aiSide === 'red' ? '红方' : '黑方'));
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
const movePairs = computed(() => game.moves.map((move, index) => ({
  index,
  label: `${index % 2 === 0 ? `${Math.floor(index / 2) + 1}. ` : ''}${move}`,
})));
const resultReasonLabel = computed(() => endReasonLabel(game.endResult));
const resultWinnerLabel = computed(() => winnerLabel(game.endResult?.winner));
const resultSummary = computed(() => endSummary(game.endResult));

let checkNoticeTimer: ReturnType<typeof setTimeout> | null = null;

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
  <NConfigProvider :theme="darkTheme" :theme-overrides="naiveThemeOverrides">
   <NMessageProvider :max="3" placement="top">
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
            <article class="entry-card custom-entry">
              <span class="entry-number">01</span>
              <h2>自定义残局</h2>
              <p>截图导入或手动摆出残局，校验后交给 AI 推演走法。</p>
              <div class="entry-notes">
                <span>截图识别布局</span>
                <span>自动校验将帅</span>
                <span>撤销重做兜底</span>
              </div>
              <NButton type="primary" size="large" block @click="openCustomEditor">
                进入摆棋工坊
              </NButton>
            </article>

            <article class="entry-card standard-entry">
              <span class="entry-number">02</span>
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

            <article v-if="TRAINING_ENABLED" class="entry-card training-entry">
              <span class="entry-number">03</span>
              <h2>模型训练</h2>
              <p>把真实截图和正确 FEN 转成 crops，重新训练 ONNX 识别模型。</p>
              <div class="entry-notes">
                <span>提取真实裁剪</span>
                <span>生成 dataset</span>
                <span>训练并检查 ONNX</span>
              </div>
              <NButton type="primary" size="large" block @click="openTraining">
                进入训练工作台
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

            <aside class="match-panel">
              <div class="stats-grid">
                <NStatistic label="玩家执方" :value="humanSideLabel" />
                <NStatistic label="AI 执方" :value="aiSideLabel" />
                <NStatistic label="回合数" :value="game.fullmove" />
                <NStatistic label="限着" :value="game.halfmove" />
              </div>

              <div v-if="game.ended" class="result-box" role="status">
                <strong>{{ resultWinnerLabel }}</strong>
                <span>
                  {{ resultReasonLabel }}
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
            </aside>
          </div>
        </section>
      </main>

      <Transition name="check-notice">
        <div v-if="showCheckNotice" class="check-notice" aria-live="assertive">
          <span>将军</span>
        </div>
      </Transition>

      <footer class="status-bar">
        <span class="status-item">
          <i class="dot" :class="{ on: ui.backendOnline, warn: ui.backendOnline && !ui.modelReady }" />
          {{ backendLabel }}
        </span>
        <span v-if="screen === 'editor' && ui.cursorText" class="status-item">光标：{{ ui.cursorText }}</span>
        <span class="status-spacer" />
        <span v-if="screen === 'play'" class="status-item mono">{{ game.fen }}</span>
      </footer>
    </div>

    <Transition name="splash-fade">
      <LoadingSplash v-if="booting" />
    </Transition>
   </NMessageProvider>
  </NConfigProvider>
</template>

<style scoped>
.app-shell {
  min-height: 90dvh;
  color: #f6ead4;
  padding-bottom: 30px; /* 给底部固定状态栏留位 */
}

/* 底部状态栏 */
.status-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: 28px;
  z-index: 12;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 16px;
  background: rgba(16, 12, 9, 0.96);
  border-top: 1px solid rgba(236, 202, 142, 0.16);
  color: #a99472;
  font-size: 12px;
  backdrop-filter: blur(6px);
}
.status-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.status-item.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  opacity: 0.85;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 52vw;
}
.status-spacer {
  flex: 1;
}
.status-bar .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #c85f4a;
}
.status-bar .dot.on {
  background: #5fae7a;
}
.status-bar .dot.warn {
  background: #d2aa70;
}
.splash-fade-leave-active {
  transition: opacity 0.35s ease;
}
.splash-fade-leave-to {
  opacity: 0;
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

.resign-button {
  --n-text-color: #ffb6a5 !important;
  --n-text-color-hover: #ffd0c5 !important;
  --n-text-color-pressed: #ffd0c5 !important;
  --n-text-color-focus: #ffd0c5 !important;
}

.main-stage {
  width: min(1240px, calc(100vw - 40px));
  margin: 0 auto;
  padding: 28px 0 54px;
}

.entry-screen {
  display: grid;
  align-content: start;
  gap: 22px;
  padding-top: 8px;
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
  font-size: clamp(30px, 4vw, 48px);
  line-height: 1.02;
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
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
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
  font-size: clamp(26px, 3vw, 40px);
}

.play-layout {
  display: grid;
  grid-template-columns: minmax(540px, auto) minmax(300px, 360px);
  gap: 22px;
  align-items: stretch;
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
  flex-wrap: wrap;
}

.match-panel {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.move-log {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.result-box {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px solid rgba(255, 216, 148, 0.24);
  border-radius: 12px;
  background:
    linear-gradient(135deg, rgba(255, 216, 148, 0.13), rgba(141, 46, 36, 0.12)),
    rgba(32, 26, 20, 0.72);
  color: #f7e8c7;
}

.result-box strong {
  color: #fff4d4;
  font-size: 20px;
  line-height: 1.15;
}

.result-box span {
  color: #d9bf8e;
  font-size: 13px;
  font-weight: 700;
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
  align-content: flex-start;
  gap: 8px;
  flex: 1;
  min-height: 0;
  overflow: auto;
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
