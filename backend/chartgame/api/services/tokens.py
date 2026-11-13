"""서명된 play 토큰. 클라이언트는 문제 ID를 모른 채 이 토큰으로만 답을 낸다."""
from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ... import config

_s = URLSafeTimedSerializer(config.SECRET, salt="play")


def make(play_id: int) -> str:
    return _s.dumps({"p": play_id})


def read(token: str, max_age: int = config.TOKEN_MAX_AGE) -> int | None:
    try:
        return int(_s.loads(token, max_age=max_age)["p"])
    except (BadSignature, SignatureExpired, KeyError, ValueError, TypeError):
        return None
