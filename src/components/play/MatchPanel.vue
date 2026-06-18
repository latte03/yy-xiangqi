<script setup lang="ts">
  /**
   * 对局侧栏：执方/回合统计、终局结果、走法记录。
   * 只读对局 store，无对外事件。
   */
  import { computed } from 'vue'
  import { NStatistic } from 'naive-ui'
  import { useGameStore } from '@/stores/game'
  import { endReasonLabel, winnerLabel } from '@/utils/end-state'

  const game = useGameStore()

  const humanSideLabel = computed(() => (game.humanSide === 'red' ? '红方' : '黑方'))
  const aiSideLabel = computed(() => (game.aiSide === 'red' ? '红方' : '黑方'))
  const resultReasonLabel = computed(() => endReasonLabel(game.endResult))
  const resultWinnerLabel = computed(() => winnerLabel(game.endResult?.winner))
  const movePairs = computed(() =>
    game.moves.map((move, index) => ({
      index,
      label: `${index % 2 === 0 ? `${Math.floor(index / 2) + 1}. ` : ''}${move}`
    }))
  )
</script>

<template>
  <aside class="match-panel">
    <div class="stats-grid">
      <NStatistic label="玩家执方" :value="humanSideLabel" />
      <NStatistic label="AI 执方" :value="aiSideLabel" />
      <NStatistic label="回合数" :value="game.fullmove" />
      <NStatistic label="限着" :value="game.halfmove" />
    </div>

    <div v-if="game.ended" class="result-box" role="status">
      <strong>{{ resultWinnerLabel }}</strong>
      <span>{{ resultReasonLabel }}</span>
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
</template>

<style scoped>
  .match-panel {
    border: 1px solid rgba(236, 202, 142, 0.18);
    border-radius: 22px;
    background: rgba(24, 18, 14, 0.76);
    box-shadow: 0 22px 70px rgba(0, 0, 0, 0.25);
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 16px;
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
  .move-log {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }
  .panel-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }
  .panel-title h2 {
    margin: 0;
    font-size: 18px;
    color: #fff0d3;
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
</style>
