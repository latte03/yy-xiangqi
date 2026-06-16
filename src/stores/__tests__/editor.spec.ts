import { describe, it, expect } from 'vitest';
import { validate } from '../editor';
import { emptyBoard } from '@/types';
import type { Board } from '@/types';

function place(board: Board, file: number, rank: number, type: any, color: 'red' | 'black') {
  board[rank][file] = { type, color };
}

describe('摆棋校验', () => {
  it('空棋盘: 缺少双方将帅 → 硬错误', () => {
    const b = emptyBoard();
    expect(validate(b).hardErrors).toContain('缺少红帅');
    expect(validate(b).hardErrors).toContain('缺少黑将');
  });

  it('只有红帅 → 仍缺黑将', () => {
    const b = emptyBoard();
    place(b, 4, 9, 'K', 'red');
    const r = validate(b);
    expect(r.hardErrors).not.toContain('缺少红帅');
    expect(r.hardErrors).toContain('缺少黑将');
  });

  it('双方将帅照面 → 硬错误', () => {
    const b = emptyBoard();
    place(b, 4, 9, 'K', 'red');
    place(b, 4, 0, 'K', 'black');
    expect(validate(b).hardErrors).toContain('将帅照面');
  });

  it('双方将帅不同列 → 无硬错误', () => {
    const b = emptyBoard();
    place(b, 4, 9, 'K', 'red');
    place(b, 0, 0, 'K', 'black');
    expect(validate(b).hardErrors).not.toContain('将帅照面');
  });

  it('将帅同列但中间有子 → 不算照面', () => {
    const b = emptyBoard();
    place(b, 4, 9, 'K', 'red');
    place(b, 4, 5, 'P', 'red');
    place(b, 4, 0, 'K', 'black');
    expect(validate(b).hardErrors).not.toContain('将帅照面');
  });

  it('将帅数量上限 (各 1) → 超出报错', () => {
    const b = emptyBoard();
    place(b, 0, 9, 'K', 'red');
    place(b, 8, 9, 'K', 'red');
    place(b, 4, 0, 'K', 'black');
    expect(validate(b).hardErrors.some((e) => e.includes('数量过多'))).toBe(true);
  });

  it('兵数量上限 (各 5) → 超出报错', () => {
    const b = emptyBoard();
    place(b, 4, 9, 'K', 'red');
    place(b, 4, 0, 'K', 'black');
    // 红方摆 6 个兵
    for (let i = 0; i < 6; i++) place(b, i, 5, 'P', 'red');
    expect(validate(b).hardErrors.some((e) => e.includes('兵'))).toBe(true);
  });

  it('缺士象 → 软警告', () => {
    const b = emptyBoard();
    place(b, 4, 9, 'K', 'red');
    place(b, 4, 0, 'K', 'black');
    place(b, 0, 9, 'R', 'red');
    place(b, 0, 0, 'R', 'black');
    const r = validate(b);
    expect(r.warnings.some((w) => w.includes('缺士象'))).toBe(true);
  });

  it('棋盘上子太少 → 软警告', () => {
    const b = emptyBoard();
    place(b, 4, 9, 'K', 'red');
    place(b, 4, 0, 'K', 'black');
    const r = validate(b);
    expect(r.warnings.some((w) => w.includes('只有'))).toBe(true);
  });

  it('完整的合法残局 → 无硬错误 (有缺士象警告属正常)', () => {
    // 红方单车对黑方士象全 (经典残局), 红方缺士象是预期软警告
    const b = emptyBoard();
    place(b, 4, 9, 'K', 'red');
    place(b, 0, 0, 'K', 'black'); // 不同列避免照面
    place(b, 0, 9, 'R', 'red');
    place(b, 4, 1, 'A', 'black');
    place(b, 3, 1, 'A', 'black');
    place(b, 2, 0, 'E', 'black');
    place(b, 6, 0, 'E', 'black');
    const r = validate(b);
    expect(r.hardErrors).toEqual([]);
    // 红方没士象 → 软警告是预期
    expect(r.warnings).toContain('红方缺士象');
  });

  it('完整双方残局 → 双方都有士象, 无警告', () => {
    const b = emptyBoard();
    place(b, 4, 9, 'K', 'red');
    place(b, 0, 0, 'K', 'black');
    place(b, 0, 9, 'R', 'red');
    place(b, 4, 1, 'A', 'black');
    place(b, 3, 1, 'A', 'black');
    place(b, 2, 0, 'E', 'black');
    place(b, 6, 0, 'E', 'black');
    // 红方补士象
    place(b, 4, 8, 'A', 'red');
    place(b, 3, 8, 'A', 'red');
    place(b, 2, 9, 'E', 'red');
    place(b, 6, 9, 'E', 'red');
    const r = validate(b);
    expect(r.hardErrors).toEqual([]);
    // 双方都有士象, 不会触发"缺士象"警告
    expect(r.warnings.filter((w) => w.includes('缺士象'))).toEqual([]);
  });

  it('极端残局 (红光帅 vs 黑将) → 软警告 (无照面时)', () => {
    // 红帅 e1, 黑将 a10, 不照面 → 无硬错误
    const b = emptyBoard();
    place(b, 4, 9, 'K', 'red');
    place(b, 0, 0, 'K', 'black');
    const r = validate(b);
    expect(r.hardErrors).toEqual([]);
    expect(r.warnings.length).toBeGreaterThan(0);
  });
});