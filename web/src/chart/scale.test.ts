import { describe, expect, it } from "vitest";
import { pctLabel, pctTicks, thumbWindow, xScale, yRange, yScale, type OHLC } from "./scale";

const c = (o: number, h: number, l: number, cl: number): OHLC => [o, h, l, cl];

describe("yRange", () => {
  it("covers every group with padding", () => {
    const [lo, hi] = yRange([[c(1, 1.2, 0.9, 1.1)], [c(1, 1.5, 0.95, 1.4)], null], 0.1);
    expect(lo).toBeCloseTo(0.9 - 0.06);
    expect(hi).toBeCloseTo(1.5 + 0.06);
  });
  it("falls back when empty", () => {
    expect(yRange([])).toEqual([0.9, 1.1]);
  });
});

describe("scales", () => {
  it("maps x centres evenly", () => {
    const s = xScale(10, 0, 100);
    expect(s.center(0)).toBe(5);
    expect(s.center(9)).toBe(95);
    expect(s.body).toBeCloseTo(7);
  });
  it("maps high values to the top", () => {
    const y = yScale(0.8, 1.2, 10, 110);
    expect(y(1.2)).toBe(10);
    expect(y(0.8)).toBe(110);
    expect(y(1.0)).toBe(60);
  });
});

describe("pctTicks", () => {
  it("includes 0% and uses a nice step", () => {
    const t = pctTicks(0.88, 1.31);
    expect(t.some((v) => Math.abs(v - 1) < 1e-9)).toBe(true);
    expect(t.length).toBeGreaterThanOrEqual(3);
    expect(t.length).toBeLessThanOrEqual(6);
    const steps = t.slice(1).map((v, i) => Math.round((v - t[i]) * 1000));
    expect(new Set(steps).size).toBe(1);
  });
  it("labels percentages", () => {
    expect(pctLabel(1)).toBe("0%");
    expect(pctLabel(1.1)).toBe("+10%");
    expect(pctLabel(0.975)).toBe("-2.5%");
  });
});

describe("thumbWindow", () => {
  it("clamps to the chart", () => {
    expect(thumbWindow({ L: 30, G: 18, R: 30 })).toEqual([24, 54]);
    expect(thumbWindow({ L: 3, G: 10, R: 2 })).toEqual([0, 15]);
  });
});
