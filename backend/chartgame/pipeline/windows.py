"""구간 추출: 종목별로 겹치지 않는 영역을 자르고, 영역마다 문제 후보를 만들어 난이도를 정한다."""
from __future__ import annotations

import json
import math
import zlib
from multiprocessing import Pool

import numpy as np
import pandas as pd

from .. import config
from . import features as F
from .clean import Series
from .marcap import TIER_NAMES

MIN_SIDE = {"day": 10, "week": 8}
TRIES = 3
_SERIES: dict[str, Series] = {}


def seed_for(*parts) -> int:
    return zlib.crc32("|".join(map(str, parts)).encode())


def l_range(N: int, G: int, min_side: int) -> tuple[int, int]:
    """빈칸 중심이 윈도우의 30~70% 지점에 오는 L의 범위."""
    lo = max(math.ceil(0.3 * N - G / 2), min_side)
    hi = min(math.floor(0.7 * N - G / 2), N - G - min_side)
    return lo, hi


def era_of(date) -> str:
    y = pd.Timestamp(date).year
    return "2000s" if y < 2010 else ("2010s" if y < 2020 else "2020s")


def _candidates(code: str) -> list[dict]:
    s = _SERIES[code]
    iv = s.interval
    RL = config.REGION_LEN[iv]
    out = []
    for ri, rs in enumerate(range(1, len(s) - RL + 1, RL)):
        rng = np.random.default_rng(seed_for(code, iv, ri))
        for diff, (L0, G, R0) in config.LAYOUTS[iv].items():
            N = L0 + G + R0
            lo, hi = l_range(N, G, MIN_SIDE[iv])
            for _ in range(TRIES):
                st = rs + int(rng.integers(0, RL - N + 1))
                L = int(rng.integers(lo, hi + 1))
                if not s.slice_ok(st, st + N):
                    continue
                tier = int(s.tier[st + L]) if s.tier is not None else -1
                if tier < 0:
                    continue
                e = st + N
                f = F.window_features(s.o[st:e], s.h[st:e], s.l[st:e], s.c[st:e], s.v[st:e], L, G)
                if f is None:
                    continue
                out.append({"code": code, "interval": iv, "region": ri, "start": st, "L": L, "G": G,
                            "R": N - G - L, "layout": diff, "tier": tier, **f})
    return out


def collect_candidates(series: dict[str, Series], workers: int = 4) -> pd.DataFrame:
    global _SERIES
    _SERIES = series
    codes = list(series)
    if workers > 1 and len(codes) > 50:
        with Pool(workers) as pool:  # fork: _SERIES를 그대로 공유
            chunks = pool.map(_candidates, codes, chunksize=20)
    else:
        chunks = [_candidates(c) for c in codes]
    return pd.DataFrame([row for ch in chunks for row in ch])


def calibrate(cand: pd.DataFrame) -> dict:
    """특징 표준화 값과 난이도 경계(P 분위수)를 계산."""
    stats = F.robust_stats(cand)
    p = F.p_score(cand, stats)
    q = config.DIFFICULTY_QUOTA
    hard_max = float(np.quantile(p, q["hard"]))
    easy_min = float(np.quantile(p, 1 - q["easy"]))
    return {"stats": {k: list(v) for k, v in stats.items()}, "hard_max": hard_max, "easy_min": easy_min}


def zone_of(p: np.ndarray, calib: dict) -> np.ndarray:
    return np.where(p >= calib["easy_min"], "easy", np.where(p < calib["hard_max"], "hard", "normal"))


def select(cand: pd.DataFrame, calib: dict, interval: str) -> pd.DataFrame:
    """영역마다 문제 1개. 후보의 P 구간이 그 레이아웃의 난이도와 맞아야 채택된다."""
    stats = {k: tuple(v) for k, v in calib["stats"].items()}
    cand = cand.assign(P=F.p_score(cand, stats))
    cand = cand[zone_of(cand["P"].to_numpy(), calib) == cand["layout"]]
    counts = {d: 0 for d in config.DIFFICULTIES}
    total = 0
    picked = []
    groups = {k: g for k, g in cand.groupby(["code", "region"], sort=False)}
    keys = sorted(groups, key=lambda k: seed_for("order", *k))
    for key in keys:
        g = groups[key]
        avail = set(g["layout"])
        diff = max(avail, key=lambda d: config.DIFFICULTY_QUOTA[d] - (counts[d] / total if total else 0))
        picked.append(g[g["layout"] == diff].index[0])
        counts[diff] += 1
        total += 1
    out = cand.loc[picked].rename(columns={"layout": "difficulty"}).reset_index(drop=True)
    return out


def annotate(win: pd.DataFrame, series: dict[str, Series], stocks: pd.DataFrame) -> pd.DataFrame:
    meta = stocks.set_index("code")
    rows = []
    for w in win.itertuples():
        s = series[w.code]
        N = w.L + w.G + w.R
        rows.append({
            "start_date": str(s.date[w.start]), "end_date": str(s.date[w.start + N - 1]),
            "gap_start": str(s.date[w.start + w.L]), "gap_end": str(s.date[w.start + w.L + w.G - 1]),
            "market": s.market, "cap_tier": TIER_NAMES[w.tier], "sector": meta.at[w.code, "sector"],
            "era": era_of(s.date[w.start + w.L]),
        })
    return pd.concat([win, pd.DataFrame(rows)], axis=1)


def extract(series: dict[str, Series], stocks: pd.DataFrame, interval: str, workers: int = 4,
            calib: dict | None = None) -> tuple[pd.DataFrame, dict]:
    cand = collect_candidates(series, workers)
    if cand.empty:
        return cand, calib or {}
    calib = calib or calibrate(cand)
    win = annotate(select(cand, calib, interval), series, stocks)
    return win, calib


def save(win: pd.DataFrame, calib: dict, interval: str) -> None:
    config.ensure_dirs()
    win.to_parquet(config.WORK / f"windows_{interval}.parquet", index=False)
    (config.WORK / f"calib_{interval}.json").write_text(json.dumps(calib, indent=1))
