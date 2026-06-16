"""
合成训练数据生成器（截图路 CNN）。

为 7 个类型 (K/A/E/H/R/C/P) 各渲染大量「亮圆盘 + 真实汉字」棋格，叠加强增强，
模拟真实截图在分辨率/光照/模糊/噪声/透视/JPEG 上的差异，使小型 CNN 能跨图泛化。

  红黑同型字不同 (帅/将)，都作为该型样本；马/车/炮红黑字形相同。
  输出灰度图到 dataset/{train,val}/{type}/*.png，标签=类型。

用法:
  python tools/gen_training_data.py --per-class 800
  python tools/gen_training_data.py --per-class 800 --real-crops crops  # 混入真实裁剪

注：本机有真实截图时，强烈建议用 extract_crops.py 收集真实裁剪并用 --real-crops
混入，能显著提升真实场景准确率。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import random
import shutil
from datetime import datetime, timezone

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recognizer.model_io import INPUT_SIZE, TYPES  # noqa: E402

# 类型 → (红字, 黑字)
CHARS = {
    "K": ("帅", "将"), "A": ("仕", "士"), "E": ("相", "象"),
    "H": ("马", "马"), "R": ("车", "车"), "C": ("炮", "炮"), "P": ("兵", "卒"),
}

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/Songti.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def load_fonts(extra_fonts: list[str]) -> list:
    fonts = [p for p in extra_fonts if os.path.isfile(p)]
    fonts.extend(p for p in FONT_CANDIDATES if os.path.isfile(p))
    if not fonts:
        raise FileNotFoundError("未找到 CJK 字体，请安装 Noto CJK、使用系统中文字体，或传 --font /path/to/font")
    return fonts


def render_cell(ch: str, color: str, fonts: list, canvas: int = 96) -> np.ndarray:
    """渲染一个带增强的棋格灰度图。"""
    # 背景：透出场景，偏暗，随机底色 + 低频纹理
    base = random.randint(18, 75)
    img = Image.new("L", (canvas, canvas), base)
    arr = np.array(img).astype(np.float32)
    # 低频纹理
    tex = cv2.resize(np.random.randn(6, 6).astype(np.float32), (canvas, canvas)) * random.uniform(3, 12)
    arr = np.clip(arr + tex, 0, 255)
    img = Image.fromarray(arr.astype(np.uint8))
    draw = ImageDraw.Draw(img)

    # 圆盘：亮，半径/位置/亮度抖动
    cx = canvas // 2 + random.randint(-3, 3)
    cy = canvas // 2 + random.randint(-3, 3)
    r = int(canvas * random.uniform(0.40, 0.47))
    disc = random.randint(195, 248)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=disc, outline=random.randint(90, 150), width=random.randint(1, 3))

    # 字：颜色深浅 (红字灰度偏中, 黑字偏深)，字号/字体/粗细抖动
    dark = random.randint(70, 115) if color == "red" else random.randint(15, 55)
    font_path = random.choice(fonts)
    target = int(r * 2 * random.uniform(0.62, 0.78))
    size = target
    for _ in range(8):
        font = ImageFont.truetype(font_path, size)
        b = draw.textbbox((0, 0), ch, font=font)
        cw, chh = b[2] - b[0], b[3] - b[1]
        sc = target / max(cw, chh)
        if 0.95 <= sc <= 1.06:
            break
        size = max(8, int(size * sc))
    font = ImageFont.truetype(font_path, size)
    b = draw.textbbox((0, 0), ch, font=font)
    ox = cx - (b[2] - b[0]) // 2 - b[0]
    oy = cy - (b[3] - b[1]) // 2 - b[1]
    draw.text((ox, oy), ch, fill=dark, font=font)

    out = np.array(img)

    # ---- 增强 ----
    # 小角度旋转
    ang = random.uniform(-5, 5)
    M = cv2.getRotationMatrix2D((canvas / 2, canvas / 2), ang, 1.0)
    out = cv2.warpAffine(out, M, (canvas, canvas), borderMode=cv2.BORDER_REPLICATE)
    # 轻微透视
    if random.random() < 0.5:
        d = canvas * 0.06
        src = np.float32([[0, 0], [canvas, 0], [canvas, canvas], [0, canvas]])
        dst = src + np.random.uniform(-d, d, src.shape).astype(np.float32)
        out = cv2.warpPerspective(out, cv2.getPerspectiveTransform(src, dst), (canvas, canvas), borderMode=cv2.BORDER_REPLICATE)
    # 模糊
    if random.random() < 0.6:
        k = random.choice([3, 3, 5])
        out = cv2.GaussianBlur(out, (k, k), 0)
    # 亮度/对比度
    out = np.clip(out.astype(np.float32) * random.uniform(0.85, 1.15) + random.uniform(-12, 12), 0, 255).astype(np.uint8)
    # 分辨率抖动 (缩小再放大)
    if random.random() < 0.5:
        s = random.uniform(0.5, 0.85)
        small = cv2.resize(out, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        out = cv2.resize(small, (canvas, canvas), interpolation=cv2.INTER_LINEAR)
    # 高斯噪声
    if random.random() < 0.6:
        out = np.clip(out.astype(np.float32) + np.random.randn(canvas, canvas) * random.uniform(2, 10), 0, 255).astype(np.uint8)
    # JPEG 伪影
    if random.random() < 0.5:
        q = random.randint(40, 85)
        ok, enc = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, q])
        if ok:
            out = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)

    return cv2.resize(out, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=800, help="每类训练样本数")
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--out", default="dataset")
    ap.add_argument("--real-crops", default=None, help="真实裁剪目录 (crops/{red,black}/{type}_*.png)，混入并做轻增强")
    ap.add_argument("--real-repeat", type=int, default=8, help="每张真实裁剪复制增强次数")
    ap.add_argument("--font", action="append", default=[], help="额外 CJK 字体路径，可重复传入")
    ap.add_argument("--clean", action="store_true", help="生成前清空输出目录，避免旧样本污染")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    fonts = load_fonts(args.font)
    root = os.path.join(os.path.dirname(__file__), "..")
    out_root = os.path.join(root, args.out)
    if args.clean and os.path.isdir(out_root):
        shutil.rmtree(out_root)

    # 真实裁剪 (可选)
    real: dict = {t: [] for t in TYPES}
    if args.real_crops:
        rdir = os.path.join(root, args.real_crops)
        for color in ("red", "black"):
            for t in TYPES:
                for p in glob.glob(os.path.join(rdir, color, f"{t}*.png")):
                    im = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
                    if im is not None:
                        real[t].append(im)
        print("混入真实裁剪:", {t: len(v) for t, v in real.items() if v})

    counts = {"train": 0, "val": 0}
    for t in TYPES:
        for i in range(args.per_class):
            color = "red" if i % 2 == 0 else "black"
            img = render_cell(CHARS[t][0] if color == "red" else CHARS[t][1], color, fonts)
            split = "val" if random.random() < args.val_frac else "train"
            d = os.path.join(out_root, split, t)
            os.makedirs(d, exist_ok=True)
            cv2.imwrite(os.path.join(d, f"{t}_{i}.png"), img)
            counts[split] += 1
        # 真实裁剪：每张复制多份轻增强进训练集
        for j, im in enumerate(real[t]):
            for k in range(args.real_repeat):
                aug = cv2.resize(im, (INPUT_SIZE, INPUT_SIZE))
                aug = np.clip(aug.astype(np.float32) * random.uniform(0.9, 1.1) + random.uniform(-8, 8), 0, 255).astype(np.uint8)
                if random.random() < 0.5:
                    aug = cv2.GaussianBlur(aug, (3, 3), 0)
                d = os.path.join(out_root, "train", t)
                os.makedirs(d, exist_ok=True)
                cv2.imwrite(os.path.join(d, f"{t}_real{j}_{k}.png"), aug)
                counts["train"] += 1

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "types": TYPES,
        "input_size": INPUT_SIZE,
        "per_class": args.per_class,
        "val_frac": args.val_frac,
        "seed": args.seed,
        "fonts": fonts,
        "real_crops": args.real_crops,
        "real_repeat": args.real_repeat,
        "counts": counts,
        "real_counts": {t: len(v) for t, v in real.items()},
    }
    with open(os.path.join(out_root, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"完成：train={counts['train']} val={counts['val']} → {os.path.abspath(out_root)}")


if __name__ == "__main__":
    main()
