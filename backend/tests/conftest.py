from __future__ import annotations

import os

os.environ["CHARTGAME_RATE_LIMIT"] = "0"

import numpy as np
import pandas as pd
import pytest

from chartgame import config
from chartgame.pipeline import clean, decoys, generate, windows


def synth_frame(seed: int, n: int = 700, start: str = "2016-01-04", vol: float = 0.025, price: float = 20000.0) -> pd.DataFrame:
    """그럴듯한 가짜 일봉. 정수 가격, 제한폭 안."""
    rng = np.random.default_rng(seed)
    r = np.clip(rng.standard_t(4, n) * vol * 0.7, -0.25, 0.25)
    c = price * np.exp(np.cumsum(r))
    prev = np.concatenate([[price], c[:-1]])
    o = prev * np.exp(rng.normal(0, vol * 0.3, n))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, vol * 0.4, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, vol * 0.4, n)))  # noqa: E741
    h = np.minimum(h, prev * 1.29)
    l = np.maximum(l, prev * 0.71)  # noqa: E741
    o, h, l, c = (np.round(a / 10) * 10 for a in (o, h, l, c))  # noqa: E741
    h, l = np.maximum(h, np.maximum(o, c)), np.minimum(l, np.minimum(o, c))  # noqa: E741
    v = np.round(rng.lognormal(12, 0.6, n) * (1 + 20 * np.abs(r)))
    return pd.DataFrame({"date": pd.bdate_range(start, periods=n), "open": o, "high": h, "low": l, "close": c, "volume": v})


@pytest.fixture(scope="session")
def synth_series() -> dict[str, clean.Series]:
    out = {}
    for i in range(36):
        code = f"{i:05d}0"
        s = clean.clean_frame(synth_frame(i, vol=0.018 + 0.004 * (i % 5)), code, "KOSPI" if i % 2 else "KOSDAQ", "day")
        s.tier = np.full(len(s), i % 4, dtype=np.int8)
        out[code] = s
    return out


@pytest.fixture(scope="session")
def synth_stocks(synth_series) -> pd.DataFrame:
    return pd.DataFrame([{
        "code": c, "name": f"테스트{c}", "market": s.market, "sector": f"업종{int(c[:5]) % 3}",
        "listed_date": pd.NaT, "delisted_date": pd.Timestamp("2020-01-02") if int(c[:5]) == 7 else pd.NaT,
        "delist_reason": "감사의견 거절" if int(c[:5]) == 7 else None, "shares": 1e7, "is_delisted": int(c[:5]) == 7,
    } for c, s in synth_series.items()])


@pytest.fixture(scope="session")
def synth_questions(synth_series, synth_stocks) -> pd.DataFrame:
    win, _ = windows.extract(synth_series, synth_stocks, "day", workers=1)
    sectors = dict(zip(synth_stocks.code, synth_stocks.sector, strict=True))
    generate._CTX["series"] = synth_series
    generate._CTX["index"] = {G: decoys.SegIndex(synth_series, G, 1, sectors) for _, G, _ in config.LAYOUTS["day"].values()}
    generate._CTX["stocks"] = {r.code: r for r in synth_stocks.itertuples()}
    recs, _ = generate._work(list(win.itertuples()))
    return pd.DataFrame(recs)


@pytest.fixture()
def db_url(tmp_path, monkeypatch, synth_questions):
    from chartgame.db.session import make_session
    from chartgame.pipeline import build

    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(config, "DB_URL", url)
    db = make_session(url)
    build.load_questions(synth_questions, db)
    db.close()
    return url


@pytest.fixture()
def client(db_url):
    from fastapi.testclient import TestClient

    from chartgame.api.main import app

    with TestClient(app) as c:
        yield c
