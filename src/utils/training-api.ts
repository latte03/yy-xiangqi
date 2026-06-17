/**
 * 模型训练后端客户端。
 * 与本地 FastAPI sidecar 走 localhost HTTP 通信。
 */

const BASE =
  (import.meta.env.VITE_RECOGNIZE_API as string | undefined) ?? 'http://127.0.0.1:8765';

export interface TrainingStatus {
  running: boolean;
  phase: string;
  ok: boolean;
  message: string;
  logs: string[];
  updated_at: number;
}

async function readStatus(response: Response): Promise<TrainingStatus> {
  if (!response.ok) {
    throw new Error(`训练服务返回 ${response.status}`);
  }
  return (await response.json()) as TrainingStatus;
}

export async function getTrainingStatus(): Promise<TrainingStatus> {
  return readStatus(await fetch(`${BASE}/training/status`));
}

export async function extractTrainingCrops(
  file: File,
  payload: { fen: string; corners?: string },
): Promise<TrainingStatus> {
  const form = new FormData();
  form.append('image', file);
  form.append('fen', payload.fen);
  if (payload.corners) form.append('corners', payload.corners);
  return readStatus(await fetch(`${BASE}/training/extract-crops`, { method: 'POST', body: form }));
}

export async function generateTrainingData(payload: {
  per_class: number;
  val_frac: number;
  real_repeat: number;
  clean: boolean;
}): Promise<TrainingStatus> {
  return readStatus(await fetch(`${BASE}/training/generate-data`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }));
}

export async function trainModel(payload: {
  epochs: number;
  batch: number;
  lr: number;
  export_only: boolean;
}): Promise<TrainingStatus> {
  return readStatus(await fetch(`${BASE}/training/train-model`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }));
}

export async function checkModel(split = 'val'): Promise<TrainingStatus> {
  return readStatus(await fetch(`${BASE}/training/check-model`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ split }),
  }));
}

// ---------------- 棋盘四角定位 CNN (截图 + 翻拍统一) ----------------

export async function generateLocateData(payload: {
  num: number;
  val_frac: number;
  photo_frac: number;
  clean: boolean;
  use_real_labels: boolean;
}): Promise<TrainingStatus> {
  return readStatus(await fetch(`${BASE}/training/gen-locate-data`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }));
}

export async function trainLocator(payload: {
  epochs: number;
  batch: number;
  lr: number;
  export_only: boolean;
}): Promise<TrainingStatus> {
  return readStatus(await fetch(`${BASE}/training/train-locator`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }));
}
