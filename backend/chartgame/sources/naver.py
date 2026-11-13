"""네이버 차트 API (fchart) 수집기. 인증 불필요, 수정주가, 종목당 최근 3000봉."""
from __future__ import annotations

import re
import threading
import time

import pandas as pd
import requests

from .. import config

_ITEM = re.compile(r'<item data="(\d{8})\|([^|"]*)\|([^|"]*)\|([^|"]*)\|([^|"]*)\|([^|"]*)"')
_COLS = ["date", "open", "high", "low", "close", "volume"]
_lock = threading.Lock()
_last = [0.0]


def parse_xml(text: str) -> pd.DataFrame:
    rows = _ITEM.findall(text)
    df = pd.DataFrame(rows, columns=_COLS)
    if df.empty:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in _COLS}).astype({"date": "datetime64[ns]"})
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
    for c in _COLS[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date", "close"]).drop_duplicates("date", keep="last").sort_values("date")
    return df.reset_index(drop=True)


def _throttle() -> None:
    with _lock:
        wait = config.NAVER_MIN_INTERVAL - (time.monotonic() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()


def fetch(code: str, interval: str, count: int = config.NAVER_COUNT,
          session: requests.Session | None = None, retries: int = 4) -> pd.DataFrame:
    """interval: 'day' | 'week' | 'month'. 실패하면 예외."""
    s = session or requests
    params = {"symbol": code, "timeframe": interval, "count": count, "requestType": 0}
    err: Exception | None = None
    for i in range(retries):
        _throttle()
        try:
            r = s.get(config.NAVER_URL, params=params, timeout=20)
            if r.status_code == 200 and "<chartdata" in r.text:
                return parse_xml(r.text)
            err = RuntimeError(f"HTTP {r.status_code}")
        except requests.RequestException as e:  # noqa: PERF203
            err = e
        time.sleep(2**i)
    raise RuntimeError(f"naver fetch failed: {code} {interval}: {err}")
