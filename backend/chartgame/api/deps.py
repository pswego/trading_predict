from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, Response

from ..db.models import User
from ..db.session import make_session

COOKIE = "cg_uid"
RATE_LIMIT = int(os.environ.get("CHARTGAME_RATE_LIMIT", "240"))  # 사용자당 분당 요청 수, 0이면 끔
_hits: dict[str, deque] = defaultdict(deque)


def get_db():
    db = make_session()
    try:
        yield db
    finally:
        db.close()


def get_user(request: Request, response: Response, db=Depends(get_db)) -> User:
    uid = request.cookies.get(COOKIE)
    user = db.get(User, uid) if uid else None
    if user is None:
        user = User()
        db.add(user)
        db.commit()
        response.set_cookie(COOKIE, user.id, max_age=3 * 365 * 86400, httponly=True, samesite="lax")
    if RATE_LIMIT:
        q, t = _hits[user.id], time.monotonic()
        while q and t - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            raise HTTPException(429, "요청이 너무 많아요. 잠시 후 다시 시도해 주세요.")
        q.append(t)
    return user
