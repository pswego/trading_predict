"""시점별 시총 구간. 시총(t) ≈ 수정종가(t) × 상장주식수 로 근사하고 당시 순위로 구간을 정한다."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config
from .clean import Series

TIER_NAMES = [t for t, _ in config.CAP_TIERS]


def build_ranks(weekly: dict[str, Series], stocks: pd.DataFrame) -> pd.DataFrame:
    """월별 × 종목 시총 순위 표 (index: 'YYYY-MM' 문자열, columns: code)."""
    shares = stocks.set_index("code")["shares"]
    cols = {}
    for code, s in weekly.items():
        sh = shares.get(code)
        if not sh or np.isnan(sh):
            continue
        ser = pd.Series(s.c * sh, index=pd.to_datetime(s.date))
        cols[code] = ser.groupby(ser.index.to_period("M")).last()
    cap = pd.DataFrame(cols).sort_index()
    cap = cap.ffill(limit=2)  # 거래정지로 한두 달 비는 경우
    rank = cap.rank(axis=1, ascending=False, method="first")
    rank.index = rank.index.astype(str)
    return rank


def rank_to_tier(rank: np.ndarray) -> np.ndarray:
    """순위 → 구간 인덱스. NaN은 -1."""
    out = np.full(rank.shape, -1, dtype=np.int8)
    bounds = [b for _, b in config.CAP_TIERS]
    ok = ~np.isnan(rank)
    out[ok] = np.searchsorted(bounds, rank[ok], side="left").astype(np.int8)
    return out


def attach_tiers(series: dict[str, Series], rank: pd.DataFrame) -> None:
    """각 시리즈의 봉마다 당시 시총 구간을 붙인다 (전월 말 순위 기준, 없으면 가장 가까운 값)."""
    months = pd.PeriodIndex(rank.index, freq="M")
    for code, s in series.items():
        if code not in rank.columns:
            s.tier = np.full(len(s), -1, dtype=np.int8)
            continue
        col = rank[code].to_numpy()
        tiers = pd.Series(rank_to_tier(col), index=months).replace(-1, np.nan).ffill().bfill()
        bar_m = pd.to_datetime(s.date).to_period("M")
        t = tiers.reindex(bar_m).to_numpy()
        s.tier = np.nan_to_num(t, nan=-1).astype(np.int8)
