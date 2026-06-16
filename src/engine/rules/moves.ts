/**
 * 中国象棋走法规则
 * 纯函数: 输入 board + color, 输出所有合法走法 (pseudo-legal, 未做"送将"过滤)
 */

import type {
  Board,
  Color,
  Move,
  Piece,
  Position,
} from '@/types';
import { FILES, RANKS, opponent } from '@/types';

function pushIfValid(
  out: Move[],
  board: Board,
  from: Position,
  to: Position,
  piece: Piece,
): void {
  if (to.file < 0 || to.file >= FILES || to.rank < 0 || to.rank >= RANKS) return;
  const target = board[to.rank][to.file];
  if (target && target.color === piece.color) return;
  out.push({ from, to, piece, captured: target ?? undefined });
}

/** 在 [from, to] 路径上 (不含端点) 是否被阻挡 */
function isPathBlocked(board: Board, from: Position, to: Position): boolean {
  const df = Math.sign(to.file - from.file);
  const dr = Math.sign(to.rank - from.rank);
  let f = from.file + df;
  let r = from.rank + dr;
  while (f !== to.file || r !== to.rank) {
    if (board[r][f] !== null) return true;
    f += df;
    r += dr;
  }
  return false;
}

/** 九宫内? 红方九宫: file 3-5, rank 7-9; 黑方九宫: file 3-5, rank 0-2 */
function inPalace(file: number, rank: number, color: Color): boolean {
  if (file < 3 || file > 5) return false;
  return color === 'red' ? rank >= 7 && rank <= 9 : rank >= 0 && rank <= 2;
}

/**
 * 没过河?
 * - 红方初始在 rank 5-9 (下方), 未过河 = 仍在 rank 5-9
 * - 黑方初始在 rank 0-4 (上方), 未过河 = 仍在 rank 0-4
 * - 河在 rank 4 / rank 5 之间
 */
function notCrossedRiver(rank: number, color: Color): boolean {
  return color === 'red' ? rank >= 5 : rank <= 4;
}

function generateRookMoves(board: Board, from: Position, piece: Piece): Move[] {
  const moves: Move[] = [];
  const dirs = [
    [1, 0],
    [-1, 0],
    [0, 1],
    [0, -1],
  ];
  for (const [df, dr] of dirs) {
    let f = from.file + df;
    let r = from.rank + dr;
    while (f >= 0 && f < FILES && r >= 0 && r < RANKS) {
      const target = board[r][f];
      if (!target) {
        moves.push({ from, to: { file: f, rank: r }, piece });
      } else {
        if (target.color !== piece.color) {
          moves.push({ from, to: { file: f, rank: r }, piece, captured: target });
        }
        break;
      }
      f += df;
      r += dr;
    }
  }
  return moves;
}

function generateCannonMoves(board: Board, from: Position, piece: Piece): Move[] {
  const moves: Move[] = [];
  const dirs = [
    [1, 0],
    [-1, 0],
    [0, 1],
    [0, -1],
  ];
  for (const [df, dr] of dirs) {
    let f = from.file + df;
    let r = from.rank + dr;
    // 第一段: 任意走 (不吃子), 直到碰到第一个子 (炮架) 或出界
    while (f >= 0 && f < FILES && r >= 0 && r < RANKS && board[r][f] === null) {
      moves.push({ from, to: { file: f, rank: r }, piece });
      f += df;
      r += dr;
    }
    // 找到炮架了 (出界则此方向无吃子走法)
    if (f < 0 || f >= FILES || r < 0 || r >= RANKS) continue;
    // 跳过炮架一格
    f += df;
    r += dr;
    // 第二段: 寻找第一个敌方棋子作为吃子目标
    // 注意: 这里 f/r 已经在炮架"之后"一格, 第一个非空格就是吃子目标
    while (f >= 0 && f < FILES && r >= 0 && r < RANKS) {
      const target = board[r][f];
      if (target) {
        if (target.color !== piece.color) {
          moves.push({ from, to: { file: f, rank: r }, piece, captured: target });
        }
        break;
      }
      f += df;
      r += dr;
    }
  }
  return moves;
}

function generateKnightMoves(board: Board, from: Position, piece: Piece): Move[] {
  // 马走"日"字, 8 个方向, 但需检查蹩马腿
  const offsets: Array<[[number, number], [number, number]]> = [
    // [目标偏移, 马腿偏移]
    [
      [1, 2],
      [0, 1],
    ],
    [
      [-1, 2],
      [0, 1],
    ],
    [
      [1, -2],
      [0, -1],
    ],
    [
      [-1, -2],
      [0, -1],
    ],
    [
      [2, 1],
      [1, 0],
    ],
    [
      [2, -1],
      [1, 0],
    ],
    [
      [-2, 1],
      [-1, 0],
    ],
    [
      [-2, -1],
      [-1, 0],
    ],
  ];
  const moves: Move[] = [];
  for (const [[df, dr], [lf, lr]] of offsets) {
    const legFile = from.file + lf;
    const legRank = from.rank + lr;
    if (board[legRank]?.[legFile] !== null) continue; // 蹩马腿
    pushIfValid(moves, board, from, { file: from.file + df, rank: from.rank + dr }, piece);
  }
  return moves;
}

function generateElephantMoves(
  board: Board,
  from: Position,
  piece: Piece,
): Move[] {
  // 相走"田"字, 4 个方向, 需检查塞象眼, 且不能过河
  const offsets: Array<[[number, number], [number, number]]> = [
    [
      [2, 2],
      [1, 1],
    ],
    [
      [-2, 2],
      [-1, 1],
    ],
    [
      [2, -2],
      [1, -1],
    ],
    [
      [-2, -2],
      [-1, -1],
    ],
  ];
  const moves: Move[] = [];
  for (const [[df, dr], [ef, er]] of offsets) {
    const eyeFile = from.file + ef;
    const eyeRank = from.rank + er;
    if (board[eyeRank]?.[eyeFile] !== null) continue; // 塞象眼
    const toFile = from.file + df;
    const toRank = from.rank + dr;
    if (!notCrossedRiver(toRank, piece.color)) continue; // 不能过河: 必须在己方半区
    pushIfValid(moves, board, from, { file: toFile, rank: toRank }, piece);
  }
  return moves;
}

function generateAdvisorMoves(
  board: Board,
  from: Position,
  piece: Piece,
): Move[] {
  const moves: Move[] = [];
  const dirs = [
    [1, 1],
    [1, -1],
    [-1, 1],
    [-1, -1],
  ];
  for (const [df, dr] of dirs) {
    const f = from.file + df;
    const r = from.rank + dr;
    if (!inPalace(f, r, piece.color)) continue;
    pushIfValid(moves, board, from, { file: f, rank: r }, piece);
  }
  return moves;
}

function generateKingMoves(
  board: Board,
  from: Position,
  piece: Piece,
): Move[] {
  const moves: Move[] = [];
  const dirs = [
    [1, 0],
    [-1, 0],
    [0, 1],
    [0, -1],
  ];
  for (const [df, dr] of dirs) {
    const f = from.file + df;
    const r = from.rank + dr;
    if (!inPalace(f, r, piece.color)) continue;
    pushIfValid(moves, board, from, { file: f, rank: r }, piece);
  }
  // 特殊: 帅/将对脸 (老将见面) — 处理方式: 若目标位是对方将/帅, 且路径无阻挡, 允许走 (即"吃"对方将)
  // 我们在这里显式生成对脸走法, 由合法性检查判断是否能吃
  // 见 generateFlyingKingMoves
  const oppKing = piece.color === 'red' ? 'k' : 'K';
  for (const [df, dr] of dirs) {
    const f = from.file + df;
    const r = from.rank + dr;
    if (f < 0 || f >= FILES || r < 0 || r >= RANKS) continue;
    const target = board[r][f];
    if (target && target.type === 'K' && target.color === opponent(piece.color)) {
      // 对脸: 需路径无阻挡
      if (!isPathBlocked(board, from, { file: f, rank: r })) {
        moves.push({ from, to: { file: f, rank: r }, piece, captured: target });
      }
    }
    // 不响应 oppKing 自身字符查询 (这里只是类型提示, 实际通过 type === 'K' 判断)
    void oppKing;
  }
  return moves;
}

function generatePawnMoves(board: Board, from: Position, piece: Piece): Move[] {
  const moves: Move[] = [];
  // 前进方向: 红方往黑方底线走 (rank 减小), 黑方往红方底线走 (rank 增大)
  const forward = piece.color === 'red' ? -1 : 1;
  const fr = from.rank + forward;
  if (fr >= 0 && fr < RANKS) {
    pushIfValid(moves, board, from, { file: from.file, rank: fr }, piece);
  }
  // 过河后可横走 (红方过河 = 进入 rank 0-4; 黑方过河 = 进入 rank 5-9)
  const crossed = piece.color === 'red' ? from.rank < 5 : from.rank > 4;
  // 注: notCrossedRiver(rank, 'red') = rank >= 5, 反过来 crossed = !notCrossedRiver
  if (crossed) {
    for (const df of [1, -1]) {
      const ff = from.file + df;
      if (ff >= 0 && ff < FILES) {
        pushIfValid(moves, board, from, { file: ff, rank: from.rank }, piece);
      }
    }
  }
  return moves;
}

/** 生成某方所有走法 (pseudo-legal) */
export function generateMoves(board: Board, color: Color): Move[] {
  const moves: Move[] = [];
  for (let r = 0; r < RANKS; r++) {
    for (let f = 0; f < FILES; f++) {
      const sq = board[r][f];
      if (!sq || sq.color !== color) continue;
      const from: Position = { file: f, rank: r };
      switch (sq.type) {
        case 'R':
          moves.push(...generateRookMoves(board, from, sq));
          break;
        case 'C':
          moves.push(...generateCannonMoves(board, from, sq));
          break;
        case 'H':
          moves.push(...generateKnightMoves(board, from, sq));
          break;
        case 'E':
          moves.push(...generateElephantMoves(board, from, sq));
          break;
        case 'A':
          moves.push(...generateAdvisorMoves(board, from, sq));
          break;
        case 'K':
          moves.push(...generateKingMoves(board, from, sq));
          break;
        case 'P':
          moves.push(...generatePawnMoves(board, from, sq));
          break;
      }
    }
  }
  return moves;
}