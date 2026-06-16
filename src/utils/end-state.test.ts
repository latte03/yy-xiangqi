import { describe, expect, it } from 'vitest';
import { endReasonLabel, endSummary } from './end-state';

describe('end-state labels', () => {
  it('黑方将死红帅时显示帅死', () => {
    expect(endReasonLabel({ reason: 'checkmate', winner: 'black' })).toBe('帅死');
    expect(endSummary({ reason: 'checkmate', winner: 'black' })).toBe('帅死 · 黑方胜');
  });

  it('红方将死黑将时显示将死', () => {
    expect(endReasonLabel({ reason: 'checkmate', winner: 'red' })).toBe('将死');
    expect(endSummary({ reason: 'checkmate', winner: 'red' })).toBe('将死 · 红方胜');
  });

  it('非将死终局保留原始原因', () => {
    expect(endSummary({ reason: 'resign', winner: 'black' })).toBe('认输 · 黑方胜');
  });
});
