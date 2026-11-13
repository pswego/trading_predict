import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type DailyStatus, type Leaderboard } from "../api/client";
import { Button, Card, ErrorNote, Loading, Shell, TopBar, fmt } from "../components/ui";

export default function Daily() {
  const nav = useNavigate();
  const [st, setSt] = useState<DailyStatus | null>(null);
  const [lb, setLb] = useState<Leaderboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nick, setNick] = useState("");
  const [nickMsg, setNickMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setError(null);
    Promise.all([api.daily(), api.leaderboard()])
      .then(([d, l]) => {
        setSt(d);
        setLb(l);
      })
      .catch((e) => setError(e.message));
  };
  useEffect(load, []);

  const start = async () => {
    setBusy(true);
    try {
      const s = await api.dailyStart();
      nav(`/play/${s.session_id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  const saveNick = async () => {
    setNickMsg(null);
    try {
      await api.setNickname(nick.trim());
      setNickMsg("저장했어요.");
      setLb(await api.leaderboard());
    } catch (e) {
      setNickMsg((e as Error).message);
    }
  };

  if (error && !st) {
    return (
      <Shell>
        <TopBar title="데일리 챌린지" />
        <ErrorNote message={error} onRetry={load} />
      </Shell>
    );
  }
  if (!st || !lb) {
    return (
      <Shell>
        <TopBar title="데일리 챌린지" />
        <Loading />
      </Shell>
    );
  }

  const sess = st.session;
  return (
    <Shell>
      <TopBar title="데일리 챌린지" />
      <Card className="text-center">
        <div className="text-sm text-muted">{st.date}</div>
        {sess?.finished ? (
          <>
            <div className="mt-1 text-4xl font-black tnum">{fmt(sess.score)}점</div>
            <div className="mt-1 text-sm text-muted">
              {sess.correct} / {sess.answered} 정답{lb.my_rank ? ` · ${fmt(lb.players)}명 중 ${fmt(lb.my_rank)}위` : ""}
            </div>
            <p className="mt-3 text-sm text-muted">오늘 문제는 다 풀었어요. 내일 새 문제가 나와요.</p>
          </>
        ) : !st.available ? (
          <p className="mt-2 text-sm text-muted">오늘의 문제가 아직 준비되지 않았어요.</p>
        ) : (
          <>
            <p className="mt-2 text-sm">
              모두가 같은 5문제를 풉니다. 쉬움 2 · 보통 2 · 어려움 1, 하루에 한 번만 도전할 수 있어요.
            </p>
            <Button onClick={start} disabled={busy} className="mt-4 w-full">
              {sess ? `이어서 하기 (${sess.answered} / 5)` : "도전하기"}
            </Button>
          </>
        )}
        {error && <p className="mt-2 text-sm text-bad">{error}</p>}
      </Card>

      <Card className="mt-4 !p-0">
        <h2 className="border-b border-line px-4 py-3 text-sm font-bold">오늘의 순위 {lb.players > 0 && <span className="font-normal text-muted">· {fmt(lb.players)}명 참여</span>}</h2>
        {lb.top.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-muted">아직 기록이 없어요. 첫 번째로 도전해 보세요.</p>
        ) : (
          <ol>
            {lb.top.map((t) => (
              <li key={t.rank} className={`flex items-center gap-3 border-b border-line px-4 py-2.5 text-sm last:border-0 ${t.me ? "bg-panel2 font-bold" : ""}`}>
                <span className="w-7 text-muted tnum">{t.rank}</span>
                <span className="min-w-0 flex-1 truncate">
                  {t.nickname}
                  {t.me && <span className="ml-1 text-xs text-accent">나</span>}
                </span>
                <span className="text-xs text-muted tnum">
                  {t.correct}/5 · {(t.duration_ms / 1000).toFixed(1)}초
                </span>
                <span className="w-16 text-right tnum">{fmt(t.score)}</span>
              </li>
            ))}
          </ol>
        )}
      </Card>

      {sess?.finished && (
        <Card className="mt-4">
          <label htmlFor="nick" className="text-sm font-bold">
            순위표에 표시할 닉네임
          </label>
          <div className="mt-2 flex gap-2">
            <input
              id="nick"
              value={nick}
              onChange={(e) => setNick(e.target.value)}
              maxLength={12}
              placeholder="2~12자"
              className="min-w-0 flex-1 rounded-xl border border-line bg-bg px-3 py-2 outline-none focus:border-accent"
            />
            <Button variant="ghost" onClick={saveNick} disabled={nick.trim().length < 2}>
              저장
            </Button>
          </div>
          {nickMsg && (
            <p className="mt-2 text-xs text-muted" role="status">
              {nickMsg}
            </p>
          )}
        </Card>
      )}
    </Shell>
  );
}
