"""찍어서 맞힐 확률을 반영한 Elo (IRT 3PL 형태)."""
from __future__ import annotations

import math

GUESS = {"choice4": 0.25, "ox": 0.5}


def expected(r_user: float, r_question: float, guess: float) -> float:
    return guess + (1 - guess) / (1 + 10 ** ((r_question - r_user) / 400))


def update(r_user: float, r_question: float, correct: bool, game_type: str,
           user_plays: int, question_plays: int) -> tuple[float, float]:
    p = expected(r_user, r_question, GUESS[game_type])
    s = 1.0 if correct else 0.0
    k_u = 48 if user_plays < 30 else 32
    k_q = max(8.0, 32 / math.sqrt(1 + question_plays / 10))
    return r_user + k_u * (s - p), r_question - k_q * (s - p)
