/**
 * 软件内模型更新（走 GitHub Releases）。
 *
 * 从 Editor 抽出：检查更新 → 下载应用 → 轮询进度 → 自动停轮询。
 * 组件卸载时自动清理定时器。
 */
import { onBeforeUnmount, ref } from 'vue';
import {
  checkModelUpdate,
  applyModelUpdate,
  getModelUpdateStatus,
  type ModelUpdateStatus,
} from '@/utils/model-update-api';

export function useModelUpdate() {
  const updating = ref(false);
  const message = ref('');
  const hasUpdate = ref(false);
  const percent = ref(0);
  let poll: number | null = null;

  function applyStatus(status: ModelUpdateStatus) {
    updating.value = status.running;
    percent.value = status.percent;
    message.value = status.message;
    if (!status.running) {
      stopPolling();
      if (status.ok) hasUpdate.value = false;
    }
  }

  function stopPolling() {
    if (poll !== null) {
      window.clearInterval(poll);
      poll = null;
    }
  }

  function startPolling() {
    stopPolling();
    poll = window.setInterval(async () => {
      try {
        applyStatus(await getModelUpdateStatus());
      } catch (err) {
        stopPolling();
        updating.value = false;
        message.value = err instanceof Error ? err.message : '获取更新进度失败。';
      }
    }, 700);
  }

  async function checkUpdate() {
    updating.value = true;
    message.value = '';
    hasUpdate.value = false;
    percent.value = 0;
    try {
      const res = await checkModelUpdate();
      hasUpdate.value = !!res.has_update;
      message.value =
        res.message +
        (res.has_update ? `（v${res.current_version} → v${res.latest_version}）` : '');
    } catch (err) {
      message.value = err instanceof Error ? err.message : '检查更新失败。';
    } finally {
      updating.value = false;
    }
  }

  async function applyUpdate() {
    updating.value = true;
    percent.value = 1;
    message.value = '下载并应用中…';
    try {
      const status = await applyModelUpdate();
      applyStatus(status);
      if (status.running) startPolling();
    } catch (err) {
      message.value = err instanceof Error ? err.message : '更新失败。';
      percent.value = 0;
      updating.value = false;
    } finally {
      if (poll === null) updating.value = false;
    }
  }

  onBeforeUnmount(stopPolling);

  return { updating, message, hasUpdate, percent, checkUpdate, applyUpdate };
}
