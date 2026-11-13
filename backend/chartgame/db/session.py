from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .. import config
from .models import Base

_engines: dict[str, object] = {}


def get_engine(url: str | None = None):
    url = url or config.DB_URL
    if url not in _engines:
        kw = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        eng = create_engine(url, **kw)
        if url.startswith("sqlite"):
            @event.listens_for(eng, "connect")
            def _pragma(conn, _):  # noqa: ANN001
                cur = conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.close()
        Base.metadata.create_all(eng)
        _engines[url] = eng
    return _engines[url]


def make_session(url: str | None = None):
    return sessionmaker(get_engine(url), expire_on_commit=False)()
