from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from .. import config
from ..db.models import DailyResult, GameSession, Play, PoolStat, Question, User, now
from . import game, schemas
from .deps import get_db, get_user
from .services import selector, tokens

router = APIRouter(prefix="/api")
LABELS = {
    "markets": {"KOSPI": "코스피", "KOSDAQ": "코스닥"},
    "cap_tiers": {"large": "대형주", "mid": "중형주", "small": "소형주", "micro": "초소형주"},
    "eras": {"2000s": "2000년대", "2010s": "2010년대", "2020s": "2020년대"},
    "intervals": {"day": "일봉", "week": "주봉"},
    "difficulties": {"easy": "쉬움", "normal": "보통", "hard": "어려움"},
}
BANNED = re.compile(r"(운영자|관리자|admin|씨발|시발|병신|fuck|shit)", re.I)


def _session(db, user: User, sid: str) -> GameSession:
    sess = db.get(GameSession, sid)
    if not sess or sess.user_id != user.id:
        raise HTTPException(404, "세션을 찾을 수 없어요.")
    return sess


@router.get("/health")
def health(db=Depends(get_db)):
    n = db.scalar(select(func.count()).select_from(Question))
    last = db.scalar(select(func.max(Question.created_at)))
    return {"ok": True, "questions": n, "last_build": last.isoformat() if last else None}


@router.get("/meta/filters")
def meta_filters(db=Depends(get_db)):
    rows = db.execute(select(PoolStat)).scalars().all()

    def agg(attr: str, interval: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in rows:
            if r.interval == interval:
                out[getattr(r, attr)] = out.get(getattr(r, attr), 0) + r.count
        return out

    dims = {"markets": "market", "cap_tiers": "cap_tier", "eras": "era", "difficulties": "difficulty"}
    by_interval = {}
    for iv in config.INTERVALS:
        by_interval[iv] = {
            "total": sum(r.count for r in rows if r.interval == iv),
            **{dim: [{"value": v, "label": lab, "count": agg(attr, iv).get(v, 0)} for v, lab in LABELS[dim].items()]
               for dim, attr in dims.items()},
        }
    return {"intervals": [{"value": v, "label": lab} for v, lab in LABELS["intervals"].items()],
            "by_interval": by_interval, "time_limit_ms": config.TIME_LIMIT_MS,
            "quick_total": config.QUICK_TOTAL, "survival_lives": config.SURVIVAL_LIVES}


@router.post("/pool/count")
def pool_count(body: schemas.SessionCreate, db=Depends(get_db), user: User = Depends(get_user)):
    diff = body.difficulty if body.difficulty != "auto" and body.mode != "survival" else None
    return selector.pool_count(db, user, body.filters.model_dump(), diff)


@router.post("/sessions")
def create_session(body: schemas.SessionCreate, db=Depends(get_db), user: User = Depends(get_user)):
    sess = GameSession(user_id=user.id, mode=body.mode, game_type=body.game_type,
                       filters=selector.normalize_filters(body.filters.model_dump()), difficulty=body.difficulty,
                       lives=config.SURVIVAL_LIVES if body.mode == "survival" else None)
    db.add(sess)
    db.commit()
    return game.state(sess)


@router.get("/sessions/{sid}/next")
def next_question(sid: str, db=Depends(get_db), user: User = Depends(get_user)):
    return game.next_question(db, user, _session(db, user, sid))


@router.post("/answer")
def answer(body: schemas.Answer, db=Depends(get_db), user: User = Depends(get_user)):
    pid = tokens.read(body.play_token)
    play = db.get(Play, pid) if pid else None
    if not play or play.user_id != user.id:
        raise HTTPException(400, "유효하지 않은 문제예요. 다음 문제로 넘어가 주세요.")
    if play.answered_at is not None:
        raise HTTPException(409, "이미 답한 문제예요.")
    sess = db.get(GameSession, play.session_id)
    choice = body.choice
    if choice is not None:
        if sess.game_type == "choice4" and choice not in (0, 1, 2, 3):
            raise HTTPException(422, "choice는 0~3이어야 해요.")
        if sess.game_type == "ox" and choice not in ("O", "X"):
            raise HTTPException(422, "choice는 O 또는 X여야 해요.")
    return game.apply_answer(db, user, sess, play, db.get(Question, play.question_id), choice, now())


@router.get("/sessions/{sid}/summary")
def summary(sid: str, db=Depends(get_db), user: User = Depends(get_user)):
    sess = _session(db, user, sid)
    rows = db.execute(select(Play, Question.reveal).join(Question, Question.id == Play.question_id)
                      .where(Play.session_id == sid, Play.answered_at.is_not(None)).order_by(Play.id)).all()
    plays = []
    for p, reveal in rows:
        rv = json.loads(reveal)
        plays.append({"correct": bool(p.correct), "score": p.score, "difficulty": p.difficulty,
                      "name": rv["name"], "code": rv["code"], "gap_start": rv["gap_start"], "gap_end": rv["gap_end"],
                      "gap_return_pct": rv["gap_return_pct"]})
    marks = "".join("🟩" if p["correct"] else "🟥" for p in plays)
    title = {"quick": "빠른 10문제", "survival": "서바이벌", "daily": f"데일리 {sess.daily_date}", "endless": "무한 연습"}[sess.mode]
    share = f"빈칸 차트 · {title}\n{marks}\n{sess.correct}/{sess.answered} 정답 · {sess.score:,}점"
    return {**game.state(sess), "plays": plays, "share_text": share, "elo": round(user.elo),
            "best_streak": max([0] + _streaks(plays)), "daily_date": str(sess.daily_date) if sess.daily_date else None}


def _streaks(plays: list[dict]) -> list[int]:
    out, run = [], 0
    for p in plays:
        run = run + 1 if p["correct"] else 0
        out.append(run)
    return out


# ---------- 데일리 ----------
@router.get("/daily")
def daily_status(db=Depends(get_db), user: User = Depends(get_user)):
    date = game.kst_today()
    sess = db.scalar(select(GameSession).where(GameSession.user_id == user.id, GameSession.daily_date == date))
    return {"date": str(date), "available": len(game.daily_question_ids(db, date)) == len(config.DAILY_MIX),
            "session": game.state(sess) if sess else None}


@router.post("/daily/start")
def daily_start(db=Depends(get_db), user: User = Depends(get_user)):
    date = game.kst_today()
    sess = db.scalar(select(GameSession).where(GameSession.user_id == user.id, GameSession.daily_date == date))
    if sess is None:
        if len(game.daily_question_ids(db, date)) < len(config.DAILY_MIX):
            raise HTTPException(503, "오늘의 문제가 아직 준비되지 않았어요.")
        sess = GameSession(user_id=user.id, mode="daily", game_type="choice4", filters={}, difficulty="auto", daily_date=date)
        db.add(sess)
        db.commit()
    return game.state(sess)


@router.get("/daily/leaderboard")
def leaderboard(date: str | None = None, db=Depends(get_db), user: User = Depends(get_user)):
    import datetime as dt

    try:
        d = dt.date.fromisoformat(date) if date else game.kst_today()
    except ValueError:
        raise HTTPException(422, "날짜 형식은 YYYY-MM-DD예요.") from None
    order = (DailyResult.score.desc(), DailyResult.duration_ms.asc())
    rows = db.execute(select(DailyResult, User).join(User, User.id == DailyResult.user_id)
                      .where(DailyResult.date == d).order_by(*order).limit(100)).all()
    name = lambda u: u.nickname or f"익명-{u.id[:4]}"  # noqa: E731
    top = [{"rank": i + 1, "nickname": name(u), "score": r.score, "correct": r.correct_count,
            "duration_ms": r.duration_ms, "me": u.id == user.id} for i, (r, u) in enumerate(rows)]
    mine = db.get(DailyResult, (d, user.id))
    my_rank = None
    if mine:
        better = db.scalar(select(func.count()).select_from(DailyResult).where(
            DailyResult.date == d,
            (DailyResult.score > mine.score) | ((DailyResult.score == mine.score) & (DailyResult.duration_ms < mine.duration_ms))))
        my_rank = better + 1
    total = db.scalar(select(func.count()).select_from(DailyResult).where(DailyResult.date == d))
    return {"date": str(d), "top": top, "my_rank": my_rank, "players": total}


# ---------- 내 정보 ----------
@router.post("/me/nickname")
def set_nickname(body: schemas.Nickname, db=Depends(get_db), user: User = Depends(get_user)):
    nick = body.nickname.strip()
    if len(nick) < 2 or BANNED.search(nick) or not re.fullmatch(r"[0-9A-Za-z가-힣_\- ]+", nick):
        raise HTTPException(422, "닉네임은 2~12자의 한글·영문·숫자만 쓸 수 있어요.")
    user.nickname = nick
    db.commit()
    return {"nickname": nick}


@router.get("/me/stats")
def my_stats(db=Depends(get_db), user: User = Depends(get_user)):
    def by(col):
        q = select(col, func.count(), func.sum(Play.correct)) \
            .join(Question, Question.id == Play.question_id) \
            .where(Play.user_id == user.id, Play.answered_at.is_not(None)).group_by(col)
        return [{"key": k, "plays": n, "correct": int(c or 0)} for k, n, c in db.execute(q)]

    total = db.execute(select(func.count(), func.sum(Play.correct), func.sum(Play.score))
                       .where(Play.user_id == user.id, Play.answered_at.is_not(None))).one()
    return {"nickname": user.nickname, "elo": round(user.elo), "best_streak": user.best_streak,
            "plays": total[0], "correct": int(total[1] or 0), "score": int(total[2] or 0),
            "by_difficulty": by(Question.difficulty), "by_market": by(Question.market),
            "by_cap_tier": by(Question.cap_tier), "by_interval": by(Question.interval)}
