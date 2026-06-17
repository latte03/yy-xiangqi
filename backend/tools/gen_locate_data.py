"""
棋盘四角定位 CNN 的合成数据生成器（截图路 + 翻拍路统一）。

为每张样本：
  1. 渲染一个「半透明棋盘层」(面板边框 + 淡网格线 + 九宫斜线 + 河界 + 若干亮圆盘棋子)，
     已知其落子网格四角在该层中的坐标。
  2. 随机背景 (偏暗场景纹理) + 随机单应把棋盘放进画面：
       - screenshot régime：近正对、轻透视、清晰、暗底；
       - photo régime：强透视、反光高光、摩尔纹、模糊、偏色 (模拟手机翻拍屏幕)。
  3. 同一单应作用到四角 → 标注。
  4. 全局增强后输出整图 + letterbox 归一化四角标签。

可混入真实标注：--real-labels 指向 locate_labels/ (每个 .json: {"image": "..","corners": [[x,y]*4]})。

用法 (本机)：
  python tools/gen_locate_data.py --num 4000
  python tools/gen_locate_data.py --num 4000 --real-labels locate_labels
产物：locate_dataset/{train,val}/img_*.png + labels.json + manifest.json
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
from recognizer.locate_model import LOC_INPUT, encode_corners  # noqa: E402

CELL = 64
FILES, RANKS = 9, 10
MARGIN = 46  # 网格到面板边的留白
PIECES = list("帅仕相马车炮兵将士象卒")

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/Songti.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "C:/Windows/Fonts/simsun.ttc",
]


def load_font():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    raise FileNotFoundError("未找到 CJK 字体，请安装 Noto CJK 或传系统字体")


def render_board_layer(font_path: str):
    """
    渲染半透明棋盘层 (BGRA)，返回 (layer_bgra, grid_corners(4,2))。
    grid_corners = 落子网格四角 [TL,TR,BR,BL] 在该层坐标。
    """
    gw = (FILES - 1) * CELL
    gh = (RANKS - 1) * CELL
    W = gw + 2 * MARGIN
    H = gh + 2 * MARGIN
    # 面板底 (灰度) + alpha
    panel = random.randint(70, 130)
    base = np.full((H, W), panel, np.float32)
    base += cv2.resize(np.random.randn(8, 8).astype(np.float32), (W, H)) * random.uniform(4, 14)
    base = np.clip(base, 0, 255)
    img = Image.fromarray(base.astype(np.uint8)).convert("L")
    draw = ImageDraw.Draw(img)

    ox, oy = MARGIN, MARGIN
    line = random.randint(150, 210)
    lw = 1
    # 横线
    for r in range(RANKS):
        y = oy + r * CELL
        draw.line([(ox, y), (ox + gw, y)], fill=line, width=lw)
    # 竖线 (河界处中间断开，最外两列通到底)
    for c in range(FILES):
        x = ox + c * CELL
        if c == 0 or c == FILES - 1:
            draw.line([(x, oy), (x, oy + gh)], fill=line, width=lw)
        else:
            draw.line([(x, oy), (x, oy + 4 * CELL)], fill=line, width=lw)
            draw.line([(x, oy + 5 * CELL), (x, oy + gh)], fill=line, width=lw)
    # 九宫斜线 (上下)
    for top in (True, False):
        c0 = ox + 3 * CELL
        r0 = oy + (0 if top else 7) * CELL
        draw.line([(c0, r0), (c0 + 2 * CELL, r0 + 2 * CELL)], fill=line, width=lw)
        draw.line([(c0 + 2 * CELL, r0), (c0, r0 + 2 * CELL)], fill=line, width=lw)
    # 外框
    draw.rectangle([ox - 14, oy - 14, ox + gw + 14, oy + gh + 14], outline=random.randint(170, 230), width=2)

    # 随机摆几枚棋子 (亮圆盘 + 字)
    n = random.randint(3, 18)
    cells = [(r, c) for r in range(RANKS) for c in range(FILES)]
    random.shuffle(cells)
    for r, c in cells[:n]:
        cx, cy = ox + c * CELL, oy + r * CELL
        rad = int(CELL * random.uniform(0.40, 0.46))
        draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad],
                     fill=random.randint(200, 248), outline=random.randint(90, 150), width=2)
        ch = random.choice(PIECES)
        fs = int(rad * 1.4)
        font = ImageFont.truetype(font_path, fs)
        b = draw.textbbox((0, 0), ch, font=font)
        draw.text((cx - (b[2] - b[0]) // 2 - b[0], cy - (b[3] - b[1]) // 2 - b[1]),
                  ch, fill=random.randint(20, 110), font=font)

    gray = np.array(img)
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    # alpha：面板区域半透明，外面全透明
    alpha = np.zeros((H, W), np.float32)
    alpha[oy - 14 : oy + gh + 14, ox - 14 : ox + gw + 14] = random.uniform(0.55, 0.9)
    bgra = np.dstack([bgr, (alpha * 255)])
    corners = np.float32([[ox, oy], [ox + gw, oy], [ox + gw, oy + gh], [ox, oy + gh]])
    return bgra.astype(np.uint8), corners


def random_background(w: int, h: int, regime: str) -> np.ndarray:
    """暗色场景背景。"""
    base = random.randint(8, 45)
    bg = np.full((h, w, 3), base, np.float32)
    # 低频色块 (场景透出)
    blobs = cv2.resize(np.random.rand(6, 10, 3).astype(np.float32), (w, h)) * random.uniform(20, 70)
    bg = np.clip(bg + blobs, 0, 255)
    if regime == "photo":
        bg += cv2.resize(np.random.rand(4, 6, 3).astype(np.float32), (w, h)) * 30
    return np.clip(bg, 0, 255).astype(np.uint8)


def add_moire(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    f = random.uniform(0.15, 0.5)
    ang = random.uniform(0, np.pi)
    patt = np.sin((xx * np.cos(ang) + yy * np.sin(ang)) * f) * random.uniform(6, 18)
    return np.clip(img.astype(np.float32) + patt[:, :, None], 0, 255).astype(np.uint8)


def add_glare(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    overlay = np.zeros((h, w), np.float32)
    for _ in range(random.randint(1, 3)):
        cx, cy = random.randint(0, w), random.randint(0, h)
        rad = random.randint(int(w * 0.1), int(w * 0.4))
        g = np.zeros((h, w), np.float32)
        cv2.circle(g, (cx, cy), rad, 1.0, -1)
        g = cv2.GaussianBlur(g, (0, 0), rad * 0.5)
        overlay += g * random.uniform(40, 120)
    return np.clip(img.astype(np.float32) + overlay[:, :, None], 0, 255).astype(np.uint8)


def compose_sample(font_path: str, regime: str):
    """生成一张样本，返回 (image_bgr, corners_px(4,2))。"""
    layer, lcorners = render_board_layer(font_path)
    lh, lw = layer.shape[:2]

    # 画面尺寸 (随机宽高比，模拟不同设备)
    W = random.choice([1280, 1440, 1600, 1080, 960])
    H = int(W * random.uniform(0.45, 0.7))
    bg = random_background(W, H, regime)

    # 目标四角：把棋盘层放到画面某处，加透视
    scale = random.uniform(0.5, 0.9) * min(W / lw, H / lh)
    bw, bh = lw * scale, lh * scale
    # 棋盘多偏左 (符合游戏 UI)，但也随机
    x0 = random.uniform(0.02, 0.55) * (W - bw)
    y0 = random.uniform(0.02, 0.4) * (H - bh)
    base_dst = np.float32([[x0, y0], [x0 + bw, y0], [x0 + bw, y0 + bh], [x0, y0 + bh]])
    # 透视扰动：截图弱、翻拍强
    jitter = (0.012 if regime == "screenshot" else 0.06) * max(bw, bh)
    dst = base_dst + np.random.uniform(-jitter, jitter, base_dst.shape).astype(np.float32)

    src = np.float32([[0, 0], [lw, 0], [lw, lh], [0, lh]])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(layer, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    a = warped[:, :, 3:4].astype(np.float32) / 255.0
    comp = (warped[:, :, :3].astype(np.float32) * a + bg.astype(np.float32) * (1 - a)).astype(np.uint8)

    # 网格四角经同一单应
    pts = cv2.perspectiveTransform(lcorners[None, :, :], M)[0]

    # ---- 全局增强 ----
    if regime == "photo":
        if random.random() < 0.8:
            comp = add_glare(comp)
        if random.random() < 0.7:
            comp = add_moire(comp)
        if random.random() < 0.8:
            k = random.choice([3, 5, 7])
            comp = cv2.GaussianBlur(comp, (k, k), 0)
        # 偏色 (白平衡)
        comp = np.clip(comp.astype(np.float32) * np.random.uniform(0.8, 1.2, 3), 0, 255).astype(np.uint8)
    else:
        if random.random() < 0.4:
            comp = cv2.GaussianBlur(comp, (3, 3), 0)
    comp = np.clip(comp.astype(np.float32) * random.uniform(0.8, 1.15) + random.uniform(-15, 15), 0, 255).astype(np.uint8)
    if random.random() < 0.7:
        comp = np.clip(comp.astype(np.float32) + np.random.randn(H, W, 3) * random.uniform(2, 12), 0, 255).astype(np.uint8)
    if random.random() < 0.6:
        q = random.randint(35, 88)
        ok, enc = cv2.imencode(".jpg", comp, [cv2.IMWRITE_JPEG_QUALITY, q])
        if ok:
            comp = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return comp, pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--num", type=int, default=4000, help="合成样本总数")
    ap.add_argument("--val-frac", type=float, default=0.12)
    ap.add_argument("--photo-frac", type=float, default=0.5, help="翻拍 régime 占比")
    ap.add_argument("--out", default="locate_dataset")
    ap.add_argument("--real-labels", default=None, help="真实标注目录 (*.json: image+corners)")
    ap.add_argument("--real-repeat", type=int, default=20)
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    font_path = load_font()
    root = os.path.join(os.path.dirname(__file__), "..")
    out_root = os.path.join(root, args.out)
    if args.clean and os.path.isdir(out_root):
        shutil.rmtree(out_root)

    labels: dict = {}
    counts = {"train": 0, "val": 0}

    def save(split: str, name: str, img: np.ndarray, corners_px: np.ndarray):
        d = os.path.join(out_root, split)
        os.makedirs(d, exist_ok=True)
        cv2.imwrite(os.path.join(d, name), img)
        h, w = img.shape[:2]
        labels[f"{split}/{name}"] = encode_corners(corners_px, w, h).tolist()
        counts[split] += 1

    for i in range(args.num):
        regime = "photo" if random.random() < args.photo_frac else "screenshot"
        img, pts = compose_sample(font_path, regime)
        split = "val" if random.random() < args.val_frac else "train"
        save(split, f"img_{i:05d}.png", img, pts)

    # 真实标注：轻增强复制进训练集
    real_n = 0
    if args.real_labels:
        ldir = os.path.join(root, args.real_labels)
        for jp in glob.glob(os.path.join(ldir, "*.json")):
            meta = json.load(open(jp, encoding="utf-8"))
            ip = meta["image"]
            if not os.path.isabs(ip):
                ip = os.path.join(ldir, ip)
            img = cv2.imread(ip)
            if img is None:
                continue
            corners = np.float32(meta["corners"])
            for k in range(args.real_repeat):
                aug = np.clip(img.astype(np.float32) * random.uniform(0.85, 1.15) + random.uniform(-12, 12), 0, 255).astype(np.uint8)
                if random.random() < 0.5:
                    aug = cv2.GaussianBlur(aug, (3, 3), 0)
                save("train", f"real_{real_n}.png", aug, corners)
                real_n += 1

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "loc_input": LOC_INPUT,
        "num": args.num,
        "photo_frac": args.photo_frac,
        "val_frac": args.val_frac,
        "real_labels": args.real_labels,
        "real_samples": real_n,
        "counts": counts,
        "seed": args.seed,
    }
    os.makedirs(out_root, exist_ok=True)
    json.dump(labels, open(os.path.join(out_root, "labels.json"), "w", encoding="utf-8"))
    json.dump(manifest, open(os.path.join(out_root, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"完成：train={counts['train']} val={counts['val']} real={real_n} → {os.path.abspath(out_root)}")


if __name__ == "__main__":
    main()
