/**
 * 棋盘 Konva 骨架（ChessBoard 与 Editor 共用）。
 *
 * 抽离两个组件原先各自复制的样板：
 *  - 建 Stage（尺寸固定 WIDTH×HEIGHT）
 *  - 底板层 + drawBoardLayer
 *  - 追加图层、指针坐标换算、销毁
 *  - 遍历棋盘绘制棋子的循环（paintPieces）
 *
 * 各组件仍保留自己的交互（落子/动画 vs 调色板/拖拽），
 * 只是不再重复维护这套底座。
 */
import Konva from 'konva';
import type { Board, Piece, Position } from '@/types';
import {
  addPiece,
  drawBoardLayer,
  FILES,
  RANKS,
  screenToCell,
  WIDTH,
  HEIGHT,
} from './board-drawing';

export interface BoardStage {
  stage: Konva.Stage;
  /** 底板层（棋盘底纹/格线/河界），已绘制 */
  boardLayer: Konva.Layer;
  /** 追加一个新图层并挂到 stage 上 */
  addLayer: () => Konva.Layer;
  /** 当前指针所在的格子（无则 null） */
  pointerCell: () => Position | null;
  /** 销毁 stage 及其所有图层 */
  destroy: () => void;
}

/** 创建棋盘 Stage，并画好底板层 */
export function createBoardStage(container: HTMLDivElement): BoardStage {
  const stage = new Konva.Stage({ container, width: WIDTH, height: HEIGHT });
  const boardLayer = new Konva.Layer();
  stage.add(boardLayer);
  drawBoardLayer(boardLayer);

  return {
    stage,
    boardLayer,
    addLayer() {
      const layer = new Konva.Layer();
      stage.add(layer);
      return layer;
    },
    pointerCell() {
      const pos = stage.getPointerPosition();
      return pos ? screenToCell(pos.x, pos.y) : null;
    },
    destroy() {
      stage.destroy();
    },
  };
}

export interface PaintPiecesOptions {
  /** 判断某格是否处于选中态 */
  isSelected?: (file: number, rank: number) => boolean;
  /** 每枚棋子绘制后回调，供调用方挂动画/拖拽/事件 */
  onNode?: (node: Konva.Group, piece: Piece, file: number, rank: number) => void;
}

/**
 * 清空图层并按棋盘重绘所有棋子。
 * 返回是否调用了 batchDraw（始终 true，便于链式）。
 */
export function paintPieces(
  layer: Konva.Layer,
  board: Board,
  options: PaintPiecesOptions = {},
): void {
  layer.destroyChildren();
  for (let r = 0; r < RANKS; r++) {
    for (let f = 0; f < FILES; f++) {
      const piece = board[r][f];
      if (!piece) continue;
      const selected = options.isSelected?.(f, r) ?? false;
      const node = addPiece(layer, piece, f, r, selected);
      options.onNode?.(node, piece, f, r);
    }
  }
  layer.batchDraw();
}
