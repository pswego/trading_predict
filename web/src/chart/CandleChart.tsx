import { useEffect, useId, useMemo, useRef, useState } from "react";
import { pctLabel, pctTicks, thumbWindow, xScale, yRange, yScale, type Layout, type OHLC } from "./scale";

export type FillStyle = "preview" | "real" | "wrong" | "plain";

interface Props {
  candles: OHLC[]; // 맥락만 (L + R개)
  layout: Layout;
  gapFill?: OHLC[] | null; // 빈칸에 끼워 보여 줄 보기
  fillStyle?: FillStyle;
  ghost?: OHLC[] | null; // 반투명으로 겹쳐 보여 줄 보기 (내가 고른 오답)
  rangeWith?: (OHLC[] | null | undefined)[]; // y 범위에 함께 넣을 보기들
  volume?: number[] | null;
  fillVolume?: number[] | null;
  ma?: Record<string, (number | null)[]> | null;
  mode?: "main" | "thumb";
  animate?: boolean;
  aspect?: number; // 높이 / 폭
  label?: string;
}

const TINT: Record<FillStyle, string> = {
  preview: "var(--accent)",
  real: "var(--good)",
  wrong: "var(--bad)",
  plain: "transparent",
};
const MA_COLOR: Record<string, string> = { "5": "#e0a100", "20": "#b36bff" };

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.clientWidth);
    const ro = new ResizeObserver((e) => setW(Math.round(e[0].contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

function Candle({ c, x, w, y, opacity = 1 }: { c: OHLC; x: number; w: number; y: (v: number) => number; opacity?: number }) {
  const up = c[3] >= c[0];
  const color = up ? "var(--up)" : "var(--down)";
  const top = y(Math.max(c[0], c[3]));
  const h = Math.max(y(Math.min(c[0], c[3])) - top, 1);
  return (
    <g opacity={opacity}>
      <line x1={x} x2={x} y1={y(c[1])} y2={y(c[2])} stroke={color} strokeWidth={Math.max(Math.min(w / 5, 1.5), 0.75)} />
      <rect x={x - w / 2} y={top} width={w} height={h} fill={color} rx={w > 6 ? 1 : 0} />
    </g>
  );
}

export default function CandleChart(p: Props) {
  const mode = p.mode ?? "main";
  const thumb = mode === "thumb";
  const [ref, width] = useWidth<HTMLDivElement>();
  const uid = useId().replace(/:/g, "");
  const { L, G, R } = p.layout;
  const N = L + G + R;
  const [i0, i1] = thumb ? thumbWindow(p.layout) : [0, N];
  const showVol = !thumb && !!p.volume;
  const aspect = p.aspect ?? (thumb ? 0.62 : width < 520 ? 0.62 : 0.42);
  const height = Math.round(width * aspect);
  const padR = thumb ? 2 : 44;
  const priceBottom = showVol ? height * 0.8 : height - 4;
  const volTop = height * 0.84;

  const visible = useMemo(() => {
    const left = p.candles.slice(Math.max(i0, 0), L);
    const right = p.candles.slice(L, L + Math.max(i1 - L - G, 0));
    return { left, right };
  }, [p.candles, i0, i1, L, G]);

  const [lo, hi] = useMemo(
    () => yRange([visible.left, visible.right, p.gapFill, p.ghost, ...(p.rangeWith ?? [])]),
    [visible, p.gapFill, p.ghost, p.rangeWith],
  );

  if (width === 0) return <div ref={ref} style={{ aspectRatio: `1 / ${aspect}` }} className="w-full" />;

  const xs = xScale(i1 - i0, 2, width - padR);
  const cx = (i: number) => xs.center(i - i0);
  const y = yScale(lo, hi, 6, priceBottom);
  const gx0 = cx(L) - xs.step / 2;
  const gx1 = cx(L + G - 1) + xs.step / 2;
  const fill = p.gapFill;
  const style = p.fillStyle ?? "plain";

  const vols = showVol ? [...(p.volume ?? []), ...(fill && p.fillVolume ? p.fillVolume : [])] : [];
  const vmax = vols.length ? Math.max(...vols) || 1 : 1;
  const vy = (v: number) => height - 2 - (v / vmax) * (height - 2 - volTop);

  const maPaths: { key: string; d: string }[] = [];
  if (!thumb && p.ma) {
    for (const [key, arr] of Object.entries(p.ma)) {
      for (const [from, to, offset] of [
        [0, L, 0],
        [L, L + R, G],
      ] as const) {
        let d = "";
        for (let i = from; i < to; i++) {
          const v = arr[i];
          if (v == null) continue;
          d += `${d ? "L" : "M"}${cx(i + offset).toFixed(1)},${y(v).toFixed(1)}`;
        }
        if (d) maPaths.push({ key: `${key}-${from}`, d });
      }
    }
  }

  return (
    <div ref={ref} className="w-full select-none" aria-label={p.label} role="img">
      <svg width={width} height={height} className="block">
        <defs>
          <pattern id={`hatch-${uid}`} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="8" height="8" fill="var(--panel2)" />
            <line x1="0" y1="0" x2="0" y2="8" stroke="var(--line)" strokeWidth="3" />
          </pattern>
        </defs>

        {!thumb &&
          pctTicks(lo, hi).map((t) => (
            <g key={t}>
              <line
                x1={0}
                x2={width - padR}
                y1={y(t)}
                y2={y(t)}
                stroke="var(--line)"
                strokeWidth={1}
                strokeDasharray={Math.abs(t - 1) < 1e-9 ? "4 4" : undefined}
                opacity={Math.abs(t - 1) < 1e-9 ? 1 : 0.45}
              />
              <text x={width - padR + 5} y={y(t) + 3.5} fontSize={10.5} fill="var(--muted)" className="tnum">
                {pctLabel(t)}
              </text>
            </g>
          ))}

        {/* 빈칸 */}
        {fill ? (
          <rect x={gx0} y={0} width={gx1 - gx0} height={height} fill={TINT[style]} opacity={style === "plain" ? 0 : 0.1} />
        ) : (
          <g>
            <rect x={gx0} y={0} width={gx1 - gx0} height={height} fill={`url(#hatch-${uid})`} opacity={0.75} />
            <text
              x={(gx0 + gx1) / 2}
              y={priceBottom / 2 + (thumb ? 6 : 12)}
              textAnchor="middle"
              fontSize={thumb ? 18 : 34}
              fontWeight={800}
              fill="var(--muted)"
            >
              ?
            </text>
          </g>
        )}
        {!thumb && (
          <>
            <line x1={gx0} x2={gx0} y1={0} y2={height} stroke="var(--muted)" strokeWidth={1} strokeDasharray="3 3" opacity={0.6} />
            <line x1={gx1} x2={gx1} y1={0} y2={height} stroke="var(--muted)" strokeWidth={1} strokeDasharray="3 3" opacity={0.6} />
          </>
        )}

        {/* 맥락 */}
        {visible.left.map((c, k) => {
          const i = Math.max(i0, 0) + k;
          return <Candle key={`l${i}`} c={c} x={cx(i)} w={xs.body} y={y} opacity={thumb ? 0.45 : 1} />;
        })}
        {visible.right.map((c, k) => (
          <Candle key={`r${k}`} c={c} x={cx(L + G + k)} w={xs.body} y={y} opacity={thumb ? 0.45 : 1} />
        ))}

        {maPaths.map((m) => (
          <path key={m.key} d={m.d} fill="none" stroke={MA_COLOR[m.key.split("-")[0]] ?? "var(--muted)"} strokeWidth={1.25} opacity={0.85} />
        ))}

        {/* 겹쳐 보기 */}
        {p.ghost?.map((c, k) => <Candle key={`g${k}`} c={c} x={cx(L + k)} w={xs.body} y={y} opacity={0.28} />)}

        {/* 빈칸에 끼운 보기 */}
        {fill?.map((c, k) => (
          <g
            key={`f${k}`}
            style={
              p.animate
                ? { animation: `candle-in 0.22s ease-out ${((k / Math.max(G, 1)) * 0.75).toFixed(3)}s both` }
                : undefined
            }
          >
            <Candle c={c} x={cx(L + k)} w={xs.body} y={y} />
          </g>
        ))}

        {/* 거래량 */}
        {showVol && (
          <g opacity={0.55}>
            {p.volume!.map((v, k) => {
              const i = k < L ? k : k + G;
              const c = p.candles[k];
              return (
                <rect key={`v${k}`} x={cx(i) - xs.body / 2} y={vy(v)} width={xs.body} height={Math.max(height - 2 - vy(v), 0.5)} fill={c[3] >= c[0] ? "var(--up)" : "var(--down)"} />
              );
            })}
            {fill &&
              p.fillVolume?.map((v, k) => (
                <rect key={`fv${k}`} x={cx(L + k) - xs.body / 2} y={vy(v)} width={xs.body} height={Math.max(height - 2 - vy(v), 0.5)} fill={fill[k][3] >= fill[k][0] ? "var(--up)" : "var(--down)"} />
              ))}
          </g>
        )}
      </svg>
    </div>
  );
}
