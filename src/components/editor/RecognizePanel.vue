<script setup lang="ts">
  /**
   * 截图识别面板（实验）。
   * 从 Editor 拆出：上传/拖拽/粘贴截图 → 框选四角 → 调用后端识别 → 写入棋盘，
   * 以及软件内模型更新控件。Editor 只需传入当前执方 side。
   */
  import { ref, onMounted, onBeforeUnmount } from 'vue'
  import { NCard, NSpace, NButton, NProgress, NModal, useMessage } from 'naive-ui'
  import RecognizeCorners from './RecognizeCorners.vue'
  import type { Color } from '@/types'
  import { useEditorStore } from '@/stores/editor'
  import { useTrainingSampleStore } from '@/stores/training-sample'
  import { recognizeImage, checkBackend } from '@/utils/recognize-api'
  import { useModelUpdate } from '@/composables/use-model-update'

  const props = defineProps<{ side: Color }>()

  const editor = useEditorStore()
  const trainingSample = useTrainingSampleStore()
  const message = useMessage()
  const {
    updating: modelUpdating,
    message: modelUpdateMsg,
    hasUpdate: hasModelUpdate,
    percent: modelUpdatePercent,
    checkUpdate: onCheckModelUpdate,
    applyUpdate: onApplyModelUpdate
  } = useModelUpdate()

  const recognizeInput = ref<HTMLInputElement | null>(null)
  const recognizing = ref(false)
  const reviewCount = ref(0) // 需人工复核的格子数
  const pendingFile = ref<File | null>(null) // 待识别的截图
  const showCornerPicker = ref(false) // 框选四角弹窗
  const cornerModalEntered = ref(false)
  const dragOver = ref(false)

  function pickScreenshot() {
    recognizeInput.value?.click()
  }

  /** 统一入口：选文件 / 粘贴 / 拖拽 都走这里 → 打开框选四角弹窗 */
  function startRecognizeFlow(file: File) {
    if (!file.type.startsWith('image/')) {
      message.error('请提供图片（截图）文件。')
      return
    }
    pendingFile.value = file
    cornerModalEntered.value = false
    showCornerPicker.value = true
  }

  function onScreenshotChosen(e: Event) {
    const input = e.target as HTMLInputElement
    const file = input.files?.[0]
    input.value = '' // 允许重复选同一文件
    if (file) startRecognizeFlow(file)
  }

  function onRecognizeDragOver(e: DragEvent) {
    if (e.dataTransfer?.types?.includes('Files')) {
      e.preventDefault()
      dragOver.value = true
    }
  }
  function onRecognizeDragLeave() {
    dragOver.value = false
  }
  function onRecognizeDrop(e: DragEvent) {
    dragOver.value = false
    const file = e.dataTransfer?.files?.[0]
    if (file) {
      e.preventDefault()
      startRecognizeFlow(file)
    }
  }

  // 剪贴板粘贴截图 (Ctrl/Cmd+V)：桌面端最自然的导入方式
  function onPaste(e: ClipboardEvent) {
    // 正在框选弹窗 / 输入框聚焦时不拦截
    if (showCornerPicker.value) return
    const target = e.target as HTMLElement | null
    if (target && /^(INPUT|TEXTAREA)$/.test(target.tagName)) return
    const items = e.clipboardData?.items
    if (!items) return
    for (const it of items) {
      if (it.kind === 'file' && it.type.startsWith('image/')) {
        const file = it.getAsFile()
        if (file) {
          e.preventDefault()
          startRecognizeFlow(file)
        }
        return
      }
    }
  }

  /** corners 为空 = 走后端自动定位；非空 = 手动四角 */
  async function runRecognize(corners?: string) {
    const file = pendingFile.value
    if (!file) return
    trainingSample.setFile(file)
    trainingSample.setCorners(corners ?? '')
    showCornerPicker.value = false
    recognizing.value = true
    reviewCount.value = 0
    try {
      const health = await checkBackend()
      if (!health.online) {
        message.error('识别服务未启动。请先运行本地后端（backend/），详见 backend/README.md。')
        return
      }
      if (!health.modelReady) {
        message.error(
          health.message || 'CNN 模型未就绪。请先训练并放置 backend/models/piece_classifier.onnx。'
        )
        return
      }
      const res = await recognizeImage(file, { side: props.side, corners })
      if (!res.ok) {
        message.error((res.message || '识别失败') + '。可重新上传并手动框选四角再试。')
        return
      }
      editor.loadFen(res.fen)
      reviewCount.value = res.low_confidence?.length ?? 0
      const text =
        `识别完成，已填入 ${res.cells.length} 个子。` +
        (reviewCount.value > 0
          ? `其中 ${reviewCount.value} 个置信较低，请在棋盘上核对纠正。`
          : '请核对无误后提交。') +
        (res.message ? `（${res.message}）` : '')
      if (reviewCount.value > 0) message.warning(text)
      else message.success(text)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '识别请求出错。')
    } finally {
      recognizing.value = false
    }
  }

  function onCornerConfirm(corners: string) {
    runRecognize(corners)
  }
  function onCornerAuto() {
    runRecognize(undefined)
  }
  function onCornerCancel() {
    showCornerPicker.value = false
    cornerModalEntered.value = false
    pendingFile.value = null
  }

  onMounted(() => {
    window.addEventListener('paste', onPaste)
  })
  onBeforeUnmount(() => {
    window.removeEventListener('paste', onPaste)
  })
</script>

<template>
  <NCard title="截图识别（实验）" size="small" style="margin-bottom: 12px">
    <input
      ref="recognizeInput"
      type="file"
      accept="image/*"
      style="display: none"
      @change="onScreenshotChosen"
    />
    <NSpace vertical size="small">
      <div
        class="drop-zone"
        :class="{ over: dragOver }"
        @click="pickScreenshot"
        @dragover="onRecognizeDragOver"
        @dragleave="onRecognizeDragLeave"
        @drop="onRecognizeDrop"
      >
        <span v-if="recognizing">识别中…</span>
        <span v-else>点击上传 · 拖拽图片到此 · 或直接粘贴截图（Ctrl/Cmd+V）</span>
      </div>
      <p class="palette-hint">支持自动定位或手动框选四角；识别后可在棋盘上手动拖动纠正。</p>

      <div class="model-update-row">
        <NButton size="tiny" :loading="modelUpdating" @click="onCheckModelUpdate">
          检查模型更新
        </NButton>
        <NButton
          v-if="hasModelUpdate"
          size="tiny"
          type="primary"
          :loading="modelUpdating"
          @click="onApplyModelUpdate"
        >
          下载并更新
        </NButton>
      </div>
      <NProgress
        v-if="modelUpdatePercent > 0"
        type="line"
        :percentage="modelUpdatePercent"
        :processing="modelUpdating"
        :height="8"
        :border-radius="4"
        :fill-border-radius="4"
        class="model-update-progress"
      />
      <p v-if="modelUpdateMsg" class="palette-hint">{{ modelUpdateMsg }}</p>
    </NSpace>
  </NCard>

  <NModal
    v-model:show="showCornerPicker"
    preset="card"
    title="框选棋盘四角"
    style="width: min(96vw, 1280px); max-height: min(94vh, 920px)"
    class="corner-modal"
    :mask-closable="false"
    @after-enter="cornerModalEntered = true"
    @before-leave="cornerModalEntered = false"
  >
    <RecognizeCorners
      v-if="pendingFile"
      :file="pendingFile"
      :is-enter="cornerModalEntered"
      @confirm="onCornerConfirm"
      @auto="onCornerAuto"
      @cancel="onCornerCancel"
    />
  </NModal>
</template>

<style scoped>
  .palette-hint {
    margin: 8px 0 0;
    font-size: 12px;
    color: #888;
  }
  .drop-zone {
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    min-height: 64px;
    padding: 12px;
    border: 1.5px dashed rgba(236, 202, 142, 0.4);
    border-radius: 10px;
    background: rgba(255, 244, 214, 0.04);
    color: #c8b48c;
    font-size: 12.5px;
    line-height: 1.5;
    cursor: pointer;
    transition: all 0.15s;
  }
  .drop-zone:hover {
    border-color: rgba(236, 202, 142, 0.7);
    background: rgba(255, 244, 214, 0.08);
  }
  .drop-zone.over {
    border-color: #ffd700;
    background: rgba(255, 215, 0, 0.1);
    color: #ffe7b1;
  }
  .model-update-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 4px;
  }
  .model-update-progress {
    max-width: 100%;
  }
</style>
