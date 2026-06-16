"""
训练裁剪提取工具：从一张「已知布局」的干净截图收集真实棋子 crop。

用法:
  python tools/extract_crops.py <screenshot> <fen> [--corners x0,y0;x1,y1;x2,y2;x3,y3]

  - screenshot: 一张清晰的《燕云十六声》游戏截图
  - fen:        该局面的正确 FEN (可先用前端编辑器手动摆好后复制 FEN 预览)
  - corners:    可选，手动四角 (落子网格左上,右上,右下,左下)；不传则自动检测

输出到 backend/crops/{red,black}/{type}_{idx}.png，供 gen_training_data.py --real-crops crops 混入训练。
这些 crop 只用于训练，不参与运行时识别。
"""

from __future__ import annotations

import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recognizer.fen import FILES, RANKS  # noqa: E402
from recognizer.locate import auto_detect_corners, warp_to_canonical  # noqa: E402
from recognizer.slice import slice_cells  # noqa: E402

# FEN 字符 → 内部 type
FEN_TO_TYPE = {"K": "K", "A": "A", "B": "E", "E": "E", "N": "H", "H": "H", "R": "R", "C": "C", "P": "P"}


def parse_fen_board(fen: str):
    board_part = fen.strip().split()[0]
    ranks = board_part.split("/")
    assert len(ranks) == RANKS, f"FEN 需 {RANKS} 行"
    grid = [[None] * FILES for _ in range(RANKS)]
    for r, row in enumerate(ranks):
        f = 0
        for ch in row:
            if ch.isdigit():
                f += int(ch)
            else:
                t = FEN_TO_TYPE[ch.upper()]
                color = "red" if ch.isupper() else "black"
                grid[r][f] = (t, color)
                f += 1
    return grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("screenshot")
    ap.add_argument("fen")
    ap.add_argument("--corners", default=None)
    args = ap.parse_args()

    img = cv2.imread(args.screenshot, cv2.IMREAD_COLOR)
    assert img is not None, "无法读取截图"

    if args.corners:
        corners = np.array([[float(v) for v in p.split(",")] for p in args.corners.split(";")], dtype=np.float32)
    else:
        corners = auto_detect_corners(img)
        assert corners is not None, "自动定位失败，请用 --corners 手动指定四角"

    warped = warp_to_canonical(img, corners)
    cells = slice_cells(warped)
    grid = parse_fen_board(args.fen)

    import glob

    out_root = os.path.join(os.path.dirname(__file__), "..", "crops")
    # 每类保存所有实例；idx 从已有样本数续编，多次跑不同截图会累加而非覆盖。
    counter: dict = {}
    for r in range(RANKS):
        for f in range(FILES):
            piece = grid[r][f]
            if piece is None:
                continue
            t, color = piece
            key = (color, t)
            if key not in counter:
                existing = len(glob.glob(os.path.join(out_root, color, f"{t}_*.png")))
                counter[key] = existing
            idx = counter[key]
            counter[key] = idx + 1
            # 存原始分辨率灰度裁剪，保留细节；生成训练数据时再统一缩放/增强。
            g = cv2.cvtColor(cells[r][f], cv2.COLOR_BGR2GRAY)
            d = os.path.join(out_root, color)
            os.makedirs(d, exist_ok=True)
            cv2.imwrite(os.path.join(d, f"{t}_{idx}.png"), g)

    total = sum(counter.values())
    print(f"完成，共 {total} 个训练裁剪，覆盖 {len(counter)} 个(颜色,类型)。")
    print("缺失类型可换一张含该子的截图再跑补齐 (以新 idx 追加)。")


if __name__ == "__main__":
    main()
