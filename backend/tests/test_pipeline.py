import json

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chartgame import config
from chartgame.pipeline import clean, decoys, windows
from chartgame.pipeline import features as F

from .conftest import synth_frame


def _window(c_gap_fn, L=30, G=18, R=30, vol=0.01, seed=0):
    """맥락은 잔잔한 랜덤워크, 빈칸 종가는 c_gap_fn(t)로 만든 합성 윈도우."""
    rng = np.random.default_rng(seed)
    left = 100 * np.exp(np.cumsum(rng.normal(0.002, vol, L)))
    gap = left[-1] * np.exp(c_gap_fn(np.arange(1, G + 1) / G) + rng.normal(0, vol / 4, G))
    right = gap[-1] * np.exp(np.cumsum(rng.normal(0.002, vol, R)))
    c = np.concatenate([left, gap, right])
    o = np.concatenate([[c[0]], c[:-1]])
    return o, np.maximum(o, c) * 1.002, np.minimum(o, c) * 0.998, c, np.full(len(c), 1000.0)


def test_surprise_separates_straight_trend_from_hidden_spike():
    straight = F.window_features(*_window(lambda t: 0.036 * t), 30, 18)
    spike = F.window_features(*_window(lambda t: 0.4 * np.sin(np.pi * t)), 30, 18)  # 빈칸 안에서 급등 후 원위치
    assert straight["S"] < 1.0 < spike["S"]
    assert straight["E"] > spike["E"]
    assert straight["T"] > spike["T"]


def test_p_score_orders_easy_above_hard():
    import pandas as pd

    rows = [F.window_features(*_window(lambda t: 0.036 * t, seed=s), 30, 18) for s in range(20)]
    rows += [F.window_features(*_window(lambda t: 0.4 * np.sin(np.pi * t), seed=s), 30, 18) for s in range(20)]
    df = pd.DataFrame(rows)
    p = F.p_score(df, F.robust_stats(df))
    assert p[:20].mean() > p[20:].mean() + 0.3


@pytest.mark.parametrize("interval", ["day", "week"])
def test_gap_center_stays_in_middle(interval):
    for L0, G, R0 in config.LAYOUTS[interval].values():
        N = L0 + G + R0
        lo, hi = windows.l_range(N, G, windows.MIN_SIDE[interval])
        assert lo <= hi
        for L in (lo, hi):
            assert 0.3 * N - 1 <= L + G / 2 <= 0.7 * N + 1
            assert min(L, N - G - L) >= windows.MIN_SIDE[interval]


def test_windows_do_not_overlap_and_cover_all_difficulties(synth_series, synth_stocks):
    win, calib = windows.extract(synth_series, synth_stocks, "day", workers=1)
    assert set(win.difficulty) == set(config.DIFFICULTIES)
    assert calib["hard_max"] < calib["easy_min"]
    for _, g in win.groupby("code"):
        spans = sorted(zip(g.start, g.start + g.L + g.G + g.R, strict=True))
        assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:], strict=False))
    assert win.groupby(["code", "region"]).size().max() == 1
    share = win.difficulty.value_counts(normalize=True)
    for d, q in config.DIFFICULTY_QUOTA.items():
        assert abs(share[d] - q) < 0.15


def test_extraction_is_deterministic(synth_series, synth_stocks):
    a, _ = windows.extract(synth_series, synth_stocks, "day", workers=1)
    b, _ = windows.extract(synth_series, synth_stocks, "day", workers=1)
    assert a.equals(b)


def _check_question(rec):
    p = json.loads(rec.payload)
    L, G, R = p["layout"]["L"], p["layout"]["G"], p["layout"]["R"]
    assert len(p["candles"]) == L + R and len(p["options"]) == 4
    assert abs(p["candles"][L - 1][3] - 1.0) < 1e-9  # 빈칸 직전 종가가 기준(=1)
    end = p["options"][0][-1][3]
    paths = []
    for opt in p["options"]:
        a = np.array(opt)
        assert a.shape == (G, 4) and (a > 0).all()
        assert abs(a[-1, 3] - end) < 1e-9  # 모든 보기의 끝점이 같다
        assert (a[:, 2] <= np.minimum(a[:, 0], a[:, 3]) + 1e-9).all() and (a[:, 1] >= np.maximum(a[:, 0], a[:, 3]) - 1e-9).all()
        prev = np.concatenate([[1.0], a[:-1, 3]])
        assert (np.abs(a[:, 3] / prev - 1) <= 0.30 + 1e-4).all()  # 가격제한폭
        paths.append(tuple(a[:, 3]))
    assert len(set(paths)) == 4  # 보기끼리 서로 다르다
    if rec.difficulty == "hard":
        assert p["volume"] is None and p["option_volume"] is None
    else:
        assert len(p["volume"]) == L + R and len(p["option_volume"]) == 4
    assert (p["ma"] is not None) == (rec.difficulty == "easy")


def test_generated_questions_hold_invariants(synth_questions):
    assert len(synth_questions) > 100
    for rec in synth_questions.itertuples():
        _check_question(rec)
    rv = json.loads(synth_questions.iloc[0].reveal)
    assert {"name", "code", "gap_start", "gap_return_pct", "decoy_sources"} <= set(rv)
    assert len(rv["decoy_sources"]) == 3


def test_reveal_marks_delisted(synth_questions):
    rv = [json.loads(r) for r in synth_questions[synth_questions.code == "000070"].reveal]
    assert rv and all(r["delisted"]["reason"] == "감사의견 거절" for r in rv)


def test_mirror_keeps_endpoints_and_order():
    df = synth_frame(5, 60)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))  # noqa: E741
    c0 = 20000.0
    O, H, L, C = decoys.mirror(o, h, l, c, c0)
    assert np.isclose(C[-1], c[-1])
    assert (H >= np.maximum(O, C) - 1e-6).all() and (L <= np.minimum(O, C) + 1e-6).all()
    mid = len(c) // 2
    b = np.log(c0) + (np.log(c[-1]) - np.log(c0)) * (mid + 1) / len(c)
    assert np.isclose(np.log(C[mid]) - b, -(np.log(c[mid]) - b))  # 직선 기준 상하 반전


@settings(max_examples=150, deadline=None)
@given(seed=st.integers(0, 10_000), G=st.sampled_from([8, 10, 12, 18, 28]), k=st.floats(0.5, 1.8),
       ret=st.floats(-0.3, 0.3), start=st.integers(1, 200), grid=st.sampled_from([0.0, 1.0, 5.0, 50.0]))
def test_transform_property(seed, G, k, ret, start, grid):
    """어떤 출처 구간이든 변환하면 끝점이 정확히 맞고 봉 모양이 유효하다."""
    s = clean.clean_frame(synth_frame(seed, 260), "000010", "KOSPI", "day")
    c0 = 15000.0
    c_end = c0 * np.exp(ret)
    O, H, L, C, d = decoys.transform(s, start, G, k, ret, c0)
    assert np.isclose(C[-1], c_end, rtol=1e-9)
    assert np.isclose(d, (ret - k * s.r[start:start + G].sum()) / G)
    O, H, L, C = decoys.snap(O, H, L, C, grid, c_end)
    assert decoys.validate_option(O, H, L, C, c0, c_end, None, grid) is None
    if grid:
        assert np.allclose(O / grid, np.round(O / grid)) and np.allclose(C[:-1] / grid, np.round(C[:-1] / grid))


def test_validate_option_catches_violations():
    c0, G = 100.0, 5
    C = np.array([101, 102, 103, 104, 105.0])
    O = np.array([100, 101, 102, 103, 104.0])
    H, L = C + 0.5, O - 0.5
    ok = lambda **kw: decoys.validate_option(kw.get("O", O), kw.get("H", H), kw.get("L", L), kw.get("C", C), c0, kw.get("end", 105.0), kw.get("limit"), 0.0)  # noqa: E731
    assert ok() is None
    assert ok(end=106.0) == "endpoint"
    assert ok(H=C - 1) == "ohlc_order"
    assert ok(limit=np.full(G, 0.005)) == "price_limit"
    assert ok(L=np.array([-1, 100, 101, 102, 103.0])) == "nonpositive"


def test_segment_index_pools(synth_series, synth_stocks):
    sectors = dict(zip(synth_stocks.code, synth_stocks.sector, strict=True))
    idx = decoys.SegIndex(synth_series, 18, 1, sectors)
    rng = np.random.default_rng(0)
    code = next(iter(synth_series))
    same = idx.sample("same", rng, code, "KOSDAQ", 0, None)
    assert len(same) and {idx.codes[i] for i in idx.ci[same]} == {code}
    tier = idx.sample("tier", rng, code, "KOSPI", 1, None)
    assert (idx.tier[tier] == 1).all() and (idx.mkt[tier] == 0).all()
    sec = idx.sample("sector", rng, code, "KOSPI", 1, "업종1")
    assert {sectors[idx.codes[i]] for i in idx.ci[sec]} == {"업종1"}
