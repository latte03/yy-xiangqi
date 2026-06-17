/**
 * 全局 UI 状态（供底部状态栏等跨组件读取）。
 * 与业务逻辑解耦：只放「展示用」的轻量状态。
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useUiStore = defineStore('ui', () => {
  const backendOnline = ref(false); // 识别后端是否在线
  const modelReady = ref(false); // 棋子识别模型是否就绪
  const modelVersion = ref<number | null>(null); // 当前生效模型版本
  const cursorText = ref(''); // 当前光标所在格（编辑器）
  const contextText = ref(''); // 当前界面上下文（如校验摘要 / FEN 简述）

  function setBackend(online: boolean, ready: boolean, version: number | null) {
    backendOnline.value = online;
    modelReady.value = ready;
    modelVersion.value = version;
  }

  return { backendOnline, modelReady, modelVersion, cursorText, contextText, setBackend };
});
