<script setup lang="ts">
  /**
   * 顶部标题栏：Tauri 窗口控制（关闭/最小化/缩放 + 拖拽）+ 屏幕导航。
   * 窗口操作内聚在此，App 只接收导航事件。
   */
  import { NButton, NTag } from 'naive-ui'

  const props = defineProps<{
    screen: 'home' | 'editor' | 'play' | 'training'
    trainingEnabled: boolean
    isTauri: boolean
  }>()

  const emit = defineEmits<{
    (e: 'open-editor'): void
    (e: 'open-training'): void
    (e: 'go-home'): void
  }>()

  async function withAppWindow(action: 'close' | 'minimize' | 'toggleMaximize' | 'startDragging') {
    if (!props.isTauri) return
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    await getCurrentWindow()[action]()
  }

  function startWindowDrag(event: MouseEvent) {
    if (!props.isTauri) return
    if ((event.target as HTMLElement | null)?.closest('button, .n-button')) return
    void withAppWindow('startDragging')
  }
</script>

<template>
  <header class="titlebar" data-tauri-drag-region @mousedown="startWindowDrag">

    <div v-if="isTauri" class="window-controls">
      <button class="window-control close" type="button" aria-label="关闭窗口" @click="withAppWindow('close')" />
      <button class="window-control minimize" type="button" aria-label="最小化窗口" @click="withAppWindow('minimize')" />
      <button class="window-control maximize" type="button" aria-label="缩放窗口" @click="withAppWindow('toggleMaximize')" />
    </div>
    <div class="titlebar-drag" data-tauri-drag-region />
    <div class="titlebar-actions">
      <NButton v-if="screen !== 'editor'" size="small" type="primary" secondary @click="emit('open-editor')">
        自定义残局
      </NButton>
      <NTag v-else :bordered="false" type="warning">自定义残局</NTag>
      <NButton
        v-if="trainingEnabled && screen !== 'training'"
        size="small"
        type="primary"
        secondary
        @click="emit('open-training')"
      >
        模型训练
      </NButton>
      <NTag v-else-if="trainingEnabled" :bordered="false" type="info">模型训练</NTag>
      <NButton v-if="screen !== 'home'" size="small" secondary @click="emit('go-home')">返回入口</NButton>
    </div>
  </header>
</template>

<style scoped>
  .titlebar {
    width: min(1560px, calc(100vw - 40px));
    margin: 0 auto;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    -webkit-app-region: drag;
    user-select: none;
  }
  .window-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    -webkit-app-region: no-drag;
  }
  .window-control {
    width: 13px;
    height: 13px;
    padding: 0;
    border: 0;
    border-radius: 50%;
    cursor: pointer;
    box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.18);
  }
  .window-control.close {
    background: #ff5f57;
  }
  .window-control.minimize {
    background: #febc2e;
  }
  .window-control.maximize {
    background: #28c840;
  }
  .window-control:hover {
    filter: brightness(1.08);
  }
  .titlebar-drag {
    flex: 1;
    align-self: stretch;
  }
  .titlebar-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    -webkit-app-region: no-drag;
  }
  @media (max-width: 680px) {
    .titlebar {
      width: min(100vw - 24px, 1240px);
      align-items: flex-start;
      flex-direction: column;
      height: auto;
      padding: 10px 0 0;
    }
  }
</style>
