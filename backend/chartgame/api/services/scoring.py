from __future__ import annotations

from ... import config


def score(correct: bool, difficulty: str, game_type: str, elapsed_ms: int, streak_before: int) -> int:
    """정답 점수. streak_before: 이 문제를 풀기 전의 연속 정답 수."""
    if not correct:
        return 0
    limit = config.TIME_LIMIT_MS[game_type][difficulty]
    base = 100 * config.SCORE_MULT[difficulty]
    bonus = base * 0.5 * max(0.0, 1 - elapsed_ms / limit)
    combo = min(1 + 0.1 * streak_before, 2.0)
    total = (base + bonus) * combo
    return round(total * (0.5 if game_type == "ox" else 1.0))
