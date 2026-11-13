export type OHLC = [number, number, number, number];
export interface Layout {
  L: number;
  G: number;
  R: number;
}

/** 여러 캔들 묶음을 모두 담는 y 범위. 보기마다 축이 달라져 단서가 되는 것을 막기 위해 모든 보기를 함께 넣는다. */
export function yRange(groups: (OHLC[] | null | undefined)[], pad = 0.06): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const g of groups) {
    if (!g) continue;
    for (const c of g) {
      if (c[2] < lo) lo = c[2];
      if (c[1] > hi) hi = c[1];
    }
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0.9, 1.1];
  const p = Math.max((hi - lo) * pad, 1e-6);
  return [lo - p, hi + p];
}

export function xScale(n: number, x0: number, x1: number) {
  const step = (x1 - x0) / Math.max(n, 1);
  return {
    step,
    center: (i: number) => x0 + step * (i + 0.5),
    body: Math.max(step * 0.7, 1),
  };
}

/** 값 → 픽셀 y (top이 큰 값). */
export function yScale(lo: number, hi: number, top: number, bottom: number) {
  const span = hi - lo || 1;
  return (v: number) => bottom - ((v - lo) / span) * (bottom - top);
}

const STEPS = [0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000];

/** 기준(1.0 = 0%) 대비 보기 좋은 퍼센트 눈금. 비율 값으로 돌려준다. */
export function pctTicks(lo: number, hi: number, target = 5): number[] {
  const span = (hi - lo) * 100;
  const step = STEPS.find((s) => span / s <= target) ?? STEPS[STEPS.length - 1];
  const out: number[] = [];
  const first = Math.ceil(((lo - 1) * 100) / step - 1e-9) * step;
  for (let p = first; p <= (hi - 1) * 100 + 1e-9; p += step) out.push(1 + p / 100);
  return out;
}

export function pctLabel(ratio: number): string {
  const r = Math.round((ratio - 1) * 1000) / 10; // 소수 한 자리까지 (부동소수 오차 제거)
  const s = Number.isInteger(r) ? r.toFixed(0) : r.toFixed(1);
  return r > 0 ? `+${s}%` : `${s}%`;
}

/** 썸네일에서 보여 줄 구간: 빈칸과 양옆 몇 봉. */
export function thumbWindow(layout: Layout, side = 6): [number, number] {
  const n = layout.L + layout.G + layout.R;
  return [Math.max(layout.L - side, 0), Math.min(layout.L + layout.G + side, n)];
}
