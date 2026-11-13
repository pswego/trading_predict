"""출제: 필터에 맞는 문제 중 사용자가 아직 안 본 것을 고른다."""
from __future__ import annotations

import random

from sqlalchemy import func, select

from ... import config
from ...db.models import GameSession, Play, Question, User

TIERS = ["large", "mid", "small", "micro"]
ERAS = ["2000s", "2010s", "2020s"]
MARKETS = ["KOSPI", "KOSDAQ"]
LEVELS = list(config.DIFFICULTIES)


def normalize_filters(f: dict | None) -> dict:
    f = f or {}
    pick = lambda key, allowed: sorted({x for x in (f.get(key) or []) if x in allowed})  # noqa: E731
    return {
        "interval": f.get("interval") if f.get("interval") in config.INTERVALS else "day",
        "markets": pick("markets", MARKETS), "cap_tiers": pick("cap_tiers", TIERS), "eras": pick("eras", ERAS),
    }


def conditions(f: dict, difficulty: str | None):
    conds = [Question.interval == f["interval"]]
    if f["markets"]:
        conds.append(Question.market.in_(f["markets"]))
    if f["cap_tiers"]:
        conds.append(Question.cap_tier.in_(f["cap_tiers"]))
    if f["eras"]:
        conds.append(Question.era.in_(f["eras"]))
    if difficulty in LEVELS:
        conds.append(Question.difficulty == difficulty)
    return conds


def _neighbors(sel: list[str], order: list[str]) -> list[str]:
    if not sel:
        return sel
    idx = {order.index(x) for x in sel}
    idx |= {i + d for i in list(idx) for d in (-1, 1) if 0 <= i + d < len(order)}
    return [order[i] for i in sorted(idx)]


def widen(f: dict, step: int) -> dict:
    """step 1: 옆 시총 구간·옆 연대까지. step 2: 시총·연대 조건 해제. step 3: 시장 조건도 해제."""
    g = dict(f)
    if step == 1:
        g["cap_tiers"], g["eras"] = _neighbors(f["cap_tiers"], TIERS), _neighbors(f["eras"], ERAS)
    if step >= 2:
        g["cap_tiers"], g["eras"] = [], []
    if step >= 3:
        g["markets"] = []
    return g


def overlap_frac(a0, a1, b0, b1) -> float:
    """구간 a가 b와 겹치는 비율 (a 길이 기준)."""
    days = (min(a1, b1) - max(a0, b0)).days + 1
    return max(days, 0) / max((a1 - a0).days + 1, 1)


def survival_level(base: str, streak: int) -> str:
    start = LEVELS.index(base) if base in LEVELS else 0
    return LEVELS[min(start + streak // 5, len(LEVELS) - 1)]


def _candidates(db, conds, n: int = 200) -> list[Question]:
    r = random.random()
    cols = select(Question).where(*conds)
    rows = list(db.scalars(cols.where(Question.rnd >= r).order_by(Question.rnd).limit(n)))
    if len(rows) < n:
        rows += list(db.scalars(cols.where(Question.rnd < r).order_by(Question.rnd).limit(n - len(rows))))
    return rows


def _unseen(db, user: User, cands: list[Question], allow_repeat: bool = False) -> list[Question]:
    if not cands:
        return []
    recent = set(db.scalars(select(Play.code).where(Play.user_id == user.id).order_by(Play.id.desc()).limit(config.STOCK_COOLDOWN)))
    cands = [q for q in cands if q.code not in recent] or ([] if not allow_repeat else cands)
    if allow_repeat:
        return cands
    codes = {q.code for q in cands}
    seen: dict[tuple[str, str], list] = {}
    q = select(Play.code, Play.interval, Play.start_date, Play.end_date).where(Play.user_id == user.id, Play.code.in_(codes))
    for code, iv, s, e in db.execute(q):
        seen.setdefault((code, iv), []).append((s, e))
    out = []
    for c in cands:
        ranges = seen.get((c.code, c.interval), [])
        if all(overlap_frac(c.start_date, c.end_date, s, e) < config.OVERLAP_FRAC for s, e in ranges):
            out.append(c)
    return out


def pick(db, user: User, sess: GameSession) -> tuple[Question | None, bool]:
    """(문제, 조건을 넓혔는지). 문제가 정말 하나도 없으면 (None, False)."""
    f = normalize_filters(sess.filters)
    if sess.mode == "survival":
        difficulty = survival_level(sess.difficulty, sess.streak)
    else:
        difficulty = sess.difficulty if sess.difficulty in LEVELS else None
    for step in range(4):
        conds = conditions(widen(f, step) if step else f, difficulty)
        for _ in range(2):
            pool = _unseen(db, user, _candidates(db, conds))
            if pool:
                if difficulty is None:  # 자동: 사용자 실력에 가까운 문제
                    pool.sort(key=lambda q: abs(q.elo - user.elo))
                    pool = pool[:10]
                return random.choice(pool), step > 0
    pool = _unseen(db, user, _candidates(db, conditions(f, difficulty)), allow_repeat=True)
    if not pool:
        pool = _candidates(db, conditions(widen(f, 3), None), 50)
    return (random.choice(pool), True) if pool else (None, False)


def pool_count(db, user: User, filters: dict, difficulty: str | None) -> dict:
    f = normalize_filters(filters)
    conds = conditions(f, difficulty)
    total = db.scalar(select(func.count()).select_from(Question).where(*conds)) or 0
    played = db.scalar(
        select(func.count(func.distinct(Play.question_id))).join(Question, Question.id == Play.question_id)
        .where(Play.user_id == user.id, *conds)) or 0
    return {"total": total, "remaining": max(total - played, 0), "low": (total - played) < config.LOW_POOL_WARN}
