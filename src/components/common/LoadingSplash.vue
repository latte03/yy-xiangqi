<script setup lang="ts">
/**
 * 启动加载遮罩：在后端 sidecar 冷启动探测期间显示。
 * 用一枚棋子循环切换「帅·仕·相·马·车·炮·兵」作为加载动画。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue';

defineProps<{ text?: string }>();

const GLYPHS = ['帅', '仕', '相', '马', '车', '炮', '兵'];
const idx = ref(0);
let timer: number | null = null;

onMounted(() => {
  timer = window.setInterval(() => {
    idx.value = (idx.value + 1) % GLYPHS.length;
  }, 420);
});
onBeforeUnmount(() => {
  if (timer !== null) window.clearInterval(timer);
});
</script>

<template>
  <div class="splash">
    <div class="coin">
      <Transition name="flip" mode="out-in">
        <span :key="idx" class="glyph">{{ GLYPHS[idx] }}</span>
      </Transition>
    </div>
    <p class="splash-text">{{ text || '正在启动识别服务…' }}</p>
  </div>
</template>

<style scoped>
.splash {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 22px;
  background:
    radial-gradient(circle at 50% 40%, rgba(40, 28, 18, 0.96), rgba(12, 10, 8, 0.98));
}
.coin {
  width: 96px;
  height: 96px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 2px solid #5a3519;
  background: radial-gradient(circle at 38% 32%, #fff7df 0%, #efcf8f 70%, #bd813f 100%);
  box-shadow: 0 14px 40px rgba(0, 0, 0, 0.5);
}
.glyph {
  font-family: 'Songti SC', 'STSong', 'SimSun', serif;
  font-size: 52px;
  font-weight: 800;
  color: #a93628;
}
.splash-text {
  margin: 0;
  color: #d8c4a2;
  font-size: 14px;
  letter-spacing: 0.04em;
}
.flip-enter-active,
.flip-leave-active {
  transition: transform 0.22s ease, opacity 0.22s ease;
}
.flip-enter-from {
  transform: rotateX(80deg);
  opacity: 0;
}
.flip-leave-to {
  transform: rotateX(-80deg);
  opacity: 0;
}
</style>
