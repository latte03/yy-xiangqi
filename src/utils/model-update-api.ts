/**
 * 软件内模型更新客户端（走本地 sidecar → GitHub Releases）。
 */

const BASE =
  (import.meta.env.VITE_RECOGNIZE_API as string | undefined) ?? 'http://127.0.0.1:8765';

export interface ModelStatus {
  version: number;
  active_version: number;
  user_version: number;
  bundled_version: number;
  user_package_complete: boolean;
  bundled_package_complete: boolean;
  user_model_dir: string;
  user_active_model_dir: string;
  bundled_model_dir: string;
  sources: Record<string, 'user' | 'bundled' | 'missing'>;
  manifest_url: string;
}

export interface CheckUpdateResult {
  ok: boolean;
  current_version: number;
  latest_version?: number;
  has_update: boolean;
  files?: string[];
  message: string;
}

export interface ApplyUpdateResult {
  running: boolean;
  phase: string;
  ok: boolean;
  message: string;
  percent: number;
  logs: string[];
  updated_at: number;
}

export type ModelUpdateStatus = ApplyUpdateResult;

export async function getModelStatus(): Promise<ModelStatus> {
  const r = await fetch(`${BASE}/model/status`);
  if (!r.ok) throw new Error(`模型状态返回 ${r.status}`);
  return (await r.json()) as ModelStatus;
}

export async function checkModelUpdate(): Promise<CheckUpdateResult> {
  const r = await fetch(`${BASE}/model/check-update`);
  if (!r.ok) throw new Error(`检查更新返回 ${r.status}`);
  return (await r.json()) as CheckUpdateResult;
}

export async function applyModelUpdate(): Promise<ApplyUpdateResult> {
  const r = await fetch(`${BASE}/model/apply-update`, { method: 'POST' });
  if (!r.ok) throw new Error(`应用更新返回 ${r.status}`);
  return (await r.json()) as ApplyUpdateResult;
}

export async function getModelUpdateStatus(): Promise<ModelUpdateStatus> {
  const r = await fetch(`${BASE}/model/update-status`);
  if (!r.ok) throw new Error(`更新进度返回 ${r.status}`);
  return (await r.json()) as ModelUpdateStatus;
}
