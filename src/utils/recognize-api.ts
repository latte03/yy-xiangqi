/**
 * 截图识别后端客户端。
 * 与本地 sidecar (FastAPI) 走 localhost HTTP 通信。
 * 后端地址可通过 VITE_RECOGNIZE_API 覆盖，默认 127.0.0.1:8765。
 */

const BASE =
  (import.meta.env.VITE_RECOGNIZE_API as string | undefined) ?? 'http://127.0.0.1:8765';

export interface RecognizedCell {
  rank: number;
  file: number;
  type: string; // K/A/E/H/R/C/P 或 '?'
  color: 'red' | 'black';
  confidence: number;
}

export interface RecognizeResponse {
  ok: boolean;
  fen: string;
  side: 'red' | 'black';
  cells: RecognizedCell[];
  low_confidence: number[][]; // [[rank,file], ...] 低置信，需人工复核
  needs_review: boolean;
  message: string;
}

/** 健康检查：后端是否在线、CNN 模型是否就绪 */
export async function checkBackend(): Promise<{ online: boolean; modelReady: boolean; message: string }> {
  try {
    const r = await fetch(`${BASE}/health`, { method: 'GET' });
    if (!r.ok) return { online: false, modelReady: false, message: '' };
    const j = await r.json();
    return { online: true, modelReady: !!j.model_ready, message: j.message ?? '' };
  } catch {
    return { online: false, modelReady: false, message: '' };
  }
}

/** 上传截图识别，返回 FEN 与逐格结果 */
export async function recognizeImage(
  file: File,
  opts: { side?: 'red' | 'black'; corners?: string } = {},
): Promise<RecognizeResponse> {
  const form = new FormData();
  form.append('image', file);
  form.append('side', opts.side ?? 'red');
  if (opts.corners) form.append('corners', opts.corners);

  const r = await fetch(`${BASE}/recognize`, { method: 'POST', body: form });
  if (!r.ok) {
    throw new Error(`识别服务返回 ${r.status}`);
  }
  return (await r.json()) as RecognizeResponse;
}
