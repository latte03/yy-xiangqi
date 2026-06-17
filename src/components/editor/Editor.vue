<script setup lang="ts">
  /**
   * 摆棋编辑器
   * - 棋盘面板 (Konva) — 显示当前编辑中的棋盘, 支持拖放/点击放置/删除
   * - 侧边棋子库 — 红方/黑方各 14 类棋子 (含将帅), 点击选中后可在棋盘点击放置
   * - 校验提示 — 硬错误阻止提交, 软警告提示
   * - 撤销/重做 + 清空 + 加载初始 + 提交到对局
   *
   * 实现思路:
   * - 用 Pointer 事件实现棋子库 → 棋盘的放置，避开 Tauri WebView 中 HTML5 drag/drop 的不稳定
   * - 棋盘内拖动棋子 (从棋盘某格到另一格) 用 Konva 自定义拖拽
   * - 点击格子: 调色板选中时放置; 无调色板选中且格子有子时进入"移动模式"
   */

  import { ref, shallowRef, onMounted, onBeforeUnmount, watch, computed } from 'vue'
  import Konva from 'konva'
  import {
    NCard,
    NSpace,
    NButton,
    NTag,
    NSelect,
    NModal,
    NProgress,
    NDropdown,
    useMessage
  } from 'naive-ui'
  import RecognizeCorners from './RecognizeCorners.vue'
  import type { Position, Color, PieceType } from '@/types'
  import { opponent } from '@/types'
  import { useEditorStore } from '@/stores/editor'
  import { useGameStore } from '@/stores/game'
  import { useUiStore } from '@/stores/ui'
  import { toFen } from '@/engine/fen'
  import { recognizeImage, checkBackend } from '@/utils/recognize-api'
  import {
    checkModelUpdate,
    applyModelUpdate,
    getModelUpdateStatus
  } from '@/utils/model-update-api'
  import type { ModelUpdateStatus } from '@/utils/model-update-api'
  import {
    addPiece,
    drawBoardLayer,
    CELL_SIZE,
    fileX,
    rankY,
    FILES,
    HEIGHT,
    PIECE_LABELS_BLACK,
    PIECE_LABELS_RED,
    RANKS,
    screenToCell,
    WIDTH
  } from '@/components/board/board-drawing'

  const editor = useEditorStore()
  const game = useGameStore()
  const ui = useUiStore()
  const message = useMessage()

  const emit = defineEmits<{
    (e: 'submitted'): void
  }>()

  const containerRef = ref<HTMLDivElement | null>(null)
  const firstMover = ref<'human' | 'ai'>('ai')
  const selectedCell = ref<Position | null>(null)
  const pasteOnce = ref(false) // 右键「复制」触发的一次性粘贴态
  let suppressPaletteClick = false
  let stage: Konva.Stage | null = null
  let pieceLayer: Konva.Layer | null = null
  let highlightLayer: Konva.Layer | null = null
  let suppressNextClick = false

  interface PaletteDragState {
    type: PieceType
    color: Color
    startX: number
    startY: number
    x: number
    y: number
    moved: boolean
  }

  const paletteDrag = shallowRef<PaletteDragState | null>(null)

  const PIECE_TYPES: PieceType[] = ['K', 'R', 'C', 'H', 'A', 'E', 'P']

  const playerSideOptions = [
    { label: '玩家执黑，AI 执红', value: 'ai-red' },
    { label: '玩家执红，AI 执黑', value: 'human-red' }
  ]

  const firstMoverOptions = [
    { label: 'AI 先走', value: 'ai' },
    { label: '玩家先走', value: 'human' }
  ]

  const starterSide = computed<Color>(() =>
    firstMover.value === 'ai' ? game.aiSide : game.humanSide
  )
  const aiStarts = computed(() => firstMover.value === 'ai')
  const submitLabel = computed(() =>
    aiStarts.value ? '开始对战，AI 先走 →' : '开始对战，我方先走 →'
  )
  const paletteDragLabel = computed(() => {
    const piece = paletteDrag.value
    if (!piece) return ''
    return piece.color === 'red' ? PIECE_LABELS_RED[piece.type] : PIECE_LABELS_BLACK[piece.type]
  })

  const fenPreview = computed(() =>
    toFen({
      board: editor.board,
      side: starterSide.value,
      halfmove: 0,
      fullmove: 1
    })
  )

  function drawBoard() {
    if (!stage) return
    stage.destroyChildren()
    const bg = new Konva.Layer()
    stage.add(bg)
    drawBoardLayer(bg)

    pieceLayer = new Konva.Layer()
    highlightLayer = new Konva.Layer()
    stage.add(pieceLayer)
    stage.add(highlightLayer)
    redrawPieces()
  }

  function redrawPieces() {
    if (!pieceLayer || !highlightLayer) return
    pieceLayer.destroyChildren()
    highlightLayer.destroyChildren()
    for (let r = 0; r < RANKS; r++) {
      for (let f = 0; f < FILES; f++) {
        const p = editor.board[r][f]
        if (!p) continue
        const isSelected = selectedCell.value?.file === f && selectedCell.value?.rank === r
        const pieceNode = addPiece(pieceLayer, p, f, r, isSelected)
        pieceNode.draggable(true)
        pieceNode.on('mouseenter', () => {
          if (stage) stage.container().style.cursor = 'grab'
        })
        pieceNode.on('mouseleave', () => {
          if (stage) stage.container().style.cursor = editor.palette ? 'copy' : 'default'
        })
        pieceNode.on('contextmenu', (evt) => {
          evt.evt.preventDefault()
          evt.cancelBubble = true
          openPieceMenu({ file: f, rank: r }, evt.evt as MouseEvent)
        })
        pieceNode.on('dragstart', () => {
          selectedCell.value = { file: f, rank: r }
          pieceNode.moveToTop()
          if (stage) stage.container().style.cursor = 'grabbing'
          containerRef.value?.classList.add('dragging-piece')
        })
        pieceNode.on('dragend', () => {
          containerRef.value?.classList.remove('dragging-piece')
          if (stage) stage.container().style.cursor = 'grab'
          suppressNextClick = true
          window.setTimeout(() => {
            suppressNextClick = false
          }, 0)

          const target = screenToCell(pieceNode.x(), pieceNode.y())
          if (!target) {
            redrawPieces()
            return
          }

          if (target.file === f && target.rank === r) {
            selectedCell.value = target
            redrawPieces()
            return
          }

          selectedCell.value = target
          editor.movePiece({ file: f, rank: r }, target)
        })
      }
    }
    pieceLayer.batchDraw()
    renderHighlight()
  }

  // ---------- 悬停高亮 + 幽灵棋子 ----------
  const hoverCell = ref<Position | null>(null)

  function renderHighlight() {
    if (!highlightLayer) return
    highlightLayer.destroyChildren()
    const cell = hoverCell.value
    if (cell) {
      const x = fileX(cell.file)
      const y = rankY(cell.rank)
      // 交叉点高亮环
      highlightLayer.add(
        new Konva.Circle({
          x,
          y,
          radius: CELL_SIZE * 0.46,
          stroke: 'rgba(244, 194, 93, 0.9)',
          strokeWidth: 2,
          dash: [5, 4],
          listening: false
        })
      )
      // 选了调色板棋子或正在从棋子库拖动，且该格为空 → 半透明幽灵棋子预览
      const empty = !editor.board[cell.rank][cell.file]
      const previewPiece = editor.palette ?? paletteDrag.value
      if (previewPiece && empty) {
        const ghost = addPiece(highlightLayer, previewPiece, cell.file, cell.rank, false)
        ghost.opacity(0.45)
        ghost.listening(false)
      }
    }
    highlightLayer.batchDraw()
  }

  function onStageMouseMove() {
    if (!stage) return
    const pos = stage.getPointerPosition()
    if (!pos) return
    const cell = screenToCell(pos.x, pos.y)
    if (cell?.file !== hoverCell.value?.file || cell?.rank !== hoverCell.value?.rank) {
      hoverCell.value = cell
      ui.cursorText = cell ? `${String.fromCharCode(97 + cell.file)}${cell.rank + 1}` : ''
      renderHighlight()
    }
  }

  function onStageMouseLeave() {
    if (hoverCell.value) {
      hoverCell.value = null
      ui.cursorText = ''
      renderHighlight()
    }
  }

  /** Konva 内点击/拖拽事件 */
  function onStageClick(_evt: Konva.KonvaEventObject<MouseEvent>) {
    if (suppressNextClick) return
    if (!stage) return
    const pos = stage.getPointerPosition()
    if (!pos) return
    const cell = screenToCell(pos.x, pos.y)
    if (!cell) return
    handleCellAction(cell)
  }
  function handleCellAction(cell: Position) {
    // 模式 1: 调色板选中 → 放置
    if (editor.palette) {
      editor.setSquare(cell, editor.palette)
      selectedCell.value = cell
      editor.selectPalettePiece(null)
      pasteOnce.value = false
      return
    }

    const piece = editor.board[cell.rank][cell.file]
    if (piece) {
      // 重复点击已选中的棋子 → 取消选中
      if (selectedCell.value?.file === cell.file && selectedCell.value?.rank === cell.rank) {
        selectedCell.value = null
      } else {
        selectedCell.value = cell
      }
      redrawPieces()
      return
    }

    if (selectedCell.value) {
      editor.movePiece(selectedCell.value, cell)
      selectedCell.value = cell
    }
  }

  onMounted(() => {
    if (!containerRef.value) return
    stage = new Konva.Stage({ container: containerRef.value, width: WIDTH, height: HEIGHT })
    drawBoard()
    stage.on('click', onStageClick)
    stage.on('mousemove', onStageMouseMove)
    stage.on('mouseleave', onStageMouseLeave)
    // 屏蔽棋盘上的浏览器默认右键菜单（改用自定义菜单）
    containerRef.value.addEventListener('contextmenu', (e) => e.preventDefault())
    window.addEventListener('paste', onPaste)
  })

  watch(
    () => editor.board,
    () => redrawPieces(),
    { deep: true }
  )

  watch(
    fenPreview,
    (fen) => {
      ui.contextText = fen
    },
    { immediate: true }
  )

  onBeforeUnmount(() => {
    stage?.destroy()
    window.removeEventListener('paste', onPaste)
    removePalettePointerListeners()
    stopModelUpdatePolling()
    ui.contextText = ''
  })

  function selectFromPalette(type: PieceType, color: Color) {
    if (suppressPaletteClick) return
    editor.selectPalettePiece({ type, color })
    pasteOnce.value = false
  }

  function startPalettePointerDrag(event: PointerEvent, type: PieceType, color: Color) {
    if (event.button !== 0) return
    event.preventDefault()
    paletteDrag.value = {
      type,
      color,
      startX: event.clientX,
      startY: event.clientY,
      x: event.clientX,
      y: event.clientY,
      moved: false
    }
    window.addEventListener('pointermove', movePalettePointerDrag)
    window.addEventListener('pointerup', finishPalettePointerDrag)
    window.addEventListener('pointercancel', cancelPalettePointerDrag)
  }

  function clientPointToCell(event: Pick<PointerEvent, 'clientX' | 'clientY'>): Position | null {
    if (!containerRef.value) return null
    const rect = containerRef.value.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top
    return screenToCell(x, y)
  }

  function movePalettePointerDrag(event: PointerEvent) {
    const drag = paletteDrag.value
    if (!drag) return
    const dx = event.clientX - drag.startX
    const dy = event.clientY - drag.startY
    paletteDrag.value = {
      ...drag,
      x: event.clientX,
      y: event.clientY,
      moved: drag.moved || Math.hypot(dx, dy) > 4
    }

    const cell = clientPointToCell(event)
    if (cell?.file !== hoverCell.value?.file || cell?.rank !== hoverCell.value?.rank) {
      hoverCell.value = cell
      ui.cursorText = cell ? `${String.fromCharCode(97 + cell.file)}${cell.rank + 1}` : ''
      renderHighlight()
    }
  }

  function removePalettePointerListeners() {
    window.removeEventListener('pointermove', movePalettePointerDrag)
    window.removeEventListener('pointerup', finishPalettePointerDrag)
    window.removeEventListener('pointercancel', cancelPalettePointerDrag)
  }

  function cancelPalettePointerDrag() {
    removePalettePointerListeners()
    paletteDrag.value = null
    hoverCell.value = null
    ui.cursorText = ''
    renderHighlight()
  }

  function finishPalettePointerDrag(event: PointerEvent) {
    const drag = paletteDrag.value
    removePalettePointerListeners()
    paletteDrag.value = null

    if (!drag || !drag.moved) {
      if (drag) {
        editor.selectPalettePiece({ type: drag.type, color: drag.color })
        pasteOnce.value = false
      }
      renderHighlight()
      return
    }

    const cell = clientPointToCell(event)
    if (!cell) {
      hoverCell.value = null
      ui.cursorText = ''
      renderHighlight()
      return
    }

    editor.setSquare(cell, { type: drag.type, color: drag.color })
    editor.selectPalettePiece(null)
    pasteOnce.value = false
    selectedCell.value = cell
    hoverCell.value = cell
    ui.cursorText = `${String.fromCharCode(97 + cell.file)}${cell.rank + 1}`
    renderHighlight()
    suppressPaletteClick = true
    window.setTimeout(() => {
      suppressPaletteClick = false
    }, 0)
  }

  function clearPalette() {
    editor.selectPalettePiece(null)
    pasteOnce.value = false
  }

  function deleteSelectedPiece() {
    if (!selectedCell.value) return
    editor.deletePiece(selectedCell.value)
    selectedCell.value = null
  }

  function clearSelection() {
    selectedCell.value = null
    redrawPieces()
  }

  // ---------- 棋子右键菜单 ----------
  const contextMenu = ref<{ show: boolean; x: number; y: number; cell: Position | null }>({
    show: false,
    x: 0,
    y: 0,
    cell: null
  })

  function pieceLabel(pos: Position): string {
    const p = editor.board[pos.rank][pos.file]
    if (!p) return ''
    const name = p.color === 'red' ? PIECE_LABELS_RED[p.type] : PIECE_LABELS_BLACK[p.type]
    return `${p.color === 'red' ? '红' : '黑'}${name}`
  }

  const contextMenuOptions = computed(() => {
    const cell = contextMenu.value.cell
    if (!cell) return []
    const isSelected =
      selectedCell.value?.file === cell.file && selectedCell.value?.rank === cell.rank
    return [
      { label: `${pieceLabel(cell)}`, key: 'header', disabled: true },
      { type: 'divider', key: 'd0' },
      { label: isSelected ? '取消选中' : '选中', key: 'toggle-select' },
      { label: '复制（再点空格放置）', key: 'copy' },
      { label: '翻转红黑', key: 'flip' },
      { type: 'divider', key: 'd1' },
      { label: '删除', key: 'delete' }
    ]
  })

  /** 在棋子上右键 → 打开菜单 */
  function openPieceMenu(cell: Position, evt: MouseEvent) {
    evt.preventDefault()
    selectedCell.value = cell
    redrawPieces()
    contextMenu.value = { show: false, x: evt.clientX, y: evt.clientY, cell }
    // 先关再开，确保 NDropdown 重新定位
    void Promise.resolve().then(() => {
      contextMenu.value.show = true
    })
  }

  function closeContextMenu() {
    contextMenu.value.show = false
  }

  function onContextMenuSelect(key: string) {
    const cell = contextMenu.value.cell
    contextMenu.value.show = false
    if (!cell) return
    const piece = editor.board[cell.rank][cell.file]
    if (!piece) return
    switch (key) {
      case 'toggle-select':
        selectedCell.value =
          selectedCell.value?.file === cell.file && selectedCell.value?.rank === cell.rank
            ? null
            : cell
        redrawPieces()
        break
      case 'copy':
        // 复用调色板机制，但标记为「一次性」：下一次点空格放置一枚副本后自动退出
        editor.selectPalettePiece({ type: piece.type, color: piece.color })
        pasteOnce.value = true
        break
      case 'flip':
        editor.setSquare(cell, { type: piece.type, color: opponent(piece.color) })
        break
      case 'delete':
        editor.deletePiece(cell)
        if (selectedCell.value?.file === cell.file && selectedCell.value?.rank === cell.rank) {
          selectedCell.value = null
        }
        break
    }
  }

  function submitToGame() {
    // 硬校验
    if (editor.validation.hardErrors.length > 0) {
      return
    }
    // 把 editor.board 推给对局 store
    const fen = toFen({
      board: editor.board,
      side: starterSide.value,
      halfmove: 0,
      fullmove: 1
    })
    game.applyCustomPosition(fen)
    emit('submitted')
  }

  // ---------- 截图识别 ----------
  const recognizeInput = ref<HTMLInputElement | null>(null)
  const recognizing = ref(false)
  const reviewCount = ref(0) // 需人工复核的格子数
  const pendingFile = ref<File | null>(null) // 待识别的截图
  const showCornerPicker = ref(false) // 框选四角弹窗
  const cornerModalEntered = ref(false)

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

  // 拖拽截图到识别卡片
  const dragOver = ref(false)
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
      const res = await recognizeImage(file, { side: starterSide.value, corners })
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

  // ---------- 模型更新（软件内，走 GitHub Releases） ----------
  const modelUpdating = ref(false)
  const modelUpdateMsg = ref('')
  const hasModelUpdate = ref(false)
  const modelUpdatePercent = ref(0)
  let modelUpdatePoll: number | null = null

  function applyModelUpdateStatus(status: ModelUpdateStatus) {
    modelUpdating.value = status.running
    modelUpdatePercent.value = status.percent
    modelUpdateMsg.value = status.message
    if (!status.running) {
      stopModelUpdatePolling()
      if (status.ok) hasModelUpdate.value = false
    }
  }

  function stopModelUpdatePolling() {
    if (modelUpdatePoll !== null) {
      window.clearInterval(modelUpdatePoll)
      modelUpdatePoll = null
    }
  }

  function startModelUpdatePolling() {
    stopModelUpdatePolling()
    modelUpdatePoll = window.setInterval(async () => {
      try {
        applyModelUpdateStatus(await getModelUpdateStatus())
      } catch (err) {
        stopModelUpdatePolling()
        modelUpdating.value = false
        modelUpdateMsg.value = err instanceof Error ? err.message : '获取更新进度失败。'
      }
    }, 700)
  }

  async function onCheckModelUpdate() {
    modelUpdating.value = true
    modelUpdateMsg.value = ''
    hasModelUpdate.value = false
    modelUpdatePercent.value = 0
    try {
      const res = await checkModelUpdate()
      hasModelUpdate.value = !!res.has_update
      modelUpdateMsg.value =
        res.message + (res.has_update ? `（v${res.current_version} → v${res.latest_version}）` : '')
    } catch (err) {
      modelUpdateMsg.value = err instanceof Error ? err.message : '检查更新失败。'
    } finally {
      modelUpdating.value = false
    }
  }

  async function onApplyModelUpdate() {
    modelUpdating.value = true
    modelUpdatePercent.value = 1
    modelUpdateMsg.value = '下载并应用中…'
    try {
      const status = await applyModelUpdate()
      applyModelUpdateStatus(status)
      if (status.running) startModelUpdatePolling()
    } catch (err) {
      modelUpdateMsg.value = err instanceof Error ? err.message : '更新失败。'
      modelUpdatePercent.value = 0
      modelUpdating.value = false
    } finally {
      if (!modelUpdatePoll) modelUpdating.value = false
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

  function loadInitialLayout() {
    editor.loadInitial()
  }

  function clearAll() {
    editor.clearBoard()
    selectedCell.value = null
  }
</script>

<template>
  <div class="editor-layout">
    <div
      v-if="paletteDrag"
      class="palette-drag-ghost"
      :class="paletteDrag.color"
      :style="{ transform: `translate3d(${paletteDrag.x}px, ${paletteDrag.y}px, 0)` }"
    >
      {{ paletteDragLabel }}
    </div>

    <div class="board-section">
      <NCard  size="small">
             <div class="board-actions">
          <NSpace class="action-buttons">
            <NButton size="small" @click="loadInitialLayout">加载初始局面</NButton>
            <NButton size="small" @click="clearAll">清空棋盘</NButton>
            <NButton size="small" :disabled="editor.history.length === 0" @click="editor.undo">
              ↶ 撤销
            </NButton>
            <NButton size="small" :disabled="editor.redoStack.length === 0" @click="editor.redo">
              ↷ 重做
            </NButton>
            <NButton size="small" :disabled="!selectedCell" @click="deleteSelectedPiece">
              删除选中
            </NButton>
            <NButton size="small" :disabled="!selectedCell" @click="clearSelection">
              取消选中
            </NButton>
          </NSpace>
          <div class="editor-status">
            <NTag v-if="editor.palette" type="warning" closable @close="clearPalette">
              选中：{{ editor.palette.color === 'red' ? '红' : '黑'
              }}{{
                editor.palette.color === 'red'
                  ? PIECE_LABELS_RED[editor.palette.type]
                  : PIECE_LABELS_BLACK[editor.palette.type]
              }}
              (点击格子放置)
            </NTag>
            <NTag v-else-if="selectedCell" type="success" closable @close="clearSelection">
              已选中：{{ String.fromCharCode(97 + selectedCell.file) }}{{ selectedCell.rank + 1 }}
            </NTag>
            <span v-else>可拖动棋盘上的棋子调整位置，点选后可删除。</span>
          </div>
        </div>
        <div class="board-workspace">
          <div class="palette-strip black">
            <span class="palette-side black">黑</span>
            <div class="palette-grid">
              <button
                v-for="t in PIECE_TYPES"
                :key="'b-' + t"
                class="palette-piece black"
                :class="{ active: editor.palette?.type === t && editor.palette?.color === 'black' }"
                @click="selectFromPalette(t, 'black')"
                @pointerdown="startPalettePointerDrag($event, t, 'black')"
              >
                {{ PIECE_LABELS_BLACK[t] }}
              </button>
            </div>
          </div>

          <div
            ref="containerRef"
            class="board-canvas"
            :class="{ 'has-palette': !!editor.palette }"
            :style="{ width: WIDTH + 'px', height: HEIGHT + 'px' }"
          />

          <div class="palette-strip red">
            <span class="palette-side red">红</span>
            <div class="palette-grid">
              <button
                v-for="t in PIECE_TYPES"
                :key="'r-' + t"
                class="palette-piece red"
                :class="{ active: editor.palette?.type === t && editor.palette?.color === 'red' }"
                @click="selectFromPalette(t, 'red')"
                @pointerdown="startPalettePointerDrag($event, t, 'red')"
              >
                {{ PIECE_LABELS_RED[t] }}
              </button>
            </div>
          </div>
        </div>

        <NDropdown
          trigger="manual"
          placement="bottom-start"
          :show="contextMenu.show"
          :x="contextMenu.x"
          :y="contextMenu.y"
          :options="contextMenuOptions"
          @select="onContextMenuSelect"
          @clickoutside="closeContextMenu"
        />
      </NCard>
    </div>

    <div class="palette-section">
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
            <NButton size="tiny" :loading="modelUpdating" @click="onCheckModelUpdate"
              >检查模型更新</NButton
            >
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

      <NCard title="校验" size="small" style="margin-top: 12px">
        <div
          v-if="
            editor.validation.hardErrors.length === 0 && editor.validation.warnings.length === 0
          "
          class="ok-msg"
        >
          ✓ 摆棋合规，可以提交
        </div>
        <ul v-else class="check-list">
          <li v-for="(err, i) in editor.validation.hardErrors" :key="'e-' + i" class="check-err">
            <span class="check-dot">✕</span>{{ err }}
          </li>
          <li v-for="(w, i) in editor.validation.warnings" :key="'w-' + i" class="check-warn">
            <span class="check-dot">!</span>{{ w }}
          </li>
        </ul>
      </NCard>

      <NCard title="提交" size="small" style="margin-top: 12px">
        <NSpace vertical>
          <div class="play-options">
            <div class="option-field">
              <span class="option-label">执方</span>
              <NSelect v-model:value="game.settings.side" :options="playerSideOptions" />
            </div>
            <div class="option-field">
              <span class="option-label">首手</span>
              <NSelect v-model:value="firstMover" :options="firstMoverOptions" />
            </div>
          </div>
          <NTag :type="aiStarts ? 'info' : 'success'">
            {{
              aiStarts
                ? `提交后 AI 走${starterSide === 'red' ? '红棋' : '黑棋'}，随后轮到玩家`
                : `提交后玩家走${starterSide === 'red' ? '红棋' : '黑棋'}`
            }}
          </NTag>
          <NButton
            type="primary"
            block
            size="large"
            :disabled="editor.validation.hardErrors.length > 0"
            @click="submitToGame"
          >
            {{ submitLabel }}
          </NButton>
        </NSpace>
      </NCard>
    </div>
  </div>
</template>

<style scoped>
  .editor-layout {
    display: grid;
    grid-template-columns: minmax(600px, 1fr) minmax(320px, 360px);
    gap: 18px;
    align-items: start;
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }
  .board-section {
    min-width: 0;
    min-height: 0;
    overflow: auto;
    padding-right: 2px;
  }
  .palette-section {
    min-width: 0;
    height: 100%;
    min-height: 0;
    overflow: auto;
    padding-right: 4px;
    scrollbar-gutter: stable;
  }
  .board-workspace {
    display: grid;
    justify-items: center;
    gap: 10px;
    margin: 0 auto;
    width: fit-content;
    max-width: 100%;
  }
  .board-canvas {
    border-radius: 4px;
    cursor: default;
    max-width: 100%;
  }
  .board-canvas.has-palette {
    cursor: copy;
  }
  .board-canvas.dragging-piece {
    cursor: grabbing;
  }

  .action-buttons {
    min-height: 34px;
  }
  .editor-status {
    min-height: 30px;
    margin-top: 8px;
    display: flex;
    align-items: center;
    color: #a99472;
    font-size: 13px;
  }
  .palette-strip {
    width: min(100%, 536px);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }
  .palette-side {
    flex: 0 0 auto;
    width: 22px;
    text-align: center;
    font-size: 13px;
    font-weight: 700;
  }
  .palette-side.red {
    color: #c0392b;
  }
  .palette-side.black {
    color: #cdb589;
  }
  .palette-grid {
    display: grid;
    grid-template-columns: repeat(7, 42px);
    justify-content: center;
    gap: 6px;
  }
  .palette-piece {
    width: 42px;
    aspect-ratio: 1;
    min-width: 0;
    border-radius: 50%;
    border: 2px solid #5a3e1b;
    background: #fff5dc;
    font-family: serif;
    font-size: 21px;
    font-weight: bold;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
    user-select: none;
  }
  .palette-piece:hover {
    background: #fff;
    transform: scale(1.05);
  }
  .palette-piece.active {
    border-color: #ffd700;
    box-shadow: 0 0 8px rgba(255, 215, 0, 0.6);
  }
  .palette-piece.red {
    color: #c0392b;
  }
  .palette-piece.black {
    color: #1c1c1c;
  }
  .palette-drag-ghost {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 80;
    width: 44px;
    height: 44px;
    margin: -22px 0 0 -22px;
    border: 2px solid #5a3e1b;
    border-radius: 50%;
    background: #fff5dc;
    box-shadow: 0 14px 30px rgba(0, 0, 0, 0.35);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: serif;
    font-size: 21px;
    font-weight: bold;
    pointer-events: none;
    user-select: none;
  }
  .palette-drag-ghost.red {
    color: #c0392b;
  }
  .palette-drag-ghost.black {
    color: #1c1c1c;
  }
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
  .ok-msg {
    color: #27ae60;
    font-size: 13px;
  }
  .check-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .check-list li {
    display: flex;
    align-items: baseline;
    gap: 7px;
    font-size: 13px;
    line-height: 1.4;
  }
  .check-dot {
    flex: 0 0 auto;
    width: 14px;
    text-align: center;
    font-weight: 700;
  }
  .check-err {
    color: #e07b6a;
  }
  .check-warn {
    color: #d8b46a;
  }
  .play-options {
    display: grid;
    gap: 8px;
  }
  .option-field {
    display: grid;
    gap: 4px;
  }
  .option-label {
    font-size: 12px;
    color: #aaa;
  }
  @media (max-width: 980px) {
    .editor-layout {
      grid-template-columns: 1fr;
    }

    .palette-section {
      height: auto;
      max-height: none;
      overflow: visible;
      padding-right: 0;
      position: static;
    }
  }

  @media (max-height: 820px) and (min-width: 981px) {
    .palette-section {
      height: 100%;
    }
  }
</style>
