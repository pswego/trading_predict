import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import CandleChart from "../chart/CandleChart";
import type { OHLC } from "../chart/scale";
import { Card, Shell, fmt } from "../components/ui";

// 첫 화면용 예시 차트 (실제 종목 아님)
const DEMO: OHLC[] = (() => {
  const out: OHLC[] = [];
  let c = 1;
  const moves = [0.012, -0.008, 0.02, 0.006, -0.015, 0.018, 0.01, -0.004, 0.022, -0.012, 0.008, 0.015, -0.02, -0.01, 0.006, -0.018, 0.012, 0.02, -0.006, 0.014, 0.01, -0.012];
  for (const m of moves) {
    const o = c;
    c = c * (1 + m);
    out.push([o, Math.max(o, c) * 1.006, Math.min(o, c) * 0.994, c]);
  }
  return out;
})();

const MODES = [
  { to: "/setup/quick", title: "빠른 10문제", desc: "조건을 고르고 10문제로 실력 확인", icon: "⚡" },
  { to: "/daily", title: "데일리 챌린지", desc: "모두가 같은 5문제 · 하루 한 번", icon: "📅" },
  { to: "/setup/survival", title: "서바이벌", desc: "목숨 3개 · 맞힐수록 어려워져요", icon: "♥" },
  { to: "/setup/endless", title: "무한 연습", desc: "시간 제한 없이 천천히", icon: "∞" },
];

export default function Home() {
  const [count, setCount] = useState<number | null>(null);
  useEffect(() => {
    api.health().then((h) => setCount(h.questions)).catch(() => setCount(null));
  }, []);

  return (
    <Shell>
      <header className="mb-5 mt-4 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">빈칸 차트</h1>
          <p className="mt-1 text-sm text-muted">실제 주식 차트의 가려진 구간, 진짜 모양을 맞혀 보세요.</p>
        </div>
        <Link to="/stats" className="rounded-xl border border-line bg-panel px-3 py-2 text-sm font-semibold">
          내 기록
        </Link>
      </header>

      <Card className="mb-5 overflow-hidden !p-2">
        <CandleChart candles={DEMO} layout={{ L: 11, G: 7, R: 11 }} aspect={0.34} label="가운데가 가려진 예시 차트" />
      </Card>

      <nav className="grid gap-3 sm:grid-cols-2">
        {MODES.map((m) => (
          <Link key={m.to} to={m.to} className="group rounded-2xl border border-line bg-panel p-4 transition hover:border-accent">
            <div className="flex items-center gap-3">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-panel2 text-xl">{m.icon}</span>
              <div>
                <div className="font-bold group-hover:text-accent">{m.title}</div>
                <div className="text-sm text-muted">{m.desc}</div>
              </div>
            </div>
          </Link>
        ))}
      </nav>

      <p className="mt-6 text-center text-xs text-muted">
        {count != null && count > 0 && <>실제 차트 문제 {fmt(count)}개 · </>}
        과거 데이터 기반 오락용 게임이며 투자 권유가 아닙니다.
        <br />
        가격 데이터 출처: 네이버 금융
      </p>
    </Shell>
  );
}
