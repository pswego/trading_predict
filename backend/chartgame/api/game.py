"""게임 진행 로직: 문제 내기, 채점, 세션 상태."""
from __future__ import annotations

import datetime as dt
import json
import random
import zlib

from sqlalchemy import select

from .. import config
from ..db.models import DailyResult, DailySet, GameSession, Play, Question, User, now
from .services import elo, scoring, selector, tokens

GRACE_MS = 1500  # 네트워크 지연 여유


def kst_today() -> dt.date:
    return (now() + dt.timedelta(hours=9)).date()


def total_for(sess: GameSession) -> int | None:
    return {"quick": config.QUICK_TOTAL, "daily": len(config.DAILY_MIX)}.get(sess.mode)


def time_limit(sess: GameSession, difficulty: str) -> int | None:
    return None if sess.mode == "endless" else config.TIME_LIMIT_MS[sess.game_type][difficulty]


def daily_question_ids(db, date: dt.date) -> list[int]:
    row = db.get(DailySet, date)
    if row:
        return row.question_ids
    ids: list[int] = []
    for i, diff in enumerate(config.DAILY_MIX):
        r = (zlib.crc32(f"daily|{date}|{i}".encode()) % 10**9) / 10**9
        base = select(Question.id).where(Question.interval == "day", Question.difficulty == diff, Question.id.notin_(ids))
        qid = db.scalar(base.where(Question.rnd >= r).order_by(Question.rnd).limit(1)) \
            or db.scalar(base.order_by(Question.rnd).limit(1))
        if qid:
            ids.append(qid)
    if ids:
        db.add(DailySet(date=date, question_ids=ids))
        db.commit()
    return ids


def state(sess: GameSession) -> dict:
    return {"session_id": sess.id, "mode": sess.mode, "game_type": sess.game_type, "score": sess.score,
            "streak": sess.streak, "lives": sess.lives, "answered": sess.answered, "correct": sess.correct,
            "total": total_for(sess), "finished": sess.finished}


def render(q: Question, play: Play, sess: GameSession, remaining_ms: int | None) -> dict:
    """클라이언트에 보내는 문제. 정답 위치·종목·날짜는 들어가지 않는다."""
    p = json.loads(q.payload)
    out = {
        "play_token": tokens.make(play.id),
        "index": sess.index, "total": total_for(sess),
        "game_type": sess.game_type, "difficulty": q.difficulty,
        "time_limit_ms": time_limit(sess, q.difficulty), "remaining_ms": remaining_ms,
        "layout": p["layout"], "candles": p["candles"], "volume": p["volume"], "ma": p["ma"],
        "context_hint": {"market": q.market, "cap_tier": q.cap_tier, "interval": q.interval},
        "state": state(sess), "widened": sess.widened,
    }
    if sess.game_type == "choice4":
        out["options"] = [p["options"][i] for i in play.option_order]
        out["option_volume"] = [p["option_volume"][i] for i in play.option_order] if p["option_volume"] else None
    else:
        out["candidate"] = p["options"][play.ox_shown]
        out["candidate_volume"] = p["option_volume"][play.ox_shown] if p["option_volume"] else None
    return out


def apply_answer(db, user: User, sess: GameSession, play: Play, q: Question, choice, at: dt.datetime) -> dict:
    limit = time_limit(sess, q.difficulty)
    elapsed = int((at - play.served_at).total_seconds() * 1000)
    timed_out = limit is not None and elapsed > limit + GRACE_MS
    real_pos = play.option_order.index(0)
    if timed_out or choice is None:
        correct, stored = False, None
    elif sess.game_type == "choice4":
        correct, stored = choice == real_pos, str(choice)
    else:
        correct, stored = (choice == "O") == (play.ox_shown == 0), str(choice)

    pts = 0
    if sess.mode != "endless":
        pts = scoring.score(correct, q.difficulty, sess.game_type, min(elapsed, limit or elapsed), sess.streak)
    play.answered_at, play.choice, play.correct, play.score = at, stored, correct, pts
    sess.answered += 1
    sess.correct += int(correct)
    sess.score += pts
    sess.streak = sess.streak + 1 if correct else 0
    if sess.mode == "survival" and not correct:
        sess.lives = max((sess.lives or 0) - 1, 0)
    total = total_for(sess)
    if (total and sess.answered >= total) or (sess.mode == "survival" and sess.lives == 0):
        sess.finished = True

    before = user.elo
    user.elo, q.elo = elo.update(user.elo, q.elo, correct, sess.game_type, user.plays, q.plays)
    user.plays += 1
    user.best_streak = max(user.best_streak, sess.streak)
    q.plays += 1
    q.correct += int(correct)

    if sess.finished and sess.mode == "daily" and not db.get(DailyResult, (sess.daily_date, user.id)):
        plays = db.scalars(select(Play).where(Play.session_id == sess.id)).all()
        dur = sum(int((p.answered_at - p.served_at).total_seconds() * 1000) for p in plays if p.answered_at)
        db.add(DailyResult(date=sess.daily_date, user_id=user.id, score=sess.score,
                           correct_count=sess.correct, duration_ms=dur))
    db.commit()

    p = json.loads(q.payload)
    out = {
        "correct": correct, "timed_out": timed_out, "score_delta": pts, "state": state(sess),
        "elo": {"before": round(before), "after": round(user.elo)},
        "reveal": json.loads(q.reveal),
    }
    if sess.game_type == "choice4":
        out["correct_choice"] = real_pos
        out["decoy_sources"] = [None if i == 0 else out["reveal"]["decoy_sources"][i - 1] for i in play.option_order]
    else:
        out["shown_was_real"] = play.ox_shown == 0
        out["real"] = p["options"][0]
        out["real_volume"] = p["option_volume"][0] if p["option_volume"] else None
    return out


def next_question(db, user: User, sess: GameSession) -> dict:
    if sess.finished:
        return {"finished": True, "state": state(sess)}
    pending = db.scalar(select(Play).where(Play.session_id == sess.id, Play.answered_at.is_(None)).order_by(Play.id.desc()))
    if pending:
        q = db.get(Question, pending.question_id)
        limit = time_limit(sess, q.difficulty)
        elapsed = int((now() - pending.served_at).total_seconds() * 1000)
        if limit is None or elapsed <= limit:
            return render(q, pending, sess, None if limit is None else limit - elapsed)
        apply_answer(db, user, sess, pending, q, None, now())  # 새로고침으로 시간 초과를 피할 수 없다
        if sess.finished:
            return {"finished": True, "state": state(sess)}

    widened = False
    if sess.mode == "daily":
        ids = daily_question_ids(db, sess.daily_date)
        q = db.get(Question, ids[sess.index]) if sess.index < len(ids) else None
    else:
        q, widened = selector.pick(db, user, sess)
    if q is None:
        sess.finished = True
        db.commit()
        return {"finished": True, "state": state(sess), "empty": True}

    order = [0, 1, 2, 3]
    random.shuffle(order)
    ox = None
    if sess.game_type == "ox":
        ox = 0 if random.random() < 0.5 else random.choice([1, 2, 3])
    play = Play(session_id=sess.id, user_id=user.id, question_id=q.id, code=q.code, interval=q.interval,
                start_date=q.start_date, end_date=q.end_date, difficulty=q.difficulty,
                option_order=order, ox_shown=ox, served_at=now())
    sess.index += 1
    sess.widened = sess.widened or widened
    db.add(play)
    db.commit()
    return render(q, play, sess, time_limit(sess, q.difficulty))
