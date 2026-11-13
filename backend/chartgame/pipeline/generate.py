"""문제 생성: 정제 → 시총 구간 → 구간 추출 → 오답 → 문제 레코드(Parquet)."""
from __future__ import annotations

import json
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

from .. import config
from ..sources.listing import load_stocks
from . import clean, decoys, marcap, windows

_CTX: dict = {}


def _ma(c: np.ndarray, n: int) -> np.ndarray:
    cs = np.concatenate([[0], np.cumsum(c)])
    out = np.full(len(c), np.nan)
    out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def _r(a, nd=5):
    return [round(float(x), nd) for x in a]


def to_record(s: clean.Series, w, q: dict, stock) -> dict:
    """내부 계산 결과 → 저장용 레코드. 가격은 빈칸 직전 종가(c0)로 나눈 상대값."""
    st, L, G, R = int(w.start), int(w.L), int(w.G), int(w.R)
    N = L + G + R
    gs, ge, c0 = st + L, st + L + G, q["c0"]
    idx = np.r_[st:gs, ge:st + N]
    candles = [_r(row) for row in np.stack([s.o[idx], s.h[idx], s.l[idx], s.c[idx]], axis=1) / c0]
    options = [[_r(row) for row in np.stack(o, axis=1) / c0] for o in q["options"]]
    vmed = float(np.median(s.v[idx])) or 1.0
    hard = w.difficulty == "hard"
    payload = {
        "layout": {"L": L, "G": G, "R": R},
        "candles": candles,
        "options": options,
        "volume": None if hard else _r(s.v[idx] / vmed, 3),
        "option_volume": None if hard else [_r(v / vmed, 3) for v in q["volumes"]],
        "ma": None,
    }
    if w.difficulty == "easy":
        lo = max(st - 25, 0)
        ma = {}
        for n in (5, 20):
            m = _ma(s.c[lo:st + N], n)[st - lo:] / c0
            m = m[np.r_[0:L, L + G:N]]
            ma[str(n)] = [None if np.isnan(x) else round(float(x), 5) for x in m]
        payload["ma"] = ma
    real = q["options"][0]
    reveal = {
        "name": stock.name, "code": s.code, "market": s.market,
        "start_date": w.start_date, "gap_start": w.gap_start, "gap_end": w.gap_end, "end_date": w.end_date,
        "cap_tier_then": w.cap_tier,
        "gap_return_pct": round((real[3][-1] / c0 - 1) * 100, 2),
        "gap_max_pct": round((real[1].max() / c0 - 1) * 100, 2),
        "gap_min_pct": round((real[2].min() / c0 - 1) * 100, 2),
        "delisted": ({"date": str(pd.Timestamp(stock.delisted_date).date()), "reason": stock.delist_reason}
                     if stock.is_delisted else None),
        "decoy_sources": q["sources"],
    }
    return {
        "code": s.code, "interval": s.interval, "region": int(w.region),
        "start_date": w.start_date, "end_date": w.end_date, "gap_start": w.gap_start, "gap_end": w.gap_end,
        "market": s.market, "cap_tier": w.cap_tier, "sector": w.sector, "era": w.era,
        "difficulty": w.difficulty, "p_score": round(float(w.P), 4),
        "payload": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        "reveal": json.dumps(reveal, ensure_ascii=False, separators=(",", ":")),
    }


def _work(rows: list) -> tuple[list[dict], int]:
    series, idx, stocks = _CTX["series"], _CTX["index"], _CTX["stocks"]
    out, fail = [], 0
    for w in rows:
        s = series[w.code]
        rng = np.random.default_rng(windows.seed_for(w.code, s.interval, w.region, "decoy"))
        q = decoys.make_question(s, int(w.start), int(w.L), int(w.G), int(w.R), w.difficulty, idx[int(w.G)],
                                 w.sector if isinstance(w.sector, str) else None, rng, float(w.sigma_c))
        if q is None:
            fail += 1
            continue
        out.append(to_record(s, w, q, stocks[w.code]))
    return out, fail


def prepare(interval: str, limit: int | None = None):
    """정제된 시리즈(시총 구간 포함)와 종목 표."""
    stocks = load_stocks()
    weekly = clean.load_all("week", stocks, limit)
    rank = marcap.build_ranks(weekly, stocks)
    series = weekly if interval == "week" else clean.load_all("day", stocks, limit)
    marcap.attach_tiers(series, rank)
    return series, stocks


def run(interval: str, limit: int | None = None, workers: int = 4, max_questions: int | None = None) -> pd.DataFrame:
    t0 = time.time()
    series, stocks = prepare(interval, limit)
    print(f"[{interval}] 종목 {len(series)}  ({time.time() - t0:.0f}s)", flush=True)
    win, calib = windows.extract(series, stocks, interval, workers)
    windows.save(win, calib, interval)
    print(f"[{interval}] 구간 {len(win)}  난이도 {win.difficulty.value_counts().to_dict()}  ({time.time() - t0:.0f}s)", flush=True)
    if max_questions:
        win = win.sample(min(max_questions, len(win)), random_state=0)
    sectors = {r.code: r.sector for r in stocks.itertuples() if isinstance(r.sector, str)}
    stride = 2 if interval == "day" else 1
    _CTX["series"] = series
    _CTX["index"] = {G: decoys.SegIndex(series, G, stride, sectors) for _, G, _ in config.LAYOUTS[interval].values()}
    _CTX["stocks"] = {r.code: r for r in stocks.itertuples()}
    print(f"[{interval}] 출처 색인 {[(G, ix.n) for G, ix in _CTX['index'].items()]}  ({time.time() - t0:.0f}s)", flush=True)
    rows = list(win.itertuples())
    chunks = [rows[i:i + 200] for i in range(0, len(rows), 200)]
    if workers > 1 and len(chunks) > 1:
        with Pool(workers) as pool:
            res = pool.map(_work, chunks)
    else:
        res = [_work(ch) for ch in chunks]
    recs = [r for out, _ in res for r in out]
    fails = sum(f for _, f in res)
    df = pd.DataFrame(recs)
    df.to_parquet(config.WORK / f"questions_{interval}.parquet", index=False)
    print(f"[{interval}] 문제 {len(df)}  오답 생성 실패 {fails}  ({time.time() - t0:.0f}s)", flush=True)
    return df
