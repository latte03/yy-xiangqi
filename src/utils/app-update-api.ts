export interface AppUpdateProgress {
  event: 'Started' | 'Progress' | 'Finished';
  downloaded: number;
  contentLength: number;
  percent: number;
}

export interface AppUpdateResult {
  ok: boolean;
  available: boolean;
  version?: string;
  message: string;
}

export async function checkAndInstallAppUpdate(
  onProgress?: (progress: AppUpdateProgress) => void,
): Promise<AppUpdateResult> {
  if (!('__TAURI_INTERNALS__' in window)) {
    return { ok: true, available: false, message: '当前不是 Tauri 桌面环境。' };
  }

  const [{ check }, { relaunch }] = await Promise.all([
    import('@tauri-apps/plugin-updater'),
    import('@tauri-apps/plugin-process'),
  ]);
  const update = await check();
  if (!update) {
    return { ok: true, available: false, message: '已是最新版本。' };
  }

  let downloaded = 0;
  let contentLength = 0;
  await update.downloadAndInstall((event) => {
    if (event.event === 'Started') {
      downloaded = 0;
      contentLength = event.data.contentLength ?? 0;
    } else if (event.event === 'Progress') {
      downloaded += event.data.chunkLength;
    }
    const percent = contentLength > 0 ? Math.round((downloaded / contentLength) * 100) : 0;
    onProgress?.({
      event: event.event,
      downloaded,
      contentLength,
      percent,
    });
  });
  await relaunch();

  return {
    ok: true,
    available: true,
    version: update.version,
    message: `已安装 ${update.version}，正在重启。`,
  };
}
