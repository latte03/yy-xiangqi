"""
本地识别后端 (FastAPI sidecar)。

接口:
  GET  /health              健康检查
  POST /recognize           上传截图 → 返回 FEN + 每格结果

前后端走 localhost HTTP。打包时用 PyInstaller 打成单二进制，作 Tauri sidecar。
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import uuid
from typing import List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import json

from recognizer.pipeline import get_classifier, recognize
from recognizer.locate import get_locator
from recognizer import model_store, model_update

app = FastAPI(title="xiangqi-endgame recognizer", version="0.1.0")

# 开发期允许 Vite dev server 跨域；打包后前端走 tauri 同源/localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CellOut(BaseModel):
    rank: int
    file: int
    type: str
    color: str
    confidence: float


class RecognizeOut(BaseModel):
    ok: bool
    fen: str = ""
    side: str = "red"
    cells: List[CellOut] = []
    low_confidence: List[List[int]] = []
    needs_review: bool = False
    message: str = ""


class TrainingStatusOut(BaseModel):
    running: bool = False
    phase: str = "idle"
    ok: bool = True
    message: str = ""
    logs: List[str] = []
    updated_at: float = 0


class ModelUpdateStatusOut(BaseModel):
    running: bool = False
    phase: str = "idle"
    ok: bool = True
    message: str = ""
    percent: int = 0
    logs: List[str] = []
    updated_at: float = 0


class GenerateDataIn(BaseModel):
    per_class: int = 1000
    val_frac: float = 0.15
    real_repeat: int = 8
    clean: bool = True


class TrainModelIn(BaseModel):
    epochs: int = 20
    batch: int = 128
    lr: float = 1e-3
    export_only: bool = False


class CheckModelIn(BaseModel):
    split: str = "val"


class GenLocateDataIn(BaseModel):
    num: int = 4000
    val_frac: float = 0.12
    photo_frac: float = 0.5
    clean: bool = True
    use_real_labels: bool = True


class TrainLocatorIn(BaseModel):
    epochs: int = 40
    batch: int = 64
    lr: float = 1e-3
    export_only: bool = False


ROOT = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(ROOT, "uploads")
LOCATE_LABELS_DIR = os.path.join(ROOT, "locate_labels")
MAX_LOG_LINES = 240

_training_lock = threading.Lock()
_training_status = {
    "running": False,
    "phase": "idle",
    "ok": True,
    "message": "",
    "logs": [],
    "updated_at": 0.0,
}

_model_update_lock = threading.Lock()
_model_update_status = {
    "running": False,
    "phase": "idle",
    "ok": True,
    "message": "",
    "percent": 0,
    "logs": [],
    "updated_at": 0.0,
}


def _set_training_status(**kwargs) -> None:
    with _training_lock:
        _training_status.update(kwargs)
        _training_status["updated_at"] = time.time()


def _set_model_update_status(**kwargs) -> None:
    with _model_update_lock:
        _model_update_status.update(kwargs)
        _model_update_status["updated_at"] = time.time()


def _append_training_log(line: str) -> None:
    with _training_lock:
        logs = list(_training_status.get("logs", []))
        logs.append(line.rstrip())
        _training_status["logs"] = logs[-MAX_LOG_LINES:]
        _training_status["updated_at"] = time.time()


def _append_model_update_log(line: str) -> None:
    with _model_update_lock:
        logs = list(_model_update_status.get("logs", []))
        logs.append(line.rstrip())
        _model_update_status["logs"] = logs[-MAX_LOG_LINES:]
        _model_update_status["updated_at"] = time.time()


def _model_update_progress(message: str, percent: Optional[int] = None, phase: Optional[str] = None) -> None:
    updates = {"message": message}
    if percent is not None:
        updates["percent"] = max(0, min(100, int(percent)))
    if phase is not None:
        updates["phase"] = phase
    _set_model_update_status(**updates)
    _append_model_update_log(message)


def _python_cmd(script: str, *args: str) -> list[str]:
    return [sys.executable, os.path.join("tools", script), *args]


def _run_command_job(phase: str, cmd: list[str]) -> None:
    def worker() -> None:
        _set_training_status(running=True, phase=phase, ok=True, message="", logs=[])
        _append_training_log("$ " + " ".join(cmd))
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            process = subprocess.Popen(
                cmd,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                _append_training_log(line)
            code = process.wait()
            if code == 0:
                _set_training_status(running=False, phase=phase, ok=True, message="任务完成")
            else:
                _set_training_status(running=False, phase=phase, ok=False, message=f"任务失败，退出码 {code}")
        except Exception as exc:
            _append_training_log(str(exc))
            _set_training_status(running=False, phase=phase, ok=False, message=str(exc))

    with _training_lock:
        if _training_status.get("running"):
            raise RuntimeError("已有训练任务正在运行，请等待完成。")
    threading.Thread(target=worker, daemon=True).start()


def _run_model_update_job() -> None:
    def worker() -> None:
        _set_model_update_status(running=True, phase="checking", ok=True, message="准备检查模型更新…", percent=1, logs=[])
        try:
            res = model_update.apply_update(progress=_model_update_progress)
            _set_model_update_status(
                running=False,
                phase="done" if res.get("ok") else "failed",
                ok=bool(res.get("ok")),
                message=str(res.get("message") or ""),
                percent=100 if res.get("ok") else int(_model_update_status.get("percent", 0)),
            )
        except Exception as exc:
            _append_model_update_log(str(exc))
            _set_model_update_status(running=False, phase="failed", ok=False, message=str(exc))

    with _model_update_lock:
        if _model_update_status.get("running"):
            raise RuntimeError("已有模型更新任务正在运行。")
    threading.Thread(target=worker, daemon=True).start()


@app.get("/health")
def health():
    clf = get_classifier()
    loc = get_locator()
    return {
        "status": "ok",
        "model_ready": clf.ready,
        "model_path": getattr(clf, "model_path", ""),
        "locator_ready": loc.ready,  # 定位 CNN 是否就绪 (否则回退经典/手动框选)
        "message": "" if clf.ready else getattr(clf, "error", "CNN 模型未就绪。"),
    }


@app.post("/recognize", response_model=RecognizeOut)
async def recognize_endpoint(
    image: UploadFile = File(...),
    side: str = Form("red"),
    corners: Optional[str] = Form(None),  # "x0,y0;x1,y1;x2,y2;x3,y3" 可选手动四角
):
    raw = await image.read()
    arr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return RecognizeOut(ok=False, message="无法解码图像。", needs_review=True)

    manual = None
    if corners:
        try:
            manual = np.array(
                [[float(v) for v in p.split(",")] for p in corners.split(";")],
                dtype=np.float32,
            )
            if manual.shape != (4, 2):
                manual = None
        except Exception:
            manual = None

    res = recognize(img, corners=manual, side=side)
    return RecognizeOut(
        ok=res.ok,
        fen=res.fen,
        side=res.side,
        cells=[CellOut(rank=c.rank, file=c.file, type=c.type, color=c.color, confidence=c.confidence) for c in res.cells],
        low_confidence=[[r, f] for (r, f) in res.low_confidence],
        needs_review=res.needs_review,
        message=res.message,
    )


@app.get("/training/status", response_model=TrainingStatusOut)
def training_status():
    with _training_lock:
        return TrainingStatusOut(**_training_status)


@app.post("/training/extract-crops", response_model=TrainingStatusOut)
async def training_extract_crops(
    image: UploadFile = File(...),
    fen: str = Form(...),
    corners: Optional[str] = Form(None),
):
    raw = await image.read()
    arr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return TrainingStatusOut(ok=False, message="无法解码图像。")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(image.filename or "")[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        ext = ".png"
    image_path = os.path.join(UPLOAD_DIR, f"train_{uuid.uuid4().hex}{ext}")
    cv2.imwrite(image_path, img)

    cmd = _python_cmd("extract_crops.py", image_path, fen)
    if corners:
        cmd.extend(["--corners", corners])
        # 同一张「图+四角」也作为定位 CNN 的真实标注存档 (一举两得)
        _save_locate_label(image_path, corners)
    try:
        _run_command_job("extract-crops", cmd)
    except RuntimeError as exc:
        return TrainingStatusOut(running=True, phase="busy", ok=False, message=str(exc))
    return training_status()


def _save_locate_label(image_path: str, corners: str) -> None:
    """把手动/已知四角存成定位训练标注 locate_labels/<name>.json。"""
    try:
        pts = [[float(v) for v in p.split(",")] for p in corners.split(";")]
        if len(pts) != 4:
            return
        os.makedirs(LOCATE_LABELS_DIR, exist_ok=True)
        name = os.path.splitext(os.path.basename(image_path))[0]
        json.dump(
            {"image": os.path.abspath(image_path), "corners": pts},
            open(os.path.join(LOCATE_LABELS_DIR, f"{name}.json"), "w", encoding="utf-8"),
        )
    except Exception:
        pass


@app.post("/training/generate-data", response_model=TrainingStatusOut)
def training_generate_data(payload: GenerateDataIn):
    cmd = _python_cmd(
        "gen_training_data.py",
        "--per-class",
        str(payload.per_class),
        "--val-frac",
        str(payload.val_frac),
        "--real-repeat",
        str(payload.real_repeat),
        "--real-crops",
        "crops",
    )
    if payload.clean:
        cmd.append("--clean")
    try:
        _run_command_job("generate-data", cmd)
    except RuntimeError as exc:
        return TrainingStatusOut(running=True, phase="busy", ok=False, message=str(exc))
    return training_status()


@app.post("/training/train-model", response_model=TrainingStatusOut)
def training_train_model(payload: TrainModelIn):
    cmd = _python_cmd(
        "train_classifier.py",
        "--epochs",
        str(payload.epochs),
        "--batch",
        str(payload.batch),
        "--lr",
        str(payload.lr),
    )
    if payload.export_only:
        cmd.append("--export-only")
    try:
        _run_command_job("train-model", cmd)
    except RuntimeError as exc:
        return TrainingStatusOut(running=True, phase="busy", ok=False, message=str(exc))
    return training_status()


@app.post("/training/check-model", response_model=TrainingStatusOut)
def training_check_model(payload: CheckModelIn):
    cmd = _python_cmd("check_model.py", "--data", "dataset", "--split", payload.split)
    try:
        _run_command_job("check-model", cmd)
    except RuntimeError as exc:
        return TrainingStatusOut(running=True, phase="busy", ok=False, message=str(exc))
    return training_status()


# ---------------- 棋盘四角定位 CNN (截图+翻拍统一) ----------------

@app.post("/training/gen-locate-data", response_model=TrainingStatusOut)
def training_gen_locate_data(payload: GenLocateDataIn):
    cmd = _python_cmd(
        "gen_locate_data.py",
        "--num", str(payload.num),
        "--val-frac", str(payload.val_frac),
        "--photo-frac", str(payload.photo_frac),
    )
    if payload.clean:
        cmd.append("--clean")
    if payload.use_real_labels and os.path.isdir(LOCATE_LABELS_DIR):
        cmd.extend(["--real-labels", "locate_labels"])
    try:
        _run_command_job("gen-locate-data", cmd)
    except RuntimeError as exc:
        return TrainingStatusOut(running=True, phase="busy", ok=False, message=str(exc))
    return training_status()


@app.post("/training/train-locator", response_model=TrainingStatusOut)
def training_train_locator(payload: TrainLocatorIn):
    cmd = _python_cmd(
        "train_locator.py",
        "--epochs", str(payload.epochs),
        "--batch", str(payload.batch),
        "--lr", str(payload.lr),
    )
    if payload.export_only:
        cmd.append("--export-only")
    try:
        _run_command_job("train-locator", cmd)
    except RuntimeError as exc:
        return TrainingStatusOut(running=True, phase="busy", ok=False, message=str(exc))
    return training_status()


# ---------------- 软件内模型更新 (走 GitHub Releases) ----------------

@app.get("/model/status")
def model_status():
    """当前模型来源（user 已更新 / bundled 内置）+ 版本。"""
    return model_store.installed_models_info()


@app.get("/model/check-update")
def model_check_update():
    """拉远端 manifest，对比本地版本。"""
    info = model_update.check_update()
    info.pop("manifest", None)  # 不回传完整 manifest
    return info


@app.get("/model/update-status", response_model=ModelUpdateStatusOut)
def model_update_status():
    """模型下载/应用进度。"""
    with _model_update_lock:
        return ModelUpdateStatusOut(**_model_update_status)


@app.post("/model/apply-update", response_model=ModelUpdateStatusOut)
def model_apply_update():
    """后台下载并应用模型更新（校验 sha256 + 试加载，通过才热替换）。"""
    try:
        _run_model_update_job()
    except RuntimeError as exc:
        return ModelUpdateStatusOut(running=True, phase="busy", ok=False, message=str(exc))
    return model_update_status()


if __name__ == "__main__":
    import uvicorn

    # 开发模式：设环境变量 XIANGQI_DEV=1 时自动热重载（改代码免手动重启）。
    # reload 需用 import 字符串形式，故分两种启动方式。
    dev = os.environ.get("XIANGQI_DEV") in ("1", "true", "True")
    host = os.environ.get("XIANGQI_HOST", "127.0.0.1")
    port = int(os.environ.get("XIANGQI_PORT", "8765"))
    if dev:
        print(f"[dev] 热重载已开启 → http://{host}:{port}")
        uvicorn.run("app:app", host=host, port=port, reload=True)
    else:
        uvicorn.run(app, host=host, port=port)
