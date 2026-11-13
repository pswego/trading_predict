import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Difficulty, type Filters, type GameType, type Meta, type PoolCount, type SessionRequest } from "../api/client";
import { Button, Card, Chip, ErrorNote, LABEL, Loading, Shell, TopBar, fmt } from "../components/ui";

type Mode = SessionRequest["mode"];
const KEY = "chartgap.setup";

function loadSaved(): Partial<SessionRequest> {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}");
  } catch {
    return {};
  }
}

function toggle(list: string[], v: string) {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
}

export default function Setup() {
  const { mode: raw } = useParams();
  const mode: Mode = raw === "survival" || raw === "endless" ? raw : "quick";
  const nav = useNavigate();
  const saved = useMemo(loadSaved, []);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gameType, setGameType] = useState<GameType>(saved.game_type ?? "choice4");
  const [difficulty, setDifficulty] = useState<Difficulty | "auto">(saved.difficulty ?? "normal");
  const [filters, setFilters] = useState<Filters>({ interval: "day", markets: [], cap_tiers: [], eras: [], ...saved.filters });
  const [pool, setPool] = useState<PoolCount | null>(null);
  const [starting, setStarting] = useState(false);

  const req: SessionRequest = useMemo(() => ({ mode, game_type: gameType, filters, difficulty }), [mode, gameType, filters, difficulty]);

  const loadMeta = () => {
    setError(null);
    api.meta().then(setMeta).catch((e) => setError(e.message));
  };
  useEffect(loadMeta, []);

  useEffect(() => {
    let live = true;
    const t = setTimeout(() => {
      api.poolCount(req).then((p) => live && setPool(p)).catch(() => live && setPool(null));
    }, 150);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [req]);

  const start = async () => {
    setStarting(true);
    try {
      try {
        localStorage.setItem(KEY, JSON.stringify({ game_type: gameType, difficulty, filters }));
      } catch {
        /* 저장 못 해도 진행 */
      }
      const s = await api.createSession(req);
      nav(`/play/${s.session_id}`);
    } catch (e) {
      setError((e as Error).message);
      setStarting(false);
    }
  };

  if (error && !meta) {
    return (
      <Shell>
        <TopBar title={LABEL.mode[mode]} />
        <ErrorNote message={error} onRetry={loadMeta} />
      </Shell>
    );
  }
  if (!meta) {
    return (
      <Shell>
        <TopBar title={LABEL.mode[mode]} />
        <Loading />
      </Shell>
    );
  }

  const dim = meta.by_interval[filters.interval];
  const group = (title: string, hint: string, key: "markets" | "cap_tiers" | "eras", options: Meta["by_interval"][string]["markets"]) => (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-sm font-bold">{title}</h2>
        <span className="text-xs text-muted">{filters[key].length ? hint : "전체"}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <Chip key={o.value} on={filters[key].includes(o.value)} onClick={() => setFilters({ ...filters, [key]: toggle(filters[key], o.value) })} sub={fmt(o.count)}>
            {o.label}
          </Chip>
        ))}
      </div>
    </div>
  );

  const diffs: (Difficulty | "auto")[] = ["easy", "normal", "hard", "auto"];
  const diffHint: Record<string, string> = {
    easy: "빈칸이 짧고 추세가 뚜렷해요. 거래량·이동평균선 표시",
    normal: "비슷한 종목의 실제 구간이 오답으로 나와요",
    hard: "빈칸이 길고 예상 밖 움직임이 많아요. 거래량 숨김",
    auto: "내 실력에 맞는 문제를 골라 줘요",
  };

  return (
    <Shell>
      <TopBar title={LABEL.mode[mode]} />
      <div className="grid gap-4">
        <Card>
          <h2 className="mb-2 text-sm font-bold">문제 방식</h2>
          <div className="grid grid-cols-2 gap-2">
            {(["choice4", "ox"] as GameType[]).map((g) => (
              <button
                key={g}
                type="button"
                aria-pressed={gameType === g}
                onClick={() => setGameType(g)}
                className={`rounded-xl border p-3 text-left transition ${gameType === g ? "border-accent bg-panel2" : "border-line"}`}
              >
                <div className="font-bold">{g === "choice4" ? "4지선다" : "O / X"}</div>
                <div className="text-xs text-muted">{g === "choice4" ? "네 모양 중 진짜 고르기" : "이 모양이 진짜일까?"}</div>
              </button>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="mb-2 text-sm font-bold">{mode === "survival" ? "시작 난이도" : "난이도"}</h2>
          <div className="flex flex-wrap gap-2">
            {diffs
              .filter((d) => mode !== "survival" || d !== "auto")
              .map((d) => (
                <Chip key={d} on={difficulty === d} onClick={() => setDifficulty(d)}>
                  {LABEL.difficulty[d]}
                </Chip>
              ))}
          </div>
          <p className="mt-2 text-xs text-muted">
            {mode === "survival" ? "5문제 연속으로 맞힐 때마다 한 단계 올라가요." : diffHint[difficulty]}
          </p>
        </Card>

        <Card className="grid gap-4">
          <div>
            <h2 className="mb-2 text-sm font-bold">차트 단위</h2>
            <div className="flex gap-2">
              {meta.intervals.map((iv) => (
                <Chip key={iv.value} on={filters.interval === iv.value} onClick={() => setFilters({ ...filters, interval: iv.value })} sub={fmt(meta.by_interval[iv.value].total)}>
                  {iv.label}
                </Chip>
              ))}
            </div>
          </div>
          {group("시장", "선택한 시장만", "markets", dim.markets)}
          {group("규모 (당시 시가총액 순위)", "선택한 규모만", "cap_tiers", dim.cap_tiers)}
          {group("시기", "선택한 시기만", "eras", dim.eras)}
        </Card>
      </div>

      <div className="fixed inset-x-0 bottom-0 border-t border-line bg-bg/95 backdrop-blur">
        <div className="mx-auto flex max-w-2xl items-center gap-3 px-4 py-3">
          <div className="flex-1 text-sm" aria-live="polite">
            {pool ? (
              pool.total === 0 ? (
                <span className="text-bad">이 조건에 맞는 문제가 없어요. 비슷한 조건의 문제로 진행돼요.</span>
              ) : (
                <>
                  <span className="font-bold tnum">{fmt(pool.remaining)}</span>
                  <span className="text-muted"> 문제 남음</span>
                  {pool.low && <div className="text-xs text-bad">문제가 얼마 없어요. 다 풀면 비슷한 조건으로 넓혀요.</div>}
                </>
              )
            ) : (
              <span className="text-muted">문제 수 확인 중…</span>
            )}
            {error && <div className="text-xs text-bad">{error}</div>}
          </div>
          <Button onClick={start} disabled={starting} className="min-w-28">
            {starting ? "준비 중…" : "시작"}
          </Button>
        </div>
      </div>
    </Shell>
  );
}
