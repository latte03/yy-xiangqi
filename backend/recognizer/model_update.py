"""
软件内模型更新：从 GitHub Releases 拉取新模型，校验后热替换。

manifest (models.json) 格式：
  {
    "version": 3,
    "files": [
      {"name": "piece_classifier.onnx", "url": "https://.../piece_classifier.onnx", "sha256": "..."},
      {"name": "board_locator.onnx",    "url": "https://.../board_locator.onnx",    "sha256": "..."}
    ]
  }

流程：拉 manifest → 比本地版本 → 下载到临时文件 → 校验 sha256 + onnxruntime 试加载
→ 通过才移入用户模型目录 + 写版本 + 热重载；任一步失败保留旧模型，绝不变砖。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
from typing import Callable, Dict, List, Optional

from . import model_store

Progress = Optional[Callable[[str], None]]


def _log(cb: Progress, msg: str) -> None:
    if cb:
        cb(msg)


def fetch_manifest(url: Optional[str] = None, timeout: int = 15) -> dict:
    url = url or model_store.manifest_url()
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (受信任的自有发布地址)
        return json.loads(r.read().decode("utf-8"))


def check_update(timeout: int = 15) -> dict:
    """返回 {ok, current_version, latest_version, has_update, files, message}。"""
    current = model_store.local_version()
    try:
        manifest = fetch_manifest(timeout=timeout)
    except Exception as exc:
        return {"ok": False, "current_version": current, "has_update": False,
                "message": f"获取更新信息失败：{exc}"}
    latest = int(manifest.get("version", 0))
    files = manifest.get("files", [])
    return {
        "ok": True,
        "current_version": current,
        "latest_version": latest,
        "has_update": latest > current,
        "files": [f.get("name") for f in files],
        "manifest": manifest,
        "message": "有可用的模型更新。" if latest > current else "已是最新模型。",
    }


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_onnx_loadable(path: str) -> None:
    """试用 onnxruntime 加载，确保不是损坏/半截文件。"""
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    ort.InferenceSession(path, sess_options=so, providers=["CPUExecutionProvider"])


def apply_update(manifest: Optional[dict] = None, timeout: int = 60, progress: Progress = None) -> dict:
    """
    下载并应用 manifest 中的模型文件。返回 {ok, version, applied, message}。
    全程对临时文件操作，校验通过后才原子替换；失败不动现有模型。
    """
    if manifest is None:
        info = check_update(timeout=timeout)
        if not info["ok"]:
            return {"ok": False, "message": info["message"]}
        manifest = info["manifest"]

    version = int(manifest.get("version", 0))
    files: List[Dict] = manifest.get("files", [])
    if not files:
        return {"ok": False, "message": "manifest 未包含任何模型文件。"}

    dest_dir = model_store.user_model_dir(create=True)
    staged: List[tuple] = []  # (tmp_path, final_path, name)

    with tempfile.TemporaryDirectory() as tmp:
        for f in files:
            name, url, want = f.get("name"), f.get("url"), (f.get("sha256") or "").lower()
            if not name or not url:
                return {"ok": False, "message": f"manifest 文件项缺 name/url：{f}"}
            _log(progress, f"下载 {name} …")
            tmp_path = os.path.join(tmp, name)
            try:
                with urllib.request.urlopen(url, timeout=timeout) as r, open(tmp_path, "wb") as out:  # noqa: S310
                    shutil.copyfileobj(r, out)
            except Exception as exc:
                return {"ok": False, "message": f"下载 {name} 失败：{exc}"}

            if want:
                got = _sha256(tmp_path)
                if got != want:
                    return {"ok": False, "message": f"{name} 校验失败（sha256 不匹配）。"}
            try:
                _verify_onnx_loadable(tmp_path)
            except Exception as exc:
                return {"ok": False, "message": f"{name} 无法加载，已放弃更新：{exc}"}

            staged.append((tmp_path, os.path.join(dest_dir, name), name))

        # 全部校验通过 → 落盘替换
        applied = []
        for tmp_path, final_path, name in staged:
            shutil.copyfile(tmp_path, final_path)
            applied.append(name)

    model_store.set_local_version(version)
    _hot_reload()
    _log(progress, f"完成，已更新到版本 {version}：{', '.join(applied)}")
    return {"ok": True, "version": version, "applied": applied, "message": f"已更新到版本 {version}。"}


def _hot_reload() -> None:
    """替换模型后清推理缓存，下次识别用新模型。"""
    try:
        from .pipeline import reset_classifier
        from .locate import reset_locator

        reset_classifier()
        reset_locator()
    except Exception:
        pass
