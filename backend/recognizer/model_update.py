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
from .locate_model import LOC_INPUT, NUM_COORDS
from .model_io import INPUT_SIZE, NUM_CLASSES

Progress = Optional[Callable[[str, Optional[int], Optional[str]], None]]

EXPECTED_MODELS = {
    "piece_classifier.onnx": {
        "input_tail": [1, INPUT_SIZE, INPUT_SIZE],
        "output_tail": [NUM_CLASSES],
    },
    "board_locator.onnx": {
        "input_tail": [1, LOC_INPUT, LOC_INPUT],
        "output_tail": [NUM_COORDS],
    },
}


def _log(cb: Progress, msg: str, percent: Optional[int] = None, phase: Optional[str] = None) -> None:
    if cb:
        cb(msg, percent, phase)


def fetch_manifest(url: Optional[str] = None, timeout: int = 15) -> dict:
    url = url or model_store.manifest_url()
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (受信任的自有发布地址)
        return json.loads(r.read().decode("utf-8"))


def check_update(timeout: int = 15) -> dict:
    """返回 {ok, current_version, latest_version, has_update, files, message}。"""
    current = model_store.active_version()
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


def _dim_tail_matches(shape: list, expected_tail: list[int]) -> bool:
    if len(shape) < len(expected_tail):
        return False
    return all(actual == expected for actual, expected in zip(shape[-len(expected_tail):], expected_tail))


def _verify_onnx_contract(name: str, path: str) -> None:
    """试用 onnxruntime 加载，并校验模型文件名对应的输入输出契约。"""
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    session = ort.InferenceSession(path, sess_options=so, providers=["CPUExecutionProvider"])
    expected = EXPECTED_MODELS.get(name)
    if not expected:
        raise ValueError(f"不支持的模型文件: {name}")
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if len(inputs) != 1 or len(outputs) != 1:
        raise ValueError(f"{name} 输入/输出数量不符合预期。")
    if not _dim_tail_matches(list(inputs[0].shape), expected["input_tail"]):
        raise ValueError(f"{name} 输入 shape 不符合预期: {inputs[0].shape}")
    if not _dim_tail_matches(list(outputs[0].shape), expected["output_tail"]):
        raise ValueError(f"{name} 输出 shape 不符合预期: {outputs[0].shape}")


def _validate_manifest(manifest: dict) -> List[Dict]:
    files: List[Dict] = manifest.get("files", [])
    if not files:
        raise ValueError("manifest 未包含任何模型文件。")
    if any(not f.get("name") for f in files):
        raise ValueError("manifest 文件项缺少 name。")
    by_name = {f.get("name"): f for f in files}
    expected = set(model_store.MODEL_FILES)
    got = set(by_name)
    if got != expected:
        missing = ", ".join(sorted(expected - got)) or "无"
        extra = ", ".join(sorted(got - expected)) or "无"
        raise ValueError(f"模型 Release 必须完整包含两个 ONNX（缺失: {missing}; 多余: {extra}）。")
    for name, f in by_name.items():
        if not f.get("url"):
            raise ValueError(f"{name} 缺少 url。")
        sha256 = (f.get("sha256") or "").lower()
        if len(sha256) != 64:
            raise ValueError(f"{name} 缺少有效 sha256。")
        f["sha256"] = sha256
    return [by_name[name] for name in model_store.MODEL_FILES]


def _download_file(url: str, path: str, timeout: int, progress: Progress, start: int, span: int) -> None:
    with urllib.request.urlopen(url, timeout=timeout) as r, open(path, "wb") as out:  # noqa: S310
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total > 0:
                percent = start + int(min(done / total, 1.0) * span)
                _log(progress, f"下载中 {os.path.basename(path)} ({done}/{total} bytes)", percent, "downloading")


def apply_update(manifest: Optional[dict] = None, timeout: int = 60, progress: Progress = None) -> dict:
    """
    下载并应用 manifest 中的模型文件。返回 {ok, version, applied, message}。
    全程对临时文件操作，校验通过后才原子替换；失败不动现有模型。
    """
    if manifest is None:
        _log(progress, "获取模型更新信息…", 5, "checking")
        info = check_update(timeout=timeout)
        if not info["ok"]:
            return {"ok": False, "message": info["message"]}
        manifest = info["manifest"]

    version = int(manifest.get("version", 0))
    current = model_store.active_version()
    if version <= current:
        return {"ok": True, "version": current, "applied": [], "message": "已是最新模型。"}
    try:
        files = _validate_manifest(manifest)
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}

    dest_dir = model_store.user_model_dir(create=True)
    packages_dir = os.path.join(dest_dir, "packages")
    os.makedirs(packages_dir, exist_ok=True)
    package_dir = os.path.join(packages_dir, str(version))
    tmp_package = tempfile.mkdtemp(prefix=f".{version}-", dir=packages_dir)
    staged: List[str] = []

    try:
        for index, f in enumerate(files):
            name, url, want = f.get("name"), f.get("url"), (f.get("sha256") or "").lower()
            _log(progress, f"下载 {name} …", 10 + index * 35, "downloading")
            tmp_path = os.path.join(tmp_package, name)
            try:
                _download_file(url, tmp_path, timeout, progress, 10 + index * 35, 25)
            except Exception as exc:
                return {"ok": False, "message": f"下载 {name} 失败：{exc}"}

            _log(progress, f"校验 {name} …", 35 + index * 35, "verifying")
            got = _sha256(tmp_path)
            if got != want:
                return {"ok": False, "message": f"{name} 校验失败（sha256 不匹配）。"}
            try:
                _verify_onnx_contract(name, tmp_path)
            except Exception as exc:
                return {"ok": False, "message": f"{name} 无法加载，已放弃更新：{exc}"}

            staged.append(name)

        # 全部校验通过 → 发布一个完整版本目录，再更新 version.json 指针
        _log(progress, "应用模型更新…", 90, "applying")
        if os.path.isdir(package_dir):
            shutil.rmtree(package_dir)
        os.rename(tmp_package, package_dir)
        tmp_package = ""
    finally:
        if tmp_package and os.path.isdir(tmp_package):
            shutil.rmtree(tmp_package, ignore_errors=True)

    applied = staged
    model_store.set_local_model_package(version, package_dir)
    _hot_reload()
    _log(progress, f"完成，已更新到版本 {version}：{', '.join(applied)}", 100, "done")
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
