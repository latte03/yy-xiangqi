import Konva from 'konva';
import type { Color, Piece, PieceType, Position } from '@/types';

export const CELL_SIZE = 58;
export const BOARD_PADDING = 36;
export const FILES = 9;
export const RANKS = 10;
export const WIDTH = CELL_SIZE * (FILES - 1) + BOARD_PADDING * 2;
export const HEIGHT = CELL_SIZE * (RANKS - 1) + BOARD_PADDING * 2;

const INK = '#4c2f18';
const INK_SOFT = 'rgba(76, 47, 24, 0.72)';

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
  return color === 'red' ? '#a93628' : '#1f1b17';
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

  layer.add(new Konva.Rect({
    x: 0,
    y: 0,
    width: WIDTH,
    height: HEIGHT,
    cornerRadius: 18,
    fillLinearGradientStartPoint: { x: 0, y: 0 },
    fillLinearGradientEndPoint: { x: WIDTH, y: HEIGHT },
    fillLinearGradientColorStops: [0, '#d7a65d', 0.42, '#f0cf8b', 1, '#b9793c'],
    shadowColor: '#000',
    shadowBlur: 28,
    shadowOpacity: 0.28,
    shadowOffsetY: 12,
  }));

  layer.add(new Konva.Rect({
    x: 14,
    y: 14,
    width: WIDTH - 28,
    height: HEIGHT - 28,
    cornerRadius: 12,
    stroke: 'rgba(76, 47, 24, 0.78)',
    strokeWidth: 3,
  }));

  for (let i = 0; i < 24; i++) {
    const y = 26 + ((i * 41) % (HEIGHT - 52));
    layer.add(new Konva.Line({
      points: [26, y, WIDTH - 26, y + ((i % 5) - 2) * 2],
      stroke: 'rgba(84, 47, 19, 0.08)',
      strokeWidth: i % 4 === 0 ? 2 : 1,
      tension: 0.45,
    }));
  }

  layer.add(new Konva.Rect({
    x: fileX(0),
    y: rankY(4),
    width: CELL_SIZE * 8,
    height: CELL_SIZE,
    fill: 'rgba(255, 238, 183, 0.22)',
  }));

  for (let rank = 0; rank < RANKS; rank++) {
    layer.add(new Konva.Line({
      points: [fileX(0), rankY(rank), fileX(FILES - 1), rankY(rank)],
      stroke: INK,
      strokeWidth: rank === 0 || rank === RANKS - 1 ? 1.8 : 1.1,
    }));
  }

  for (let file = 0; file < FILES; file++) {
    const x = fileX(file);
    if (file === 0 || file === FILES - 1) {
      layer.add(new Konva.Line({
        points: [x, rankY(0), x, rankY(RANKS - 1)],
        stroke: INK,
        strokeWidth: 1.8,
      }));
      continue;
    }

    layer.add(new Konva.Line({
      points: [x, rankY(0), x, rankY(4)],
      stroke: INK,
      strokeWidth: 1.1,
    }));
    layer.add(new Konva.Line({
      points: [x, rankY(5), x, rankY(RANKS - 1)],
      stroke: INK,
      strokeWidth: 1.1,
    }));
  }

  drawPalace(layer, 0);
  drawPalace(layer, 7);
  drawMarkers(layer);

  layer.add(new Konva.Text({
    x: fileX(1),
    y: rankY(4) + 14,
    width: CELL_SIZE * 3,
    align: 'center',
    text: '楚  河',
    fontSize: 24,
    fill: 'rgba(76, 47, 24, 0.58)',
    fontFamily: 'Georgia, serif',
    fontStyle: 'bold',
  }));
  layer.add(new Konva.Text({
    x: fileX(4),
    y: rankY(4) + 14,
    width: CELL_SIZE * 3,
    align: 'center',
    text: '汉  界',
    fontSize: 24,
    fill: 'rgba(76, 47, 24, 0.58)',
    fontFamily: 'Georgia, serif',
    fontStyle: 'bold',
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

export function addPiece(
  layer: Konva.Layer,
  piece: Piece,
  file: number,
  rank: number,
  selected = false,
): Konva.Group {
  const x = fileX(file);
  const y = rankY(rank);
  const radius = CELL_SIZE * 0.39;

  const group = new Konva.Group({ x, y });
  group.add(new Konva.Circle({
    radius: radius + 3,
    fill: selected ? 'rgba(244, 194, 93, 0.44)' : 'rgba(58, 31, 13, 0.2)',
    shadowColor: '#2a1609',
    shadowBlur: selected ? 14 : 8,
    shadowOpacity: selected ? 0.42 : 0.26,
    shadowOffsetY: 4,
  }));
  group.add(new Konva.Circle({
    radius,
    fillRadialGradientStartPoint: { x: -7, y: -9 },
    fillRadialGradientStartRadius: 2,
    fillRadialGradientEndPoint: { x: 0, y: 0 },
    fillRadialGradientEndRadius: radius,
    fillRadialGradientColorStops: [0, '#fff7df', 0.72, '#efcf8f', 1, '#bd813f'],
    stroke: selected ? '#f0b844' : '#5a3519',
    strokeWidth: selected ? 3 : 2,
  }));
  group.add(new Konva.Circle({
    radius: radius - 6,
    stroke: 'rgba(90, 53, 25, 0.45)',
    strokeWidth: 1,
  }));
  group.add(new Konva.Text({
    x: -radius,
    y: -radius,
    width: radius * 2,
    height: radius * 2,
    align: 'center',
    verticalAlign: 'middle',
    text: pieceLabel(piece),
    fontSize: 24,
    fontStyle: 'bold',
    fill: pieceInk(piece.color),
    fontFamily: 'Songti SC, STSong, SimSun, serif',
  }));
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
