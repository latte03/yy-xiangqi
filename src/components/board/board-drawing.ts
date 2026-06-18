import Konva from 'konva';
import type { Color, Piece, PieceType, Position } from '@/types';

export const CELL_SIZE = 58;
export const BOARD_PADDING = 36;
export const FILES = 9;
export const RANKS = 10;
export const WIDTH = CELL_SIZE * (FILES - 1) + BOARD_PADDING * 2;
export const HEIGHT = CELL_SIZE * (RANKS - 1) + BOARD_PADDING * 2;

const INK = '#553419';
const INK_SOFT = 'rgba(85, 52, 25, 0.68)';
const PIECE_DARK_INK = '#24201b';
const PIECE_RED_INK = '#a53427';
const PIECE_FACE = '#e8c37b';

export const PIECE_LABELS_RED: Record<PieceType, string> = {
  K: '帅',
  R: '车',
  C: '炮',
  H: '马',
  A: '仕',
  E: '相',
  P: '兵',
};

export const PIECE_LABELS_BLACK: Record<PieceType, string> = {
  K: '将',
  R: '车',
  C: '炮',
  H: '马',
  A: '士',
  E: '象',
  P: '卒',
};

export function pieceLabel(piece: Piece | null): string {
  if (!piece) return '';
  return piece.color === 'red' ? PIECE_LABELS_RED[piece.type] : PIECE_LABELS_BLACK[piece.type];
}

export function pieceInk(color: Color): string {
  return color === 'red' ? PIECE_RED_INK : PIECE_DARK_INK;
}

export function fileX(file: number): number {
  return BOARD_PADDING + file * CELL_SIZE;
}

export function rankY(rank: number): number {
  return BOARD_PADDING + rank * CELL_SIZE;
}

export function screenToCell(x: number, y: number): Position | null {
  const file = Math.round((x - BOARD_PADDING) / CELL_SIZE);
  const rank = Math.round((y - BOARD_PADDING) / CELL_SIZE);
  if (file < 0 || file >= FILES || rank < 0 || rank >= RANKS) return null;
  return { file, rank };
}

export function drawBoardLayer(layer: Konva.Layer): void {
  layer.destroyChildren();

  // 1) 底板：暖木色，柔和圆角与外投影
  layer.add(new Konva.Rect({
    x: 0,
    y: 0,
    width: WIDTH,
    height: HEIGHT,
    cornerRadius: 22,
    fillLinearGradientStartPoint: { x: 0, y: 0 },
    fillLinearGradientEndPoint: { x: WIDTH, y: HEIGHT },
    fillLinearGradientColorStops: [0, '#d89d57', 0.3, '#f2d293', 0.62, '#cf9a55', 1, '#8b4e21'],
    shadowColor: '#170b04',
    shadowBlur: 34,
    shadowOpacity: 0.4,
    shadowOffsetY: 16,
  }));

  // 2) 顺纹木纹：竖向细线，安静不抢戏
  for (let i = 1; i < 13; i++) {
    const x = 28 + (i * (WIDTH - 56)) / 13;
    layer.add(new Konva.Line({
      points: [x, 26, x + (((i % 3) - 1) * 2), HEIGHT - 26],
      stroke: i % 2 === 0 ? 'rgba(120, 68, 28, 0.05)' : 'rgba(255, 246, 214, 0.055)',
      strokeWidth: 1,
      listening: false,
    }));
  }

  // 3) 外框：单层深色细边（克制，不堆叠多重边框）
  layer.add(new Konva.Rect({
    x: 12,
    y: 12,
    width: WIDTH - 24,
    height: HEIGHT - 24,
    cornerRadius: 14,
    stroke: 'rgba(58, 31, 12, 0.7)',
    strokeWidth: 1.6,
  }));

  // 4) 楚河汉界 河道带
  layer.add(new Konva.Rect({
    x: fileX(0),
    y: rankY(4),
    width: CELL_SIZE * 8,
    height: CELL_SIZE,
    fillLinearGradientStartPoint: { x: 0, y: rankY(4) },
    fillLinearGradientEndPoint: { x: 0, y: rankY(5) },
    fillLinearGradientColorStops: [0, 'rgba(110, 58, 22, 0.04)', 0.5, 'rgba(255, 247, 220, 0.2)', 1, 'rgba(110, 58, 22, 0.04)'],
    listening: false,
  }));

  for (let rank = 0; rank < RANKS; rank++) {
    layer.add(new Konva.Line({
      points: [fileX(0), rankY(rank), fileX(FILES - 1), rankY(rank)],
      stroke: INK,
      strokeWidth: rank === 0 || rank === RANKS - 1 ? 2 : 1.15,
      lineCap: 'round',
    }));
  }

  for (let file = 0; file < FILES; file++) {
    const x = fileX(file);
    if (file === 0 || file === FILES - 1) {
      layer.add(new Konva.Line({
        points: [x, rankY(0), x, rankY(RANKS - 1)],
        stroke: INK,
        strokeWidth: 2,
        lineCap: 'round',
      }));
      continue;
    }

    layer.add(new Konva.Line({
      points: [x, rankY(0), x, rankY(4)],
      stroke: INK,
      strokeWidth: 1.1,
      lineCap: 'round',
    }));
    layer.add(new Konva.Line({
      points: [x, rankY(5), x, rankY(RANKS - 1)],
      stroke: INK,
      strokeWidth: 1.1,
      lineCap: 'round',
    }));
  }

  drawPalace(layer, 0);
  drawPalace(layer, 7);
  drawMarkers(layer);

  layer.add(new Konva.Text({
    x: fileX(1),
    y: rankY(4) + 13,
    width: CELL_SIZE * 3,
    align: 'center',
    text: '楚   河',
    fontSize: 27,
    fill: 'rgba(74, 41, 16, 0.5)',
    fontFamily: 'Songti SC, STSong, SimSun, serif',
    fontStyle: 'bold',
    shadowColor: 'rgba(255, 247, 222, 0.6)',
    shadowBlur: 0,
    shadowOffsetY: 1,
    shadowOpacity: 0.6,
    listening: false,
  }));
  layer.add(new Konva.Text({
    x: fileX(4),
    y: rankY(4) + 13,
    width: CELL_SIZE * 3,
    align: 'center',
    text: '汉   界',
    fontSize: 27,
    fill: 'rgba(74, 41, 16, 0.5)',
    fontFamily: 'Songti SC, STSong, SimSun, serif',
    fontStyle: 'bold',
    shadowColor: 'rgba(255, 247, 222, 0.6)',
    shadowBlur: 0,
    shadowOffsetY: 1,
    shadowOpacity: 0.6,
    listening: false,
  }));

  for (let file = 0; file < FILES; file++) {
    layer.add(new Konva.Text({
      x: fileX(file) - 6,
      y: HEIGHT - 26,
      text: String.fromCharCode(97 + file),
      fontSize: 11,
      fill: 'rgba(76, 47, 24, 0.52)',
      fontFamily: 'ui-monospace, monospace',
    }));
  }
  for (let rank = 0; rank < RANKS; rank++) {
    layer.add(new Konva.Text({
      x: 16,
      y: rankY(rank) - 7,
      text: String(rank + 1),
      fontSize: 11,
      fill: 'rgba(76, 47, 24, 0.52)',
      fontFamily: 'ui-monospace, monospace',
    }));
  }

  layer.batchDraw();
}

/** 棋盘上单格棋子的标准半径 */
export const PIECE_RADIUS = CELL_SIZE * 0.39;

/**
 * 以 (0,0) 为中心，把一枚棋子的完整造型画进一个 Konva.Group。
 * 棋盘棋子与候选棋子共用此函数，保证像素级一致。
 * 字号随半径等比缩放（棋盘半径对应 25px）。
 */
export function buildPieceGroup(
  piece: Piece,
  radius: number = PIECE_RADIUS,
  selected = false,
): Konva.Group {
  const fontSize = 26 * (radius / PIECE_RADIUS);
  const group = new Konva.Group();

  // 选中态：棋子外侧的柔和光晕
  if (selected) {
    group.add(new Konva.Circle({
      radius: radius + 2,
      fill: 'rgba(244, 194, 93, 0.18)',
      shadowColor: '#f4c85d',
      shadowBlur: 18,
      shadowOpacity: 0.85,
      listening: false,
    }));
  }

  // 1) 外盘：温润的木质/金边圆盘，自带接触阴影（取代以往多层同心圆）
  group.add(new Konva.Circle({
    radius,
    fillLinearGradientStartPoint: { x: 0, y: -radius },
    fillLinearGradientEndPoint: { x: 0, y: radius },
    fillLinearGradientColorStops: [0, '#f6dca0', 0.5, '#caa055', 1, '#8a5224'],
    stroke: selected ? '#f4c85d' : '#5d3415',
    strokeWidth: selected ? Math.max(1.6, radius * 0.07) : Math.max(1, radius * 0.045),
    shadowColor: '#1c0e05',
    shadowBlur: selected ? 12 : 8,
    shadowOpacity: selected ? 0.5 : 0.38,
    shadowOffsetY: radius * 0.16,
  }));

  // 2) 棋面：与外盘齐平的平整棋面（不做下沉），均匀的暖木色
  const faceR = radius * 0.9;
  group.add(new Konva.Circle({
    radius: faceR,
    fillLinearGradientStartPoint: { x: 0, y: -faceR },
    fillLinearGradientEndPoint: { x: 0, y: faceR },
    fillLinearGradientColorStops: [0, '#fff3d6', 0.55, PIECE_FACE, 1, '#e0ba75'],
    listening: false,
  }));

  // 3) 唯一的装饰刻线：棋面靠外沿的一圈细凹槽
  group.add(new Konva.Circle({
    radius: radius * 0.86,
    stroke: 'rgba(74, 40, 16, 0.5)',
    strokeWidth: Math.max(0.8, radius * 0.035),
    listening: false,
  }));

  // 4) 字：分层描绘出阴刻质感（上深下亮，字像刻进棋面）
  const label = pieceLabel(piece);
  const ink = pieceInk(piece.color);
  const mkText = (dy: number, fill: string) =>
    new Konva.Text({
      x: -radius,
      y: -radius + dy - 1,
      width: radius * 2,
      height: radius * 2,
      align: 'center',
      verticalAlign: 'middle',
      text: label,
      fontSize,
      fontStyle: 'bold',
      fill,
      fontFamily: 'Songti SC, STSong, SimSun, serif',
      listening: false,
    });
  // 上沿内阴影（加深、营造刻痕的上壁）
  group.add(mkText(-0.7 * (radius / PIECE_RADIUS), 'rgba(48, 26, 10, 0.45)'));
  // 下沿高光（让刻痕底部反光）
  group.add(mkText(1.1 * (radius / PIECE_RADIUS), 'rgba(255, 248, 226, 0.6)'));
  // 主字
  group.add(mkText(0, ink));
  return group;
}

/**
 * 把一枚独立棋子渲染进给定容器（自带 Konva.Stage）。
 * 候选棋子库使用，size 为正方形画布边长（px）。
 * 返回 stage，调用方负责在卸载时 destroy。
 */
export function renderStandalonePiece(
  container: HTMLDivElement,
  piece: Piece,
  size: number,
  selected = false,
): Konva.Stage {
  const stage = new Konva.Stage({ container, width: size, height: size });
  const layer = new Konva.Layer({ listening: false });
  // 留出阴影/选中环的余量，避免被画布裁切
  const radius = (size / 2) * 0.78;
  const group = buildPieceGroup(piece, radius, selected);
  group.position({ x: size / 2, y: size / 2 });
  layer.add(group);
  stage.add(layer);
  layer.draw();
  return stage;
}

export function addPiece(
  layer: Konva.Layer,
  piece: Piece,
  file: number,
  rank: number,
  selected = false,
): Konva.Group {
  const x = fileX(file);
  const y = rankY(rank);
  const radius = PIECE_RADIUS;

  const group = buildPieceGroup(piece, radius, selected);
  group.position({ x, y });
  layer.add(group);
  return group;
}

function drawPalace(layer: Konva.Layer, topRank: number): void {
  layer.add(new Konva.Line({
    points: [fileX(3), rankY(topRank), fileX(5), rankY(topRank + 2)],
    stroke: INK,
    strokeWidth: 1.15,
  }));
  layer.add(new Konva.Line({
    points: [fileX(5), rankY(topRank), fileX(3), rankY(topRank + 2)],
    stroke: INK,
    strokeWidth: 1.15,
  }));
}

function drawMarkers(layer: Konva.Layer): void {
  const points: Array<[number, number]> = [
    [1, 2],
    [7, 2],
    [0, 3],
    [2, 3],
    [4, 3],
    [6, 3],
    [8, 3],
    [1, 7],
    [7, 7],
    [0, 6],
    [2, 6],
    [4, 6],
    [6, 6],
    [8, 6],
  ];

  for (const [file, rank] of points) {
    addMarker(layer, file, rank);
  }
}

function addMarker(layer: Konva.Layer, file: number, rank: number): void {
  const x = fileX(file);
  const y = rankY(rank);
  const len = 7;
  const gap = 8;
  const sides = [
    { sx: -1, sy: -1 },
    { sx: 1, sy: -1 },
    { sx: -1, sy: 1 },
    { sx: 1, sy: 1 },
  ];

  for (const { sx, sy } of sides) {
    if ((file === 0 && sx < 0) || (file === FILES - 1 && sx > 0)) continue;
    const cx = x + sx * gap;
    const cy = y + sy * gap;
    layer.add(new Konva.Line({
      points: [cx, cy, cx + sx * len, cy],
      stroke: INK_SOFT,
      strokeWidth: 1,
    }));
    layer.add(new Konva.Line({
      points: [cx, cy, cx, cy + sy * len],
      stroke: INK_SOFT,
      strokeWidth: 1,
    }));
  }
}
