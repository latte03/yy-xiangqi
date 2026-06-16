"""
训练小型 CNN 棋子类型分类器，导出 ONNX（截图路）。

在本机运行（需 PyTorch；沙箱无 torch）：
  pip install -r requirements-train.txt
  python tools/gen_training_data.py --per-class 1000 --real-crops crops
  python tools/train_classifier.py --epochs 20
  # 产物: models/piece_classifier.onnx (+ labels.txt)

模型很小（约 0.1–0.5M 参数，ONNX 量化后 1–3MB），CPU 推理足够快。
推理端 recognizer/classify.py 用 onnxruntime 加载，接口不变。
"""

from __future__ import annotations

import argparse
import glob
import os
import random
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recognizer.model_io import INPUT_SIZE, NUM_CLASSES, TYPES  # noqa: E402

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset


class CellDataset(Dataset):
    def __init__(self, root: str, split: str):
        self.items = []
        for ti, t in enumerate(TYPES):
            for p in glob.glob(os.path.join(root, split, t, "*.png")):
                self.items.append((p, ti))
        if not self.items:
            raise RuntimeError(f"{root}/{split} 下没有样本，请先跑 gen_training_data.py")

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        p, y = self.items[i]
        g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        g = cv2.resize(g, (INPUT_SIZE, INPUT_SIZE))
        x = torch.from_numpy((g.astype("float32") / 255.0)[None, :, :])
        return x, y


class TinyCNN(nn.Module):
    """约 3 层卷积的小网络，64x64 灰度 → 7 类。"""

    def __init__(self, n=NUM_CLASSES):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(), nn.MaxPool2d(2),   # 32
            nn.Conv2d(16, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),  # 16
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2),  # 8
            nn.AdaptiveAvgPool2d(4),  # 4x4
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Dropout(0.3), nn.Linear(64 * 16, n))

    def forward(self, x):
        return self.head(self.features(x))


def evaluate(model, loader, device):
    model.eval()
    correct = total = 0
    confusion = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=np.int64)
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            pred = model(x).argmax(1).cpu()
            for yi, pi in zip(y.numpy(), pred.numpy()):
                confusion[int(yi), int(pi)] += 1
            correct += (pred == y).sum().item()
            total += len(y)
    return correct / max(total, 1), confusion


def format_confusion(confusion: np.ndarray) -> str:
    header = "true\\pred " + " ".join(f"{t:>5}" for t in TYPES)
    rows = [header]
    for i, t in enumerate(TYPES):
        rows.append(f"{t:>9} " + " ".join(f"{int(v):>5}" for v in confusion[i]))
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="dataset")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--out", default="models/piece_classifier.onnx")
    ap.add_argument("--checkpoint", default="models/piece_classifier.pt")
    ap.add_argument("--export-only", action="store_true", help="从 checkpoint 重新导出 ONNX，不重新训练")
    ap.add_argument("--opset", type=int, default=17, help="ONNX opset 版本；默认 17，避免新 exporter 回转 opset 11 的转换器问题")
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

    model = TinyCNN().to(device)
    out_path = os.path.join(root, args.out)
    ckpt_path = os.path.join(root, args.checkpoint)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    os.makedirs(os.path.dirname(ckpt_path), exist_ok=True)

    if args.export_only:
        export_from_checkpoint(model, ckpt_path, out_path, device, args.opset)
        return

    train = DataLoader(CellDataset(data_root, "train"), batch_size=args.batch, shuffle=True, num_workers=args.workers)
    val = DataLoader(CellDataset(data_root, "val"), batch_size=args.batch, num_workers=args.workers)

    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs)
    lossf = nn.CrossEntropyLoss()

    best = 0.0
    best_confusion = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=np.int64)
    for ep in range(args.epochs):
        model.train()
        running_loss = 0.0
        seen = 0
        for x, y in train:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = lossf(model(x), y)
            loss.backward()
            opt.step()
            running_loss += float(loss.item()) * len(y)
            seen += len(y)
        sched.step()
        acc, confusion = evaluate(model, val, device)
        print(f"epoch {ep+1}/{args.epochs}  loss={running_loss / max(seen, 1):.4f}  val_acc={acc:.4f}")
        if acc >= best:
            best = acc
            best_confusion = confusion
            torch.save(
                {
                    "model": model.state_dict(),
                    "types": TYPES,
                    "input_size": INPUT_SIZE,
                    "val_acc": best,
                    "epoch": ep + 1,
                },
                ckpt_path,
            )
            export_onnx(model, out_path, device, args.opset)
            verify_onnx(model, out_path, device)
    # 写标签顺序
    with open(os.path.join(os.path.dirname(out_path), "labels.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(TYPES))
    print("最佳模型混淆矩阵:")
    print(format_confusion(best_confusion))
    print(f"完成。最佳 val_acc={best:.4f}，模型 → {out_path}，checkpoint → {ckpt_path}")


def export_from_checkpoint(model, ckpt_path, out_path, device, opset):
    if not os.path.isfile(ckpt_path):
        raise FileNotFoundError(f"未找到 checkpoint: {ckpt_path}")
    ckpt = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(ckpt["model"])
    export_onnx(model, out_path, device, opset)
    verify_onnx(model, out_path, device)
    with open(os.path.join(os.path.dirname(out_path), "labels.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(TYPES))
    print(
        f"已从 checkpoint 导出 ONNX → {out_path}"
        + (f"，checkpoint val_acc={ckpt.get('val_acc'):.4f}" if ckpt.get("val_acc") is not None else "")
    )


def export_onnx(model, path, device, opset):
    model.eval()
    dummy = torch.zeros(1, 1, INPUT_SIZE, INPUT_SIZE, device=device)
    torch.onnx.export(
        model, (dummy,), path,
        input_names=["input"], output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=opset,
        dynamo=False,
        external_data=False,
    )


def ensure_export_dependencies():
    missing = []
    for name in ("onnx", "onnxruntime"):
        try:
            __import__(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise RuntimeError(
            "缺少 ONNX 导出/校验依赖: "
            + ", ".join(missing)
            + "。请在 backend 虚拟环境中运行: pip install -r requirements-train.txt"
        )


def verify_onnx(model, path, device):
    """导出后抽样对比 PyTorch/ONNX logits，避免模型文件不可加载或输出漂移过大。"""
    import onnxruntime as ort

    model.eval()
    x = torch.rand(4, 1, INPUT_SIZE, INPUT_SIZE, device=device)
    with torch.no_grad():
        torch_logits = model(x).detach().cpu().numpy()
    session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    name = session.get_inputs()[0].name
    onnx_logits = session.run(None, {name: x.detach().cpu().numpy()})[0]
    max_diff = float(np.abs(torch_logits - onnx_logits).max())
    if max_diff > 1e-4:
        raise RuntimeError(f"ONNX 导出校验失败，max_diff={max_diff:.6f}")


if __name__ == "__main__":
    main()
