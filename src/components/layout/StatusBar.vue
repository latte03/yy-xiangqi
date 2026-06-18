<script setup lang="ts">
  /**
   * 底部状态栏：识别后端状态、编辑器光标/FEN（含复制）、对局 FEN。
   * 直接读 ui / game store（皆为展示用状态），FEN 复制逻辑内聚于此。
   */
  import { computed, onBeforeUnmount, shallowRef } from 'vue'
  import { useUiStore } from '@/stores/ui'
  import { useGameStore } from '@/stores/game'

  defineProps<{ screen: 'home' | 'editor' | 'play' | 'training' }>()

  const ui = useUiStore()
  const game = useGameStore()

  const backendLabel = computed(() => {
    if (!ui.backendOnline) return '识别服务：离线'
    if (!ui.modelReady) return '识别服务：在线（模型未就绪）'
    return `识别服务：在线${ui.modelVersion != null ? ` · 模型 v${ui.modelVersion}` : ''}`
  })

  const fenCopied = shallowRef(false)
  let fenCopiedTimer: ReturnType<typeof setTimeout> | null = null

  function markFenCopied() {
    if (fenCopiedTimer) clearTimeout(fenCopiedTimer)
    fenCopied.value = true
    fenCopiedTimer = setTimeout(() => {
      fenCopied.value = false
      fenCopiedTimer = null
    }, 1400)
  }

  async function copyEditorFen() {
    const fen = ui.editorFen
    if (!fen) return
    try {
      await navigator.clipboard.writeText(fen)
      markFenCopied()
    } catch {
      const textarea = document.createElement('textarea')
      textarea.value = fen
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      textarea.remove()
      markFenCopied()
    }
  }

  onBeforeUnmount(() => {
    if (fenCopiedTimer) {
      clearTimeout(fenCopiedTimer)
      fenCopiedTimer = null
    }
  })
</script>

<template>
  <footer class="status-bar">
    <span class="status-item">
      <i class="dot" :class="{ on: ui.backendOnline, warn: ui.backendOnline && !ui.modelReady }" />
      {{ backendLabel }}
    </span>
    <span v-if="screen === 'editor' && ui.cursorText" class="status-item">光标：{{ ui.cursorText }}</span>
    <button
      v-if="screen === 'editor' && ui.editorFen"
      class="status-copy"
      type="button"
      @click="copyEditorFen"
    >
      {{ fenCopied ? '已复制 FEN' : '复制 FEN' }}
    </button>
    <span class="status-spacer" />
    <span v-if="screen === 'editor' && ui.editorFen" class="status-item mono">{{ ui.editorFen }}</span>
    <span v-if="screen === 'play'" class="status-item mono">{{ game.fen }}</span>
  </footer>
</template>

<style scoped>
  .status-bar {
    position: absolute;
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
  .status-copy {
    height: 20px;
    padding: 0 8px;
    border: 1px solid rgba(236, 202, 142, 0.22);
    border-radius: 6px;
    background: rgba(255, 244, 214, 0.06);
    color: #d8c4a2;
    cursor: pointer;
    font-size: 12px;
    line-height: 18px;
  }
  .status-copy:hover {
    border-color: rgba(236, 202, 142, 0.42);
    color: #f6ead4;
  }
  .status-spacer {
    flex: 1;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #c85f4a;
  }
  .dot.on {
    background: #5fae7a;
  }
  .dot.warn {
    background: #d2aa70;
  }
</style>
