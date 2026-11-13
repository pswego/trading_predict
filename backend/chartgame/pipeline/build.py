"""적재: 문제 Parquet → DB. 이미 있는 (종목, 주기, 영역)은 건드리지 않는다 → 문제 ID가 안정적이다."""
from __future__ import annotations

import datetime as dt
import zlib

import pandas as pd
from sqlalchemy import delete, func, select

from .. import config
from ..db.models import PoolStat, Question, Stock
from ..db.session import make_session
from ..sources.listing import load_stocks


def _rnd(code: str, interval: str, region: int) -> float:
    return (zlib.crc32(f"rnd|{code}|{interval}|{region}".encode()) % 10**9) / 10**9


def initial_elo(p_score: float, ai_p_real: float | None) -> float:
    """문제 Elo 초기값: 추측 가능성이 낮을수록, 판별기가 헷갈릴수록 높다."""
    elo = 1000 + 600 * (0.5 - p_score)
    if ai_p_real is not None:
        elo += 200 * (0.25 - ai_p_real)
    return round(elo, 1)


def load_questions(df: pd.DataFrame, db=None) -> int:
    db = db or make_session()
    existing = set(db.execute(select(Question.code, Question.interval, Question.region)).all())
    added = 0
    d = dt.date.fromisoformat
    for r in df.itertuples():
        if (r.code, r.interval, int(r.region)) in existing:
            continue
        ai = float(r.ai_p_real) if hasattr(r, "ai_p_real") and pd.notna(r.ai_p_real) else None
        db.add(Question(
            code=r.code, interval=r.interval, region=int(r.region),
            start_date=d(r.start_date), end_date=d(r.end_date), gap_start=d(r.gap_start), gap_end=d(r.gap_end),
            market=r.market, cap_tier=r.cap_tier, sector=r.sector if isinstance(r.sector, str) else None, era=r.era,
            difficulty=r.difficulty, p_score=float(r.p_score), ai_p_real=ai, elo=initial_elo(float(r.p_score), ai),
            payload=r.payload, reveal=r.reveal, rnd=_rnd(r.code, r.interval, int(r.region)),
        ))
        added += 1
        if added % 5000 == 0:
            db.commit()
    db.commit()
    refresh_stats(db)
    return added


def refresh_stats(db) -> None:
    db.execute(delete(PoolStat))
    q = select(Question.interval, Question.market, Question.cap_tier, Question.era, Question.difficulty,
               func.count()).group_by(Question.interval, Question.market, Question.cap_tier, Question.era, Question.difficulty)
    for iv, m, t, e, dff, n in db.execute(q):
        db.add(PoolStat(interval=iv, market=m, cap_tier=t, era=e, difficulty=dff, count=n))
    db.commit()


def load_stocks_table(db=None) -> None:
    db = db or make_session()
    have = set(db.scalars(select(Stock.code)))
    for r in load_stocks().itertuples():
        if r.code not in have:
            db.add(Stock(code=r.code, name=r.name, market=r.market,
                         sector=r.sector if isinstance(r.sector, str) else None, is_delisted=bool(r.is_delisted)))
    db.commit()


def run() -> dict:
    db = make_session()
    out = {}
    for iv in config.INTERVALS:
        path = config.WORK / f"questions_{iv}.parquet"
        if path.exists():
            out[iv] = load_questions(pd.read_parquet(path), db)
    load_stocks_table(db)
    out["total"] = db.scalar(select(func.count()).select_from(Question))
    return out
