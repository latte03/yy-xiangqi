<script setup lang="ts">
  /**
   * 入口首页：自定义残局 / 普通对战 /（可选）模型训练 三张卡片。
   * 普通对战的难度、执方设置直接绑定到对局 store；其余动作以事件抛给 App。
   */
  import { NButton, NSelect } from 'naive-ui'
  import { useGameStore } from '@/stores/game'

  defineProps<{ trainingEnabled: boolean }>()

  const emit = defineEmits<{
    (e: 'start-standard'): void
    (e: 'open-editor'): void
    (e: 'open-training'): void
  }>()

  const game = useGameStore()

  const difficultyOptions = [
    { label: '入门 depth 2', value: 'easy' },
    { label: '业余 depth 4', value: 'medium' },
    { label: '进阶 depth 6', value: 'hard' },
    { label: '挑战 depth 8', value: 'expert' }
  ]

  const sideOptions = [
    { label: '玩家执黑，AI 执红', value: 'ai-red' },
    { label: '玩家执红，AI 执黑', value: 'human-red' }
  ]
</script>

<template>
  <section class="entry-screen">
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
        <NButton type="primary" size="large" block @click="emit('open-editor')">
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
        <NButton type="primary" size="large" block @click="emit('start-standard')">
          进入普通对战
        </NButton>
      </article>

      <article v-if="trainingEnabled" class="entry-card training-entry">
        <span class="entry-number">03</span>
        <h2>模型训练</h2>
        <p>把真实截图和正确 FEN 转成 crops，重新训练 ONNX 识别模型。</p>
        <div class="entry-notes">
          <span>提取真实裁剪</span>
          <span>生成 dataset</span>
          <span>训练并检查 ONNX</span>
        </div>
        <NButton type="primary" size="large" block @click="emit('open-training')">
          进入训练工作台
        </NButton>
      </article>
    </div>
  </section>
</template>

<style scoped>
  .entry-screen {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    justify-items: center;
    align-content: center;
    gap: 22px;
    height: 100%;
    min-height: 0;
    padding: 0;
    text-align: center;
  }
  .entry-copy {
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
    text-wrap: balance;
  }
  h2 {
    color: #fff0d3;
    font-size: 26px;
    line-height: 1.1;
  }
  .lead {
    margin-top: 16px;
    max-width: 620px;
    color: #bba88a;
    font-size: 16px;
    line-height: 1.6;
  }
  .entry-grid {
    width: min(960px, 100%);
    display: grid;
    grid-template-columns: repeat(2, minmax(260px, 1fr));
    gap: 14px;
    align-content: start;
    text-align: left;
  }
  .entry-card {
    position: relative;
    min-height: 250px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 14px;
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
  @media (max-width: 980px) {
    .entry-screen,
    .entry-grid {
      grid-template-columns: 1fr;
    }
  }
  @media (max-width: 680px) {
    .entry-settings {
      grid-template-columns: 1fr;
    }
  }
</style>
