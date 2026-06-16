<script setup lang="ts">
/**
 * 手动框选四角：自动定位的兜底安全网。
 * 在上传截图上叠 4 个可拖动角点 (左上/右上/右下/左下)，
 * 用户对准「落子网格」四角后，换算回原图像素坐标，
 * 以 "x0,y0;x1,y1;x2,y2;x3,y3" 传给后端 /recognize 的 corners 参数。
 *
 * 坐标：handle 存「显示像素」(相对图片左上角)；确认时按
 * naturalWidth/displayWidth 缩放回原图像素。
 */

import { computed, ref, reactive, onMounted, onBeforeUnmount, nextTick, watch } from 'vue';
import { NButton, NSpace } from 'naive-ui';

const props = withDefaults(defineProps<{
  file: File;
  showAuto?: boolean;
  isEnter?: boolean;
}>(), {
  showAuto: true,
  isEnter: false,
});
const emit = defineEmits<{
  (e: 'confirm', corners: string): void;
  (e: 'auto'): void;
  (e: 'cancel'): void;
}>();

const objectUrl = ref<string>('');
const imgEl = ref<HTMLImageElement | null>(null);

// 显示尺寸 (图片在页面上的实际渲染像素)
const disp = reactive({ w: 0, h: 0 });
// 原图自然尺寸
const nat = reactive({ w: 0, h: 0 });
// 4 角点 (显示像素，顺序: 左上,右上,右下,左下)
const pts = reactive([
  { x: 0, y: 0 },
  { x: 0, y: 0 },
  { x: 0, y: 0 },
  { x: 0, y: 0 },
]);

const activeCorner = ref(0);
let dragIdx = -1;
let activePointerId: number | null = null;
let initialized = false;
let resizeObserver: ResizeObserver | null = null;

const imageBoxStyle = computed(() => (
  nat.w > 0 && nat.h > 0
    ? {
        aspectRatio: `${nat.w} / ${nat.h}`,
        width: `min(100%, calc((94vh - 190px) * ${nat.w / nat.h}))`,
      }
    : undefined
));

function measureNatural() {
  if (!imgEl.value) return;
  nat.w = imgEl.value.naturalWidth;
  nat.h = imgEl.value.naturalHeight;
}

function measureDisplay() {
  if (!imgEl.value) return;
  const r = imgEl.value.getBoundingClientRect();
  disp.w = r.width;
  disp.h = r.height;
}

function nextFrame() {
  return new Promise<void>((resolve) => {
    window.requestAnimationFrame(() => resolve());
  });
}

function initPoints() {
  // 默认四角放在画面内缩 18%，方便用户拖到网格角
  const ix = disp.w * 0.18;
  const iy = disp.h * 0.18;
  pts[0] = { x: ix, y: iy };
  pts[1] = { x: disp.w - ix, y: iy };
  pts[2] = { x: disp.w - ix, y: disp.h - iy };
  pts[3] = { x: ix, y: disp.h - iy };
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

function syncDisplaySize(forceInit = false) {
  if (!imgEl.value) return;
  const oldW = disp.w;
  const oldH = disp.h;
  measureDisplay();
  if (disp.w <= 0 || disp.h <= 0) return;

  if (forceInit || !initialized || oldW <= 0 || oldH <= 0) {
    initPoints();
    initialized = true;
    return;
  }

  if (Math.abs(oldW - disp.w) < 0.5 && Math.abs(oldH - disp.h) < 0.5) {
    return;
  }

  const rx = disp.w / oldW;
  const ry = disp.h / oldH;
  for (const p of pts) {
    p.x *= rx;
    p.y *= ry;
  }
}

async function onImgLoad() {
  measureNatural();
  if (props.isEnter) {
    await stabilizeAfterEnter();
  }
}

async function stabilizeAfterEnter() {
  if (!imgEl.value || nat.w <= 0 || nat.h <= 0) return;
  await nextTick();
  await nextFrame();
  await nextFrame();
  await nextFrame();
  syncDisplaySize(!initialized);

  resizeObserver?.disconnect();
  if (imgEl.value) {
    resizeObserver = new ResizeObserver(() => {
      syncDisplaySize();
    });
    resizeObserver.observe(imgEl.value);
  }
}

function startDrag(i: number, ev: PointerEvent) {
  activeCorner.value = i;
  dragIdx = i;
  activePointerId = ev.pointerId;
  window.addEventListener('pointermove', onMove);
  window.addEventListener('pointerup', endDrag);
  window.addEventListener('pointercancel', endDrag);
  ev.stopPropagation();
  ev.preventDefault();
}

function pointFromEvent(ev: PointerEvent) {
  if (!imgEl.value) return null;
  const r = imgEl.value.getBoundingClientRect();
  return {
    x: clamp(ev.clientX - r.left, 0, disp.w),
    y: clamp(ev.clientY - r.top, 0, disp.h),
  };
}

function onMove(ev: PointerEvent) {
  if (dragIdx < 0) return;
  if (activePointerId !== null && ev.pointerId !== activePointerId) return;
  const point = pointFromEvent(ev);
  if (!point) return;
  pts[dragIdx] = point;
}

function placeActiveCorner(ev: PointerEvent) {
  const point = pointFromEvent(ev);
  if (!point) return;
  pts[activeCorner.value] = point;
}

function endDrag() {
  dragIdx = -1;
  activePointerId = null;
  window.removeEventListener('pointermove', onMove);
  window.removeEventListener('pointerup', endDrag);
  window.removeEventListener('pointercancel', endDrag);
}

function confirm() {
  if (disp.w === 0 || nat.w === 0) return;
  const sx = nat.w / disp.w;
  const sy = nat.h / disp.h;
  const s = pts
    .map((p) => `${Math.round(p.x * sx)},${Math.round(p.y * sy)}`)
    .join(';');
  emit('confirm', s);
}

const LABELS = ['左上', '右上', '右下', '左下'];

function onResize() {
  syncDisplaySize();
}

watch(
  () => props.isEnter,
  (isEnter) => {
    if (isEnter) {
      stabilizeAfterEnter();
    }
  },
);

onMounted(async () => {
  objectUrl.value = URL.createObjectURL(props.file);
  await nextTick();
  window.addEventListener('resize', onResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize);
  resizeObserver?.disconnect();
  endDrag();
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value);
});
</script>

<template>
  <div class="corners-picker">
    <p class="hint">
      选中一个角点后点击图片放置，或直接拖动角点到棋盘「落子网格」四角。
    </p>

    <NSpace size="small" class="corner-tabs">
      <NButton
        v-for="(label, i) in LABELS"
        :key="label"
        size="tiny"
        :type="activeCorner === i ? 'primary' : 'default'"
        @click="activeCorner = i"
      >
        {{ label }}
      </NButton>
    </NSpace>

    <div
      class="img-wrap"
      :style="imageBoxStyle"
      @pointerdown="placeActiveCorner"
    >
      <img
        ref="imgEl"
        :src="objectUrl"
        class="shot"
        draggable="false"
        @load="onImgLoad"
      />
      <!-- 连线 -->
      <svg v-if="disp.w" class="overlay" :width="disp.w" :height="disp.h">
        <polygon
          :points="pts.map((p) => `${p.x},${p.y}`).join(' ')"
          fill="rgba(255,215,0,0.12)"
          stroke="#ffd700"
          stroke-width="2"
        />
      </svg>
      <!-- 角点手柄 -->
      <div
        v-for="(p, i) in pts"
        :key="i"
        class="handle"
        :class="{ active: activeCorner === i }"
        :style="{ left: p.x + 'px', top: p.y + 'px' }"
        @pointerdown="startDrag(i, $event)"
      >
        <span class="handle-label">{{ LABELS[i] }}</span>
      </div>
    </div>

    <NSpace justify="space-between" class="actions">
      <NButton size="small" @click="emit('cancel')">重选图片</NButton>
      <NSpace>
        <NButton v-if="props.showAuto" size="small" @click="emit('auto')">自动定位识别</NButton>
        <NButton size="small" type="primary" @click="confirm">用框选的四角识别</NButton>
      </NSpace>
    </NSpace>
  </div>
</template>

<style scoped>
.corners-picker {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}
.hint {
  margin: 0;
  font-size: 12px;
  color: #a99472;
  line-height: 1.5;
}
.img-wrap {
  position: relative;
  align-self: center;
  overflow: visible;
  line-height: 0;
  cursor: crosshair;
  user-select: none;
  touch-action: none;
}
.shot {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 4px;
}
.overlay {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
}
.handle {
  position: absolute;
  width: 22px;
  height: 22px;
  margin-left: -11px;
  margin-top: -11px;
  border: 2px solid #ffd700;
  border-radius: 50%;
  background: rgba(255, 215, 0, 0.35);
  cursor: grab;
  touch-action: none;
}
.handle:active {
  cursor: grabbing;
}
.handle.active {
  background: rgba(255, 215, 0, 0.7);
  box-shadow: 0 0 0 4px rgba(255, 215, 0, 0.18);
}
.handle-label {
  position: absolute;
  left: 50%;
  top: -18px;
  transform: translateX(-50%);
  font-size: 11px;
  color: #ffd700;
  white-space: nowrap;
  pointer-events: none;
}
.actions {
  margin-top: 4px;
}
.corner-tabs {
  min-height: 26px;
  align-items: center;
}
</style>
