"""
训练棋盘四角定位 CNN，导出 ONNX (截图路 + 翻拍路统一)。

本机运行 (需 PyTorch；沙箱无 torch)：
  pip install -r requirements-train.txt
  python tools/gen_locate_data.py --num 4000
  python tools/train_locator.py --epochs 40
  # 产物: models/board_locator.onnx

输出 8 个值 = 四角 (TL,TR,BR,BL) 在 letterbox 图中的归一化坐标 [0,1]，sigmoid 约束。
推理端 recognizer/locate.py 用 onnxruntime 加载。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recognizer.locate_model import LOC_INPUT, NUM_COORDS  # noqa: E402

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset


class BoardDataset(Dataset):
    def __init__(self, root: str, split: str, labels: dict):
        self.root = root
        self.items = [(k, v) for k, v in labels.items() if k.startswith(split + "/")]
        if not self.items:
            raise RuntimeError(f"{root} 下 split={split} 无样本，请先跑 gen_locate_data.py")

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        rel, label = self.items[i]
        g = cv2.imread(os.path.join(self.root, rel), cv2.IMREAD_GRAYSCALE)
        g = cv2.resize(g, (LOC_INPUT, LOC_INPUT))
        x = torch.from_numpy((g.astype("float32") / 255.0)[None, :, :])
        y = torch.tensor(label, dtype=torch.float32)
        return x, y


class LocatorCNN(nn.Module):
    """约 4 层卷积的小网络，256x256 灰度 → 8 坐标 (sigmoid)。"""

    def __init__(self, n=NUM_COORDS):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, 2, 1), nn.BatchNorm2d(16), nn.ReLU(),    # 128
            nn.Conv2d(16, 32, 3, 2, 1), nn.BatchNorm2d(32), nn.ReLU(),   # 64
            nn.Conv2d(32, 64, 3, 2, 1), nn.BatchNorm2d(64), nn.ReLU(),   # 32
            nn.Conv2d(64, 96, 3, 2, 1), nn.BatchNorm2d(96), nn.ReLU(),   # 16
            nn.AdaptiveAvgPool2d(4),                                     # 4x4
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Dropout(0.2), nn.Linear(96 * 16, 128), nn.ReLU(), nn.Linear(128, n))

    def forward(self, x):
        return torch.sigmoid(self.head(self.features(x)))


def mean_corner_error(model, loader, device) -> float:
    """验证集四角平均误差 (letterbox 归一化距离 × LOC_INPUT = 像素)。"""
    model.eval()
    total, n = 0.0, 0
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            p = model(x).cpu().numpy().reshape(-1, 4, 2)
            t = y.numpy().reshape(-1, 4, 2)
            d = np.linalg.norm((p - t) * LOC_INPUT, axis=2)  # 每角像素误差
            total += d.sum()
            n += d.size
    return total / max(n, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="locate_dataset")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--out", default="models/board_locator.onnx")
    ap.add_argument("--checkpoint", default="models/board_locator.pt")
    ap.add_argument("--export-only", action="store_true")
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()

    ensure_export_dependencies()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    root = os.path.join(os.path.dirname(__file__), "..")
    data_root = os.path.join(root, args.data)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    out_path = os.path.join(root, args.out)
    ckpt_path = os.path.join(root, args.checkpoint)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    model = LocatorCNN().to(device)
    if args.export_only:
        export_from_checkpoint(model, ckpt_path, out_path, device, args.opset)
        return

    labels = json.load(open(os.path.join(data_root, "labels.json"), encoding="utf-8"))
    train = DataLoader(BoardDataset(data_root, "train", labels), batch_size=args.batch, shuffle=True, num_workers=args.workers)
    val = DataLoader(BoardDataset(data_root, "val", labels), batch_size=args.batch, num_workers=args.workers)

    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs)
    lossf = nn.SmoothL1Loss()

    best = 1e9
    for ep in range(args.epochs):
        model.train()
        run, seen = 0.0, 0
        for x, y in train:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = lossf(model(x), y)
            loss.backward()
            opt.step()
            run += float(loss.item()) * len(y)
            seen += len(y)
        sched.step()
        err = mean_corner_error(model, val, device)
        print(f"epoch {ep+1}/{args.epochs}  loss={run/max(seen,1):.5f}  val_corner_err={err:.2f}px(@{LOC_INPUT})")
        if err <= best:
            best = err
            torch.save({"model": model.state_dict(), "loc_input": LOC_INPUT, "val_corner_err": best, "epoch": ep + 1}, ckpt_path)
            export_onnx(model, out_path, device, args.opset)
            verify_onnx(model, out_path, device)
    print(f"完成。最佳 val_corner_err={best:.2f}px(@{LOC_INPUT}) → {out_path}")


def export_from_checkpoint(model, ckpt_path, out_path, device, opset):
    if not os.path.isfile(ckpt_path):
        raise FileNotFoundError(f"未找到 checkpoint: {ckpt_path}")
    ckpt = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(ckpt["model"])
    export_onnx(model, out_path, device, opset)
    verify_onnx(model, out_path, device)
    print(f"已从 checkpoint 导出 ONNX → {out_path}")


def export_onnx(model, path, device, opset):
    model.eval()
    dummy = torch.zeros(1, 1, LOC_INPUT, LOC_INPUT, device=device)
    torch.onnx.export(
        model, (dummy,), path,
        input_names=["input"], output_names=["corners"],
        dynamic_axes={"input": {0: "batch"}, "corners": {0: "batch"}},
        opset_version=opset, dynamo=False, external_data=False,
    )


def ensure_export_dependencies():
    missing = [n for n in ("onnx", "onnxruntime") if _missing(n)]
    if missing:
        raise RuntimeError("缺少 ONNX 依赖: " + ", ".join(missing) + "。请 pip install -r requirements-train.txt")


def _missing(name: str) -> bool:
    try:
        __import__(name)
        return False
    except ModuleNotFoundError:
        return True


def verify_onnx(model, path, device):
    import onnxruntime as ort

    model.eval()
    x = torch.rand(2, 1, LOC_INPUT, LOC_INPUT, device=device)
    with torch.no_grad():
        ref = model(x).cpu().numpy()
    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    got = sess.run(None, {sess.get_inputs()[0].name: x.cpu().numpy()})[0]
    md = float(np.abs(ref - got).max())
    if md > 1e-4:
        raise RuntimeError(f"ONNX 校验失败 max_diff={md:.6f}")


if __name__ == "__main__":
    main()
