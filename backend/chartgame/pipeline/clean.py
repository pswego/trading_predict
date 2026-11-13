"""정제: Parquet → 메모리 시리즈. 봉마다 '문제에 쓰면 안 됨' 표시를 만든다."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import config
from ..core.limits import price_limit


@dataclass
class Series:
    code: str
    market: str
    interval: str
    date: np.ndarray  # datetime64[D]
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray  # noqa: E741
    c: np.ndarray
    v: np.ndarray
    notrade: np.ndarray  # 거래 없음(가격 0 또는 거래량 0)
    flat: np.ndarray  # 종가 변동 없음
    bad: np.ndarray  # 윈도우에 들어가면 안 되는 봉
    limit: np.ndarray  # 일봉 가격제한폭 (주봉은 inf)
    tier: np.ndarray = field(default=None)  # 당시 시총 구간 인덱스 (marcap에서 채움)
    # 직전 종가 기준 로그 상대값 (오답 변환용). 첫 봉은 0
    r: np.ndarray = field(default=None)
    ro: np.ndarray = field(default=None)
    rh: np.ndarray = field(default=None)
    rl: np.ndarray = field(default=None)
    # 누적합 (구간 검사용)
    cs_bad: np.ndarray = field(default=None)
    cs_notrade: np.ndarray = field(default=None)
    cs_flat: np.ndarray = field(default=None)

    def __len__(self) -> int:
        return len(self.c)

    def slice_ok(self, s: int, e: int) -> bool:
        """[s, e) 구간이 품질 필터를 통과하는지."""
        n = e - s
        if s < 1 or e > len(self.c):  # s>=1: 첫 봉의 직전 종가가 필요
            return False
        if self.cs_bad[e] - self.cs_bad[s] > 0:
            return False
        if (self.cs_notrade[e] - self.cs_notrade[s]) / n > config.MAX_NOTRADE_FRAC:
            return False
        if (self.cs_flat[e] - self.cs_flat[s]) / n > config.MAX_FLAT_FRAC:
            return False
        turnover = np.median(self.c[s:e] * self.v[s:e])
        return turnover >= config.MIN_MEDIAN_TURNOVER[self.interval]


def clean_frame(df: pd.DataFrame, code: str, market: str, interval: str,
                is_delisted: bool = False) -> Series | None:
    df = df[(df["date"] >= config.DATA_START) & (df["close"] > 0)].reset_index(drop=True)
    if len(df) < 30:
        return None
    capped = len(df) >= config.NAVER_COUNT - 5  # 3000봉 상한에 걸리면 첫 봉은 상장일이 아니다
    date = df["date"].to_numpy().astype("datetime64[D]")
    o, h, l, c, v = (df[k].to_numpy(dtype="float64").copy() for k in ("open", "high", "low", "close", "volume"))  # noqa: E741
    v = np.nan_to_num(v)
    notrade = ~(o > 0) | ~(h > 0) | ~(l > 0) | (v <= 0)
    o[notrade], h[notrade], l[notrade] = c[notrade], c[notrade], c[notrade]

    bad = (h < np.maximum(o, c) - 1e-9) | (l > np.minimum(o, c) + 1e-9)
    prev = np.concatenate([[c[0]], c[:-1]])
    ret = c / prev - 1
    if interval == "day":
        limit = price_limit(market, date)
        over = (np.abs(ret) > limit + config.LIMIT_TOLERANCE) | (h / prev - 1 > limit + config.LIMIT_TOLERANCE) \
            | (1 - l / prev > limit + config.LIMIT_TOLERANCE)
        over[0] = False
        bad |= over
    else:
        limit = np.full(len(c), np.inf)
    gap = np.concatenate([[0], np.diff(date).astype(int)])
    bad |= gap > config.MAX_CAL_GAP_DAYS[interval]
    bad |= c < config.MIN_CLOSE
    if not capped:
        bad[: config.SKIP_AFTER_LISTING[interval]] = True
    if is_delisted:
        bad[-config.SKIP_BEFORE_DELISTING[interval]:] = True
    flat = ret == 0
    flat[0] = False

    lc = np.log(c)
    lp = np.log(prev)
    s = Series(code, market, interval, date, o, h, l, c, v, notrade, flat, bad, limit)
    s.r, s.ro, s.rh, s.rl = lc - lp, np.log(o) - lp, np.log(h) - lp, np.log(l) - lp
    for name, arr in (("cs_bad", bad), ("cs_notrade", notrade), ("cs_flat", flat)):
        setattr(s, name, np.concatenate([[0], np.cumsum(arr)]))
    return s


def load_all(interval: str, stocks: pd.DataFrame | None = None, limit: int | None = None) -> dict[str, Series]:
    from ..sources.listing import load_stocks

    stocks = load_stocks() if stocks is None else stocks
    out: dict[str, Series] = {}
    for row in stocks.itertuples():
        path = config.PRICES / interval / f"{row.code}.parquet"
        if not path.exists():
            continue
        s = clean_frame(pd.read_parquet(path), row.code, row.market, interval, bool(row.is_delisted))
        if s is not None:
            out[row.code] = s
        if limit and len(out) >= limit:
            break
    return out
