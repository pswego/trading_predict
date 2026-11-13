import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type AnswerResult, type Question } from "../api/client";
import CandleChart from "../chart/CandleChart";
import Timer from "../components/Timer";
import { Button, Card, ErrorNote, LABEL, Loading, Shell, fmt, pct } from "../components/ui";
import { beep } from "../store/settings";

type Phase = "loading" | "playing" | "submitting" | "revealed" | "error";
type Choice = number | "O" | "X" | null;

export default function Play() {
  const { sid = "" } = useParams();
  const nav = useNavigate();
  const [q, setQ] = useState<Question | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [selected, setSelected] = useState<number | null>(null);
  const [mine, setMine] = useState<Choice>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);

  const load = useCallback(async () => {
    setPhase("loading");
    setError(null);
    try {
      const r = await api.next(sid);
      if ("finished" in r) {
        nav(`/result/${sid}`, { replace: true });
        return;
      }
      setQ(r);
      setSelected(null);
      setMine(null);
      setResult(null);
      busy.current = false;
      setPhase("playing");
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError((e as Error).message);
      setPhase("error");
    }
  }, [sid, nav]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = useCallback(
    async (choice: Choice) => {
      if (!q || busy.current) return;
      busy.current = true;
      setMine(choice);
      setPhase("submitting");
      try {
        const r = await api.answer(q.play_token, choice);
        setResult(r);
        setPhase("revealed");
        beep(r.correct ? "good" : "bad");
      } catch (e) {
        setError((e as Error).message);
        setPhase("error");
      }
    },
    [q],
  );

  const next = useCallback(() => {
    if (result?.state.finished) nav(`/result/${sid}`, { replace: true });
    else load();
  }, [result, nav, sid, load]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (phase === "revealed" && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        next();
        return;
      }
      if (phase !== "playing" || !q) return;
      if (q.game_type === "choice4") {
        if (["1", "2", "3", "4"].includes(e.key)) setSelected(Number(e.key) - 1);
        else if (e.key === "Enter" && selected != null) submit(selected);
      } else {
        const k = e.key.toLowerCase();
        if (k === "o") submit("O");
        else if (k === "x") submit("X");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, q, selected, submit, next]);

  if (phase === "error" && !q) {
    return (
      <Shell wide>
        <ErrorNote message={error ?? "문제를 불러오지 못했어요."} onRetry={load} />
        <p className="mt-4 text-center text-sm">
          <Link to="/" className="text-muted underline">
            홈으로
          </Link>
        </p>
      </Shell>
    );
  }
  if (!q) {
    return (
      <Shell wide>
        <Loading label="문제를 준비하는 중…" />
      </Shell>
    );
  }

  const st = result?.state ?? q.state;
  const revealed = phase === "revealed" && result;
  const isOX = q.game_type === "ox";
  const playing = phase === "playing";
  const hint = q.context_hint;

  // 메인 차트에 끼울 보기
  let fill = null;
  let fillVol = null;
  let ghost = null;
  let style: "preview" | "real" | "plain" = "preview";
  if (revealed) {
    style = "real";
    if (isOX) {
      fill = result.real ?? null;
      fillVol = result.real_volume ?? null;
      ghost = result.shown_was_real ? null : (q.candidate ?? null);
    } else {
      fill = q.options![result.correct_choice!];
      fillVol = q.option_volume?.[result.correct_choice!] ?? null;
      ghost = typeof mine === "number" && mine !== result.correct_choice ? q.options![mine] : null;
    }
  } else if (isOX) {
    fill = q.candidate ?? null;
    fillVol = q.candidate_volume ?? null;
  } else if (selected != null) {
    fill = q.options![selected];
    fillVol = q.option_volume?.[selected] ?? null;
  }
  const rangeWith = isOX ? [q.candidate, result?.real] : q.options;

  return (
    <Shell wide>
      <header className="mb-2 flex items-center gap-3 text-sm">
        <Link to="/" aria-label="그만하기" className="-ml-1 rounded-lg px-1 text-lg text-muted hover:text-ink">
          ✕
        </Link>
        <span className="font-bold tnum">
          {q.total ? `${q.index} / ${q.total}` : `${q.index}번째`}
        </span>
        <span className="flex-1" />
        {st.lives != null && (
          <span aria-label={`목숨 ${st.lives}개`} className="tracking-widest text-up">
            {"♥".repeat(st.lives)}
            <span className="opacity-25">{"♥".repeat(Math.max(3 - st.lives, 0))}</span>
          </span>
        )}
        {st.streak >= 2 && <span className="font-bold text-accent">🔥 {st.streak}</span>}
        {st.mode !== "endless" && <span className="font-bold tnum">{fmt(st.score)}점</span>}
      </header>

      {q.time_limit_ms != null && (
        <div className="mb-2">
          <Timer key={q.play_token} totalMs={q.time_limit_ms} remainingMs={q.remaining_ms ?? q.time_limit_ms} running={playing} onExpire={() => submit(null)} />
        </div>
      )}

      <div className="mb-2 flex flex-wrap items-center gap-1.5 text-xs text-muted">
        {[LABEL.market[hint.market], LABEL.cap[hint.cap_tier], LABEL.interval[hint.interval], LABEL.difficulty[q.difficulty]].map((t) => (
          <span key={t} className="rounded-md bg-panel2 px-2 py-1">
            {t}
          </span>
        ))}
        {q.widened && <span className="text-bad">고른 조건의 문제를 다 풀어서 비슷한 조건으로 넓혔어요</span>}
      </div>

      <Card className="!p-2">
        <CandleChart
          key={q.play_token}
          candles={q.candles}
          layout={q.layout}
          gapFill={fill}
          fillVolume={fillVol}
          fillStyle={style}
          ghost={ghost}
          rangeWith={rangeWith}
          volume={q.volume}
          ma={q.ma}
          animate={!!revealed}
          label="가운데가 가려진 주식 차트"
        />
      </Card>

      {revealed && <RevealPanel q={q} r={result} mine={mine} />}

      {!isOX && (
        <>
          <p className="mb-2 mt-4 text-sm font-bold">{revealed ? "보기" : "빈칸에 실제로 들어간 모양은?"}</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {q.options!.map((opt, i) => {
              const isReal = revealed && i === result.correct_choice;
              const isMine = revealed ? mine === i : selected === i;
              const ring = revealed ? (isReal ? "border-good ring-2 ring-good" : isMine ? "border-bad ring-2 ring-bad" : "border-line opacity-70") : isMine ? "border-accent ring-2 ring-accent" : "border-line hover:border-muted";
              return (
                <button
                  key={i}
                  type="button"
                  disabled={!playing}
                  aria-pressed={!revealed && isMine}
                  aria-label={`보기 ${i + 1}`}
                  onClick={() => (selected === i ? submit(i) : setSelected(i))}
                  className={`relative overflow-hidden rounded-xl border bg-panel p-1 text-left transition ${ring}`}
                >
                  <span className="absolute left-2 top-1.5 z-10 grid h-5 w-5 place-items-center rounded-md bg-panel2 text-xs font-bold">{i + 1}</span>
                  {revealed && (isReal || isMine) && (
                    <span className={`absolute right-2 top-1.5 z-10 rounded-md px-1.5 py-0.5 text-[11px] font-bold text-white ${isReal ? "bg-good" : "bg-bad"}`}>
                      {isReal ? "실제" : "내 선택"}
                    </span>
                  )}
                  <CandleChart candles={q.candles} layout={q.layout} gapFill={opt} rangeWith={q.options} mode="thumb" />
                  {revealed && !isReal && result.decoy_sources?.[i] && (
                    <span className="block px-1 pb-1 text-[11px] leading-tight text-muted">{LABEL.source[result.decoy_sources[i]!] ?? "변형한 구간"}</span>
                  )}
                </button>
              );
            })}
          </div>
        </>
      )}

      {isOX && !revealed && (
        <div className="mt-4">
          <p className="mb-3 text-center text-sm font-bold">빈칸에 들어간 이 모양, 실제 차트일까요?</p>
          <div className="grid grid-cols-2 gap-3">
            <button type="button" disabled={!playing} onClick={() => submit("O")} aria-label="O, 실제다" className="rounded-2xl border-2 border-good bg-panel py-6 text-4xl font-black text-good transition active:scale-[0.98] disabled:opacity-50">
              O
            </button>
            <button type="button" disabled={!playing} onClick={() => submit("X")} aria-label="X, 가짜다" className="rounded-2xl border-2 border-bad bg-panel py-6 text-4xl font-black text-bad transition active:scale-[0.98] disabled:opacity-50">
              X
            </button>
          </div>
        </div>
      )}

      {error && phase === "error" && (
        <div className="mt-4">
          <ErrorNote message={error} onRetry={load} />
        </div>
      )}

      <div className="sticky bottom-0 -mx-4 mt-4 bg-gradient-to-t from-bg via-bg to-transparent px-4 pb-4 pt-6">
        {revealed ? (
          <Button onClick={next} className="w-full" autoFocus>
            {result.state.finished ? "결과 보기" : "다음 문제"}
          </Button>
        ) : (
          !isOX && (
            <Button onClick={() => selected != null && submit(selected)} disabled={!playing || selected == null} className="w-full">
              {phase === "submitting" ? "채점 중…" : selected == null ? "보기를 골라 주세요" : `${selected + 1}번으로 확정`}
            </Button>
          )
        )}
      </div>
    </Shell>
  );
}

function RevealPanel({ q, r, mine }: { q: Question; r: AnswerResult; mine: Choice }) {
  const rv = r.reveal;
  const title = r.correct ? "정답!" : r.timed_out || mine == null ? "시간 초과" : "아쉬워요";
  const sub =
    q.game_type === "ox"
      ? r.shown_was_real
        ? "보여 드린 모양이 실제 차트였어요."
        : "보여 드린 모양은 가짜였어요. 흐리게 겹쳐진 것이 가짜, 선명한 것이 실제예요."
      : !r.correct && typeof mine === "number"
        ? "흐리게 겹쳐진 것이 내가 고른 모양이에요."
        : null;
  return (
    <Card className={`pop-in mt-3 border-2 ${r.correct ? "border-good" : "border-bad shake"}`}>
      <div className="flex items-baseline justify-between gap-2">
        <h2 className={`text-xl font-extrabold ${r.correct ? "text-good" : "text-bad"}`}>{title}</h2>
        {r.state.mode !== "endless" && <span className="font-bold tnum">{r.correct ? `+${fmt(r.score_delta)}점` : "0점"}</span>}
      </div>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
      <div className="mt-3 border-t border-line pt-3">
        <div className="text-lg font-bold">
          {rv.name} <span className="text-sm font-normal text-muted">{rv.code}</span>
        </div>
        <div className="text-sm text-muted">
          {LABEL.market[rv.market]} · 당시 {LABEL.cap[rv.cap_tier_then]} · 빈칸 {rv.gap_start} ~ {rv.gap_end}
        </div>
        <dl className="mt-2 grid grid-cols-3 gap-2 text-center text-sm">
          {[
            ["빈칸 수익률", rv.gap_return_pct],
            ["빈칸 안 최고", rv.gap_max_pct],
            ["빈칸 안 최저", rv.gap_min_pct],
          ].map(([k, v]) => (
            <div key={k as string} className="rounded-lg bg-panel2 py-2">
              <dt className="text-xs text-muted">{k}</dt>
              <dd className={`font-bold tnum ${(v as number) > 0 ? "text-up" : (v as number) < 0 ? "text-down" : ""}`}>{pct(v as number)}</dd>
            </div>
          ))}
        </dl>
        {rv.delisted && (
          <p className="mt-2 rounded-lg bg-panel2 px-3 py-2 text-xs">
            이 종목은 {rv.delisted.date}에 상장폐지됐어요{rv.delisted.reason ? ` (${rv.delisted.reason})` : ""}.
          </p>
        )}
      </div>
    </Card>
  );
}
