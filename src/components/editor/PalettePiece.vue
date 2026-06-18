<script setup lang="ts">
  /**
   * 候选棋子（棋子库单枚）。
   * 用 Konva 渲染，与棋盘上的棋子共用 board-drawing 的造型函数，
   * 保证候选棋子与棋盘棋子像素级一致。
   */
  import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
  import type { Stage } from '@/lib/konva'
  import type { Color, PieceType } from '@/types'
  import { renderStandalonePiece } from '@/components/board/board-drawing'

  const props = withDefaults(
    defineProps<{
      type: PieceType
      color: Color
      selected?: boolean
      /** 画布边长（px），决定棋子尺寸 */
      size?: number
    }>(),
    { selected: false, size: 46 }
  )

  const canvasRef = ref<HTMLDivElement | null>(null)
  let stage: Stage | null = null

  function render() {
    if (!canvasRef.value) return
    stage?.destroy()
    stage = renderStandalonePiece(
      canvasRef.value,
      { type: props.type, color: props.color },
      props.size,
      props.selected
    )
  }

  onMounted(render)
  watch(
    () => [props.type, props.color, props.selected, props.size],
    render
  )
  onBeforeUnmount(() => stage?.destroy())
</script>

<template>
  <div
    ref="canvasRef"
    class="palette-piece-canvas"
    :style="{ width: size + 'px', height: size + 'px' }"
  />
</template>

<style scoped>
  .palette-piece-canvas {
    display: block;
    pointer-events: none;
  }
</style>
