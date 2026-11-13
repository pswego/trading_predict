"""구간 특징량: 맥락을 보고 빈칸을 얼마나 추측할 수 있는지를 수치화한다."""
from __future__ import annotations

import numpy as np

FEATURES = ("S", "T", "E", "V", "K", "B")
# P = sigmoid(Σ w·z(feature) + bias). z는 데이터 전체 기준 강건 표준화
WEIGHTS = {"T": 1.2, "E": 1.0, "K": 0.8, "B": 0.5, "S": -1.0, "V": -0.8}


def _slope(x: np.ndarray) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    t = np.arange(n) - (n - 1) / 2
    return float((t * (x - x.mean())).sum() / (t * t).sum())


def bridge(x0: float, x1: float, G: int) -> np.ndarray:
    """빈칸 직전 종가 x0에서 빈칸 마지막 종가 x1까지 직선. 길이 G (마지막 값 = x1)."""
    return x0 + (x1 - x0) * np.arange(1, G + 1) / G


def surprise(xg: np.ndarray, x0: float, sigma: float) -> float:
    """S: 빈칸 경로가 직선 예상에서 가장 멀리 벗어난 정도 (σ·√G 단위)."""
    G = len(xg)
    return float(np.abs(xg - bridge(x0, xg[-1], G)).max() / (sigma * np.sqrt(G) + 1e-12))


def window_features(o, h, l, c, v, L: int, G: int) -> dict[str, float] | None:  # noqa: E741
    """o..v: 윈도우 전체(길이 L+G+R). 빈칸은 [L, L+G)."""
    x = np.log(c)
    r = np.diff(x)
    ctx_r = np.concatenate([r[: L - 1], r[L + G:]])  # 맥락 안에서만 계산한 수익률
    gap_r = r[L - 1: L + G - 1]  # 빈칸 봉들의 수익률 (직전 종가 대비)
    sc = float(ctx_r.std())
    sg = float(gap_r.std())
    if sc <= 1e-6 or sg <= 1e-6:
        return None
    xg = x[L: L + G]
    x0 = x[L - 1]
    S = surprise(xg, x0, sc)
    sl, sr, sgp = _slope(x[:L]), _slope(x[L + G:]), _slope(x[L - 1: L + G])
    T = 1.0 - min(abs(sgp - (sl + sr) / 2) * np.sqrt(G) / (2 * sc), 1.0)
    E = float(abs(xg[-1] - x0) / (np.abs(gap_r).sum() + 1e-12))
    V = float(abs(np.log(sg / sc)))
    # 경계 단서: 보이는 쪽 경계 2봉의 큰 움직임 / 거래량 급증
    edge_r = np.abs(np.concatenate([r[max(L - 3, 0): L - 1], r[L + G - 1: L + G + 1]])) / sc
    ctx_v = np.concatenate([v[:L], v[L + G:]])
    edge_v = np.concatenate([v[L - 2: L], v[L + G: L + G + 2]])
    vz = (edge_v.max() - ctx_v.mean()) / (ctx_v.std() + 1e-12)
    K = float(np.clip(max(edge_r.max() / 3.0, vz / 4.0), 0.0, 1.0))
    rng = h[L: L + G] - l[L: L + G]
    body = np.abs(c[L: L + G] - o[L: L + G])
    B = float(np.where(rng > 0, body / np.where(rng > 0, rng, 1), 0).mean())
    return {"S": S, "T": T, "E": E, "V": V, "K": K, "B": B,
            "sigma_c": sc, "sigma_g": sg, "ret": float(xg[-1] - x0)}


def robust_stats(frame) -> dict[str, tuple[float, float]]:
    out = {}
    for f in FEATURES:
        q25, q50, q75 = np.nanpercentile(frame[f], [25, 50, 75])
        out[f] = (float(q50), float(max(q75 - q25, 1e-9) / 1.349))
    return out


def p_score(frame, stats: dict[str, tuple[float, float]]) -> np.ndarray:
    """추측 가능성 점수 P (0~1). 클수록 쉬움."""
    z = np.full(len(frame), 0.2)
    for f, w in WEIGHTS.items():
        med, sd = stats[f]
        z = z + w * np.clip((np.asarray(frame[f]) - med) / sd, -3, 3)
    return 1 / (1 + np.exp(-z))
