from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, default=new_id)
    code: Mapped[str] = mapped_column(String(12))
    interval: Mapped[str] = mapped_column(String(8))
    region: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[dt.date] = mapped_column(Date)
    end_date: Mapped[dt.date] = mapped_column(Date)
    gap_start: Mapped[dt.date] = mapped_column(Date)
    gap_end: Mapped[dt.date] = mapped_column(Date)
    market: Mapped[str] = mapped_column(String(8))
    cap_tier: Mapped[str] = mapped_column(String(8))
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    era: Mapped[str] = mapped_column(String(8))
    difficulty: Mapped[str] = mapped_column(String(8))
    p_score: Mapped[float] = mapped_column(Float)
    ai_p_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    elo: Mapped[float] = mapped_column(Float, default=1000.0)
    plays: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[str] = mapped_column(Text)  # JSON 문자열 (그대로 전달하므로 파싱 비용을 아낀다)
    reveal: Mapped[str] = mapped_column(Text)
    rnd: Mapped[float] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (
        Index("ix_q_filter", "interval", "difficulty", "market", "cap_tier", "era", "rnd"),
        Index("ix_q_key", "code", "interval", "region", unique=True),
    )


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    nickname: Mapped[str | None] = mapped_column(String(24), nullable=True)
    elo: Mapped[float] = mapped_column(Float, default=1000.0)
    plays: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class GameSession(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(12))  # quick | survival | daily | endless
    game_type: Mapped[str] = mapped_column(String(8))  # choice4 | ox
    filters: Mapped[dict] = mapped_column(JSON)
    difficulty: Mapped[str] = mapped_column(String(8))  # easy | normal | hard | auto
    index: Mapped[int] = mapped_column(Integer, default=0)  # 지금까지 낸 문제 수
    answered: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    lives: Mapped[int | None] = mapped_column(Integer, nullable=True)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)
    widened: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Play(Base):
    __tablename__ = "plays"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    code: Mapped[str] = mapped_column(String(12))
    interval: Mapped[str] = mapped_column(String(8))
    start_date: Mapped[dt.date] = mapped_column(Date)
    end_date: Mapped[dt.date] = mapped_column(Date)
    difficulty: Mapped[str] = mapped_column(String(8))
    option_order: Mapped[list] = mapped_column(JSON)  # 화면 위치 → 원래 보기 번호 (0이 실제)
    ox_shown: Mapped[int | None] = mapped_column(Integer, nullable=True)  # O/X에서 보여 준 원래 보기 번호
    served_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    answered_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    choice: Mapped[str | None] = mapped_column(String(4), nullable=True)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (Index("ix_play_user_code", "user_id", "code"), Index("ix_play_user_time", "user_id", "served_at"))


class DailySet(Base):
    __tablename__ = "daily_sets"
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    question_ids: Mapped[list] = mapped_column(JSON)


class DailyResult(Base):
    __tablename__ = "daily_results"
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    score: Mapped[int] = mapped_column(Integer)
    correct_count: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)


class PoolStat(Base):
    __tablename__ = "pool_stats"
    interval: Mapped[str] = mapped_column(String(8), primary_key=True)
    market: Mapped[str] = mapped_column(String(8), primary_key=True)
    cap_tier: Mapped[str] = mapped_column(String(8), primary_key=True)
    era: Mapped[str] = mapped_column(String(8), primary_key=True)
    difficulty: Mapped[str] = mapped_column(String(8), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)


class Stock(Base):
    __tablename__ = "stocks"
    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    market: Mapped[str] = mapped_column(String(8))
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_delisted: Mapped[bool] = mapped_column(Boolean, default=False)
