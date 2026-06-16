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

from recognizer.pipeline import get_classifier, recognize

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


ROOT = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(ROOT, "uploads")
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


def _set_training_status(**kwargs) -> None:
    with _training_lock:
        _training_status.update(kwargs)
        _training_status["updated_at"] = time.time()


def _append_training_log(line: str) -> None:
    with _training_lock:
        logs = list(_training_status.get("logs", []))
        logs.append(line.rstrip())
        _training_status["logs"] = logs[-MAX_LOG_LINES:]
        _training_status["updated_at"] = time.time()


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


@app.get("/health")
def health():
    clf = get_classifier()
    return {
        "status": "ok",
        "model_ready": clf.ready,
        "model_path": getattr(clf, "model_path", ""),
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
    try:
        _run_command_job("extract-crops", cmd)
    except RuntimeError as exc:
        return TrainingStatusOut(running=True, phase="busy", ok=False, message=str(exc))
    return training_status()


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
