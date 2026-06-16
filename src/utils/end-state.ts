import type { Color, EndReason } from '@/types';

interface EndResult {
  winner?: Color;
  reason?: EndReason;
}

const endReasonLabels: Record<Exclude<EndReason, 'checkmate'>, string> = {
  stalemate: '困毙',
  repetition: '重复局面',
  'fifty-move': '自然限着',
  resign: '认输',
  timeout: '超时',
};

export function sideLabel(side: Color) {
  return side === 'red' ? '红方' : '黑方';
}

export function winnerLabel(winner?: Color) {
  return winner ? `${sideLabel(winner)}胜` : '和棋';
}

export function endReasonLabel(result: EndResult | null) {
  if (!result?.reason) return '终局';
  if (result.reason === 'checkmate') {
    if (result.winner === 'black') return '帅死';
    if (result.winner === 'red') return '将死';
    return '将死';
  }
  return endReasonLabels[result.reason];
}

export function endSummary(result: EndResult | null) {
  return `${endReasonLabel(result)} · ${winnerLabel(result?.winner)}`;
}
