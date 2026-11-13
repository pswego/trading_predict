import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Summary } from "../api/client";
import { Button, Card, ErrorNote, LABEL, Loading, Shell, TopBar, fmt, pct } from "../components/ui";

export async function share(text: string): Promise<"shared" | "copied" | "failed"> {
  const full = `${text}\n${location.origin}`;
  try {
    if (navigator.share) {
      await navigator.share({ text: full });
      return "shared";
    }
    await navigator.clipboard.writeText(full);
    return "copied";
  } catch {
    return "failed";
  }
}

export default function Result() {
  const { sid = "" } = useParams();
  const [s, setS] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = () => {
    setError(null);
    api.summary(sid).then(setS).catch((e) => setError(e.message));
  };
  useEffect(load, [sid]);

  if (error) {
    return (
      <Shell>
        <TopBar title="결과" />
        <ErrorNote message={error} onRetry={load} />
      </Shell>
    );
  }
  if (!s) {
    return (
      <Shell>
        <TopBar title="결과" />
        <Loading />
      </Shell>
    );
  }

  const rate = s.answered ? Math.round((s.correct / s.answered) * 100) : 0;
  const again = s.mode === "daily" ? "/daily" : `/setup/${s.mode}`;
  return (
    <Shell>
      <TopBar title={`${LABEL.mode[s.mode]} 결과`} />
      <Card className="text-center">
        {s.mode !== "endless" && (
          <>
            <div className="text-sm text-muted">점수</div>
            <div className="text-5xl font-black tnum">{fmt(s.score)}</div>
          </>
        )}
        <div className="mt-3 flex flex-wrap justify-center gap-1 text-xl" aria-label={`${s.answered}문제 중 ${s.correct}문제 정답`}>
          {s.plays.map((p, i) => (
            <span key={i}>{p.correct ? "🟩" : "🟥"}</span>
          ))}
        </div>
        <dl className="mt-4 grid grid-cols-3 gap-2 text-sm">
          <div className="rounded-lg bg-panel2 py-2">
            <dt className="text-xs text-muted">정답</dt>
            <dd className="font-bold tnum">
              {s.correct} / {s.answered} ({rate}%)
            </dd>
          </div>
          <div className="rounded-lg bg-panel2 py-2">
            <dt className="text-xs text-muted">최고 연속 정답</dt>
            <dd className="font-bold tnum">{s.best_streak}</dd>
          </div>
          <div className="rounded-lg bg-panel2 py-2">
            <dt className="text-xs text-muted">실력 점수</dt>
            <dd className="font-bold tnum">{fmt(s.elo)}</dd>
          </div>
        </dl>
      </Card>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <Button
          variant="ghost"
          onClick={async () => {
            const r = await share(s.share_text);
            setNote(r === "copied" ? "결과를 복사했어요." : r === "failed" ? "공유하지 못했어요." : null);
          }}
        >
          결과 공유
        </Button>
        {s.mode === "daily" ? (
          <Link to="/daily" className="rounded-xl bg-accent px-4 py-3 text-center font-bold text-accent-ink">
            순위 보기
          </Link>
        ) : (
          <Link to={again} className="rounded-xl bg-accent px-4 py-3 text-center font-bold text-accent-ink">
            다시 하기
          </Link>
        )}
      </div>
      {note && (
        <p className="mt-2 text-center text-sm text-muted" role="status">
          {note}
        </p>
      )}

      {s.plays.length > 0 && (
        <Card className="mt-4 !p-0">
          <h2 className="border-b border-line px-4 py-3 text-sm font-bold">문제별 결과</h2>
          <ul>
            {s.plays.map((p, i) => (
              <li key={i} className="flex items-center gap-3 border-b border-line px-4 py-2.5 text-sm last:border-0">
                <span aria-label={p.correct ? "정답" : "오답"}>{p.correct ? "🟩" : "🟥"}</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-semibold">{p.name}</div>
                  <div className="text-xs text-muted">
                    {p.gap_start} ~ {p.gap_end} · {LABEL.difficulty[p.difficulty]}
                  </div>
                </div>
                <span className={`tnum ${p.gap_return_pct > 0 ? "text-up" : p.gap_return_pct < 0 ? "text-down" : ""}`}>{pct(p.gap_return_pct)}</span>
                {s.mode !== "endless" && <span className="w-14 text-right font-bold tnum">{fmt(p.score)}</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}
      <p className="mt-4 text-center text-sm">
        <Link to="/" className="text-muted underline">
          홈으로
        </Link>
      </p>
    </Shell>
  );
}
