import { useEffect, useState } from "react";
import { api, type Stat, type Stats as StatsData } from "../api/client";
import { Card, Chip, ErrorNote, LABEL, Loading, Shell, TopBar, fmt } from "../components/ui";
import { useSettings } from "../store/settings";

function Bars({ title, rows, labels, order }: { title: string; rows: Stat[]; labels: Record<string, string>; order: string[] }) {
  const sorted = order.map((k) => rows.find((r) => r.key === k)).filter((r): r is Stat => !!r);
  if (!sorted.length) return null;
  return (
    <Card>
      <h2 className="mb-3 text-sm font-bold">{title}</h2>
      <ul className="grid gap-2.5">
        {sorted.map((r) => {
          const rate = r.plays ? r.correct / r.plays : 0;
          return (
            <li key={r.key} className="text-sm">
              <div className="mb-1 flex justify-between">
                <span>{labels[r.key] ?? r.key}</span>
                <span className="text-muted tnum">
                  {Math.round(rate * 100)}% · {r.correct}/{r.plays}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-panel2">
                <div className="h-full rounded-full bg-accent" style={{ width: `${rate * 100}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

export default function Stats() {
  const [s, setS] = useState<StatsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const settings = useSettings();
  const load = () => {
    setError(null);
    api.stats().then(setS).catch((e) => setError(e.message));
  };
  useEffect(load, []);

  return (
    <Shell>
      <TopBar title="내 기록" />
      <div className="grid gap-4">
        {error ? (
          <ErrorNote message={error} onRetry={load} />
        ) : !s ? (
          <Loading />
        ) : s.plays === 0 ? (
          <Card className="text-center text-sm text-muted">아직 푼 문제가 없어요. 한 판 하고 오면 여기에 기록이 쌓여요.</Card>
        ) : (
          <>
            <Card>
              <dl className="grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
                {[
                  ["실력 점수", fmt(s.elo)],
                  ["푼 문제", fmt(s.plays)],
                  ["정답률", `${Math.round((s.correct / s.plays) * 100)}%`],
                  ["최고 연속 정답", fmt(s.best_streak)],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-panel2 py-3">
                    <dt className="text-xs text-muted">{k}</dt>
                    <dd className="text-xl font-extrabold tnum">{v}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 text-xs text-muted">실력 점수는 1,000에서 시작해요. 어려운 문제를 맞힐수록 많이 오르고, 쉬운 문제를 틀릴수록 많이 내려요.</p>
            </Card>
            <Bars title="난이도별 정답률" rows={s.by_difficulty} labels={LABEL.difficulty} order={["easy", "normal", "hard"]} />
            <Bars title="규모별 정답률" rows={s.by_cap_tier} labels={LABEL.cap} order={["large", "mid", "small", "micro"]} />
            <Bars title="시장별 정답률" rows={s.by_market} labels={LABEL.market} order={["KOSPI", "KOSDAQ"]} />
            <Bars title="차트 단위별 정답률" rows={s.by_interval} labels={LABEL.interval} order={["day", "week"]} />
          </>
        )}

        <Card className="grid gap-4">
          <h2 className="text-sm font-bold">설정</h2>
          <div>
            <div className="mb-2 text-xs text-muted">화면 테마</div>
            <div className="flex flex-wrap gap-2">
              {(["system", "dark", "light"] as const).map((t) => (
                <Chip key={t} on={settings.theme === t} onClick={() => settings.set({ theme: t })}>
                  {{ system: "기기 설정", dark: "어둡게", light: "밝게" }[t]}
                </Chip>
              ))}
            </div>
          </div>
          <div>
            <div className="mb-2 text-xs text-muted">캔들 색</div>
            <div className="flex flex-wrap gap-2">
              <Chip on={settings.colors === "kr"} onClick={() => settings.set({ colors: "kr" })}>
                상승 빨강 · 하락 파랑
              </Chip>
              <Chip on={settings.colors === "us"} onClick={() => settings.set({ colors: "us" })}>
                상승 초록 · 하락 빨강
              </Chip>
            </div>
          </div>
          <div>
            <div className="mb-2 text-xs text-muted">효과음</div>
            <div className="flex gap-2">
              <Chip on={settings.sound} onClick={() => settings.set({ sound: true })}>
                켜기
              </Chip>
              <Chip on={!settings.sound} onClick={() => settings.set({ sound: false })}>
                끄기
              </Chip>
            </div>
          </div>
        </Card>
      </div>
    </Shell>
  );
}
