from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Filters(BaseModel):
    interval: Literal["day", "week"] = "day"
    markets: list[str] = []
    cap_tiers: list[str] = []
    eras: list[str] = []


class SessionCreate(BaseModel):
    mode: Literal["quick", "survival", "endless"] = "quick"
    game_type: Literal["choice4", "ox"] = "choice4"
    filters: Filters = Filters()
    difficulty: Literal["easy", "normal", "hard", "auto"] = "normal"


class Answer(BaseModel):
    play_token: str
    choice: int | str | None = None  # 4지선다: 0~3, O/X: "O" | "X", 시간 초과: null


class Nickname(BaseModel):
    nickname: str = Field(min_length=2, max_length=12)
