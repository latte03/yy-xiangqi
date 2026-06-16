/**
 * Vue composable: 引擎无关的 AI 调用接口
 * UI 层只依赖这个, 不直接接触具体引擎
 */

import { ref, shallowRef } from 'vue';
import type { AiEngineOptions, AiMoveResult } from './engine';

export function useAiEngine() {
  const thinking = ref(false);
  const lastResult = shallowRef<AiMoveResult | null>(null);
  const error = shallowRef<string | null>(null);
  const worker = shallowRef<Worker | null>(null);
  let nextJobId = 1;

  async function ensureWorker(): Promise<Worker> {
    if (worker.value) return worker.value;
    worker.value = new Worker('/stockfish/engine-worker.js');
    return worker.value;
  }

  async function askBestMove(options: AiEngineOptions): Promise<AiMoveResult> {
    thinking.value = true;
    error.value = null;
    try {
      const w = await ensureWorker();
      const jobId = String(nextJobId++);
      return await new Promise<AiMoveResult>((resolve, reject) => {
        const handler = (e: MessageEvent) => {
          const data = e.data as { jobId: string; result?: AiMoveResult; error?: string };
          if (data.jobId !== jobId) return;
          w.removeEventListener('message', handler);
          if (data.error) {
            error.value = data.error;
            reject(new Error(data.error));
          } else if (data.result) {
            lastResult.value = data.result;
            resolve(data.result);
          }
        };
        w.addEventListener('message', handler);
        w.postMessage({ jobId, options });
      });
    } finally {
      thinking.value = false;
    }
  }

  function dispose() {
    worker.value?.terminate();
    worker.value = null;
  }

  return { thinking, lastResult, error, askBestMove, dispose };
}
