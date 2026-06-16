"""
ONNX 模型自检工具。

用法:
  python tools/check_model.py
  python tools/check_model.py --data dataset --split val
  python tools/check_model.py --image path/to/crop.png

不依赖后端服务启动，直接加载 models/piece_classifier.onnx，检查模型能否加载、
推理耗时、单图预测或数据集准确率。
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recognizer.model_io import MODEL_PATH_DEFAULT, TYPES, preprocess_gray  # noqa: E402


def softmax(logits: np.ndarray) -> np.ndarray:
    e = np.exp(logits - logits.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


class OnnxModel:
    def __init__(self, path: str):
        import onnxruntime as ort

        if not os.path.isfile(path):
            raise FileNotFoundError(f"未找到模型文件: {path}")
        so = ort.SessionOptions()
        so.log_severity_level = 3
        self.session = ort.InferenceSession(path, sess_options=so, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def predict_batch(self, images: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        x = np.stack([preprocess_gray(im) for im in images], axis=0).astype(np.float32)
        logits = self.session.run(None, {self.input_name: x})[0]
        prob = softmax(logits)
        return prob.argmax(axis=1), prob.max(axis=1)


def load_dataset(root: str, split: str) -> list[tuple[str, int]]:
    items: list[tuple[str, int]] = []
    for idx, t in enumerate(TYPES):
        for path in sorted(glob.glob(os.path.join(root, split, t, "*.png"))):
            items.append((path, idx))
    if not items:
        raise RuntimeError(f"{root}/{split} 下没有样本。")
    return items


def check_dataset(model: OnnxModel, root: str, split: str, batch: int) -> None:
    items = load_dataset(root, split)
    confusion = np.zeros((len(TYPES), len(TYPES)), dtype=np.int64)
    total = correct = 0
    low: list[tuple[str, str, str, float]] = []
    t0 = time.perf_counter()
    for i in range(0, len(items), batch):
        chunk = items[i : i + batch]
        images = []
        labels = []
        paths = []
        for path, label in chunk:
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            images.append(img)
            labels.append(label)
            paths.append(path)
        if not images:
            continue
        pred, conf = model.predict_batch(images)
        for path, y, p, c in zip(paths, labels, pred, conf):
            confusion[y, int(p)] += 1
            total += 1
            correct += int(y == int(p))
            if y != int(p):
                low.append((path, TYPES[y], TYPES[int(p)], float(c)))
    elapsed = time.perf_counter() - t0
    print(f"dataset={root}/{split} samples={total} acc={correct / max(total, 1):.4f}")
    print(f"avg_latency={elapsed / max(total, 1) * 1000:.3f}ms/crop")
    print_confusion(confusion)
    if low:
        print("误判样本 Top 20:")
        for path, want, got, conf in low[:20]:
            print(f"  want={want} got={got} conf={conf:.3f}  {path}")


def check_image(model: OnnxModel, path: str) -> None:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"无法读取图片: {path}")
    pred, conf = model.predict_batch([img])
    print(f"{path}")
    print(f"pred={TYPES[int(pred[0])]} confidence={float(conf[0]):.4f}")


def print_confusion(confusion: np.ndarray) -> None:
    print("true\\pred " + " ".join(f"{t:>5}" for t in TYPES))
    for i, t in enumerate(TYPES):
        print(f"{t:>9} " + " ".join(f"{int(v):>5}" for v in confusion[i]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL_PATH_DEFAULT)
    parser.add_argument("--data", default=None, help="数据集目录，例如 dataset")
    parser.add_argument("--split", default="val")
    parser.add_argument("--image", default=None, help="单张 crop 图片")
    parser.add_argument("--batch", type=int, default=256)
    args = parser.parse_args()

    root = os.path.join(os.path.dirname(__file__), "..")
    model_path = args.model if os.path.isabs(args.model) else os.path.join(root, args.model)
    model = OnnxModel(model_path)
    print(f"model={os.path.abspath(model_path)}")

    if args.image:
        image_path = args.image if os.path.isabs(args.image) else os.path.join(root, args.image)
        check_image(model, image_path)
    elif args.data:
        data_root = args.data if os.path.isabs(args.data) else os.path.join(root, args.data)
        check_dataset(model, data_root, args.split, args.batch)
    else:
        dummy = np.zeros((64, 64), dtype=np.uint8)
        pred, conf = model.predict_batch([dummy])
        print(f"load_ok=true dummy_pred={TYPES[int(pred[0])]} confidence={float(conf[0]):.4f}")


if __name__ == "__main__":
    main()
