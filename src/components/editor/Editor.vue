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
  import Konva, { type Layer } from '@/lib/konva'
  import { NCard, NSpace, NButton, NTag, NSelect, NDropdown } from 'naive-ui'
  import RecognizePanel from './RecognizePanel.vue'
  import PalettePiece from './PalettePiece.vue'
  import type { Position, Color, PieceType } from '@/types'
  import { opponent } from '@/types'
  import { useEditorStore } from '@/stores/editor'
  import { useGameStore } from '@/stores/game'
  import { useUiStore } from '@/stores/ui'
  import { toFen } from '@/engine/fen'
  import {
    addPiece,
    CELL_SIZE,
    fileX,
    rankY,
    HEIGHT,
    PIECE_LABELS_BLACK,
    PIECE_LABELS_RED,
    screenToCell,
    WIDTH
  } from '@/components/board/board-drawing'
  import { createBoardStage, paintPieces, type BoardStage } from '@/components/board/use-board-stage'

  const editor = useEditorStore()
  const game = useGameStore()
  const ui = useUiStore()

  const emit = defineEmits<{
    (e: 'submitted'): void
  }>()

  const containerRef = ref<HTMLDivElement | null>(null)
  const firstMover = ref<'human' | 'ai'>('ai')
  const selectedCell = ref<Position | null>(null)
  const pasteOnce = ref(false) // 右键「复制」触发的一次性粘贴态
  let suppressPaletteClick = false
  let boardStage: BoardStage | null = null
  let pieceLayer: Layer | null = null
  let highlightLayer: Layer | null = null
  let suppressNextClick = false

  function setCursor(cursor: string) {
    const el = boardStage?.stage.container()
    if (el) el.style.cursor = cursor
  }

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
  const PALETTE_PIECE_SIZE = 50

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
  const fenPreview = computed(() =>
    toFen({
      board: editor.board,
      side: starterSide.value,
      halfmove: 0,
      fullmove: 1
    })
  )

  function redrawPieces() {
    if (!pieceLayer || !highlightLayer) return
    paintPieces(pieceLayer, editor.board, {
      isSelected: (f, r) =>
        selectedCell.value?.file === f && selectedCell.value?.rank === r,
      onNode: (pieceNode, _piece, f, r) => {
        pieceNode.draggable(true)
        pieceNode.on('mouseenter', () => setCursor('grab'))
        pieceNode.on('mouseleave', () => setCursor(editor.palette ? 'copy' : 'default'))
        pieceNode.on('contextmenu', (evt) => {
          evt.evt.preventDefault()
          evt.cancelBubble = true
          openPieceMenu({ file: f, rank: r }, evt.evt as MouseEvent)
        })
        pieceNode.on('dragstart', () => {
          selectedCell.value = { file: f, rank: r }
          pieceNode.moveToTop()
          setCursor('grabbing')
          containerRef.value?.classList.add('dragging-piece')
        })
        pieceNode.on('dragend', () => {
          containerRef.value?.classList.remove('dragging-piece')
          setCursor('grab')
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
    })
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
    const cell = boardStage?.pointerCell() ?? null
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
  function onStageClick() {
    if (suppressNextClick) return
    const cell = boardStage?.pointerCell()
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
    boardStage = createBoardStage(containerRef.value)
    pieceLayer = boardStage.addLayer()
    highlightLayer = boardStage.addLayer()
    redrawPieces()
    boardStage.stage.on('click', onStageClick)
    boardStage.stage.on('mousemove', onStageMouseMove)
    boardStage.stage.on('mouseleave', onStageMouseLeave)
    // 屏蔽棋盘上的浏览器默认右键菜单（改用自定义菜单）
    containerRef.value.addEventListener('contextmenu', (e) => e.preventDefault())
  })

  watch(
    () => editor.board,
    () => redrawPieces(),
    { deep: true }
  )

  watch(
    fenPreview,
    (fen) => {
      ui.editorFen = fen
    },
    { immediate: true }
  )

  onBeforeUnmount(() => {
    boardStage?.destroy()
    removePalettePointerListeners()
    ui.editorFen = ''
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
      :style="{ transform: `translate3d(${paletteDrag.x}px, ${paletteDrag.y}px, 0)` }"
    >
      <PalettePiece :type="paletteDrag.type" :color="paletteDrag.color" :size="52" />
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
            <span class="palette-side black">黑方</span>
            <div class="palette-grid">
              <button
                v-for="t in PIECE_TYPES"
                :key="'b-' + t"
                class="palette-piece"
                :class="{ active: editor.palette?.type === t && editor.palette?.color === 'black' }"
                :title="PIECE_LABELS_BLACK[t]"
                @click="selectFromPalette(t, 'black')"
                @pointerdown="startPalettePointerDrag($event, t, 'black')"
              >
                <PalettePiece
                  :type="t"
                  color="black"
                  :size="PALETTE_PIECE_SIZE"
                  :selected="editor.palette?.type === t && editor.palette?.color === 'black'"
                />
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
            <span class="palette-side red">红方</span>
            <div class="palette-grid">
              <button
                v-for="t in PIECE_TYPES"
                :key="'r-' + t"
                class="palette-piece"
                :class="{ active: editor.palette?.type === t && editor.palette?.color === 'red' }"
                :title="PIECE_LABELS_RED[t]"
                @click="selectFromPalette(t, 'red')"
                @pointerdown="startPalettePointerDrag($event, t, 'red')"
              >
                <PalettePiece
                  :type="t"
                  color="red"
                  :size="PALETTE_PIECE_SIZE"
                  :selected="editor.palette?.type === t && editor.palette?.color === 'red'"
                />
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
      <RecognizePanel :side="starterSide" />

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
    gap: 14px;
    margin: 14px auto 0;
    width: fit-content;
    max-width: 100%;
  }
  .board-canvas {
    overflow: hidden;
    border: 1px solid rgba(245, 203, 128, 0.32);
    border-radius: 20px;
    cursor: default;
    max-width: 100%;
    box-shadow:
      0 24px 60px rgba(0, 0, 0, 0.34),
      0 0 0 1px rgba(255, 238, 183, 0.08) inset;
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
    gap: 10px;
    padding: 8px 12px;
    border: 1px solid rgba(236, 202, 142, 0.18);
    border-radius: 16px;
    background:
      linear-gradient(180deg, rgba(255, 244, 214, 0.09), rgba(78, 43, 18, 0.12)),
      rgba(18, 12, 8, 0.34);
    box-shadow:
      0 12px 30px rgba(0, 0, 0, 0.18),
      0 1px 0 rgba(255, 239, 194, 0.1) inset;
  }
  .palette-side {
    flex: 0 0 auto;
    width: 1.4em;
    text-align: center;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 2px;
    font-family: "Songti SC", STSong, SimSun, serif;
    line-height: 1.15;
    writing-mode: vertical-rl;
    text-orientation: upright;
  }
  .palette-side.red {
    color: #de7667;
  }
  .palette-side.black {
    color: #d6c09a;
  }
  .palette-grid {
    display: grid;
    grid-template-columns: repeat(7, 50px);
    justify-content: center;
    gap: 9px;
  }
  /* 候选棋子按钮：仅作交互框架，棋子造型由内部 Konva 画布渲染，
     从而与棋盘上的棋子保持像素级一致。 */
  .palette-piece {
    position: relative;
    width: 50px;
    height: 50px;
    min-width: 0;
    padding: 0;
    border: none;
    background: transparent;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition:
      transform 160ms ease,
      filter 160ms ease;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
  }
  /* 棋子下方的浅凹槽，提示这是一个可取用的棋位 */
  .palette-piece::before {
    position: absolute;
    inset: 3px;
    content: "";
    border-radius: 50%;
    background: radial-gradient(circle at 50% 42%, rgba(0, 0, 0, 0.16), rgba(0, 0, 0, 0) 70%);
    opacity: 0;
    transition: opacity 160ms ease;
    pointer-events: none;
    z-index: -1;
  }
  .palette-piece:hover {
    transform: translateY(-3px);
    filter: brightness(1.05) drop-shadow(0 6px 10px rgba(20, 10, 4, 0.45));
  }
  .palette-piece:hover::before {
    opacity: 1;
  }
  .palette-piece:active {
    transform: translateY(0) scale(0.96);
  }
  /* 选中态：Konva 棋子本身已画出金色高亮环，这里再补一圈柔光强调 */
  .palette-piece.active {
    filter: drop-shadow(0 0 6px rgba(244, 194, 93, 0.7));
  }
  .palette-piece.active::before {
    opacity: 1;
    background: radial-gradient(circle at 50% 50%, rgba(244, 194, 93, 0.28), rgba(244, 194, 93, 0) 72%);
  }
  .palette-piece:focus-visible {
    outline: 2px solid #f4c85d;
    outline-offset: 2px;
  }
  .palette-drag-ghost {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 80;
    width: 52px;
    height: 52px;
    margin: -26px 0 0 -26px;
    display: flex;
    align-items: center;
    justify-content: center;
    filter: drop-shadow(0 12px 20px rgba(0, 0, 0, 0.45));
    pointer-events: none;
    user-select: none;
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
