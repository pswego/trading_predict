"""오답(가짜 보기) 생성. 모든 보기는 빈칸 직전 종가에서 출발해 실제 빈칸 마지막 종가에서 끝난다."""
from __future__ import annotations

import numpy as np

from .. import config
from . import features as F
from .clean import Series

# 난이도별 오답 3개의 출처 유형
STRATEGY = {
    "easy": ("mirror", "volmis", "any"),
    "normal": ("tier", "tier", "tier"),
    "hard": ("same", "same", "sector"),
}
K_RANGE = {"any": (0.4, 2.5), "volmis": (0.4, 2.5), "tier": (0.8, 1.25), "same": (0.85, 1.18), "sector": (0.85, 1.18)}
S_TOL = {"tier": (0.25, 0.35), "same": (0.20, 0.25), "sector": (0.20, 0.25)}  # (절대, 상대) 허용 오차
FALLBACK = {"same": "sector", "sector": "tier", "tier": "any", "volmis": "any", "mirror": "any"}
SOURCE_LABEL = {"mirror": "mirror", "volmis": "other_stock_volatility_mismatch", "any": "other_stock",
                "tier": "same_market_cap_tier", "same": "same_stock_other_period", "sector": "same_sector"}


class SegIndex:
    """길이 G인 출처 구간 색인. 빠르게 '비슷한 변동성·수익률' 구간을 찾기 위한 것."""

    def __init__(self, series: dict[str, Series], G: int, stride: int = 1, sectors: dict[str, str] | None = None):
        self.G = G
        self.codes = list(series)
        self.series = series
        ci, st, sg, R, tier, mkt = [], [], [], [], [], []
        self.code_slice: dict[str, tuple[int, int]] = {}
        pos = 0
        for i, code in enumerate(self.codes):
            s = series[code]
            starts = np.arange(1, len(s) - G + 1, stride)
            if len(starts) == 0:
                continue
            ok = (s.cs_bad[starts + G] - s.cs_bad[starts] == 0) & (s.cs_notrade[starts + G] - s.cs_notrade[starts] == 0)
            ok &= (s.cs_flat[starts + G] - s.cs_flat[starts]) <= 0.1 * G
            c1 = np.concatenate([[0], np.cumsum(s.r)])
            c2 = np.concatenate([[0], np.cumsum(s.r**2)])
            Rv = c1[starts + G] - c1[starts]
            var = (c2[starts + G] - c2[starts]) / G - (Rv / G) ** 2
            sig = np.sqrt(np.maximum(var, 0))
            ok &= sig > 1e-4
            starts, Rv, sig = starts[ok], Rv[ok], sig[ok]
            n = len(starts)
            if n == 0:
                continue
            ci.append(np.full(n, i, dtype=np.int32))
            st.append(starts.astype(np.int32))
            sg.append(sig.astype(np.float32))
            R.append(Rv.astype(np.float32))
            tier.append(s.tier[starts] if s.tier is not None else np.full(n, -1, dtype=np.int8))
            mkt.append(np.full(n, 0 if s.market == "KOSPI" else 1, dtype=np.int8))
            self.code_slice[code] = (pos, pos + n)
            pos += n
        cat = lambda xs, dt: np.concatenate(xs) if xs else np.array([], dtype=dt)  # noqa: E731
        self.ci, self.start, self.sigma, self.R = cat(ci, np.int32), cat(st, np.int32), cat(sg, np.float32), cat(R, np.float32)
        self.tier, self.mkt = cat(tier, np.int8), cat(mkt, np.int8)
        self.n = len(self.ci)
        self.pool_tier = {(m, t): np.where((self.mkt == m) & (self.tier == t))[0] for m in (0, 1) for t in range(4)}
        self.pool_sector: dict[str, np.ndarray] = {}
        if sectors:
            by: dict[str, list[int]] = {}
            for i, code in enumerate(self.codes):
                sec = sectors.get(code)
                if sec and code in self.code_slice:
                    by.setdefault(sec, []).append(i)
            for sec, idxs in by.items():
                if len(idxs) >= 3:
                    self.pool_sector[sec] = np.concatenate([np.arange(*self.code_slice[self.codes[i]]) for i in idxs])

    def sample(self, kind: str, rng, code: str, market: str, tier: int, sector: str | None) -> np.ndarray:
        if kind in ("any", "volmis"):
            return rng.integers(0, self.n, size=config.DECOY_SAMPLE)
        if kind == "tier":
            pool = self.pool_tier.get((0 if market == "KOSPI" else 1, tier))
        elif kind == "same":
            a, b = self.code_slice.get(code, (0, 0))
            return np.arange(a, b)
        else:
            pool = self.pool_sector.get(sector) if sector else None
        if pool is None or len(pool) == 0:
            return np.array([], dtype=np.int64)
        return pool[rng.integers(0, len(pool), size=min(config.DECOY_SAMPLE, len(pool) * 2))]


def price_grid(*arrays) -> float:
    """맥락에서 관측된 가격 최소 단위."""
    u = np.unique(np.concatenate([np.asarray(a, dtype="float64").ravel() for a in arrays]))
    d = np.diff(u)
    d = d[d > 1e-9]
    return float(d.min()) if len(d) else 0.0


def snap(O, H, L, C, grid: float, c_end: float):  # noqa: E741
    if grid > 0:
        O, H, L, C = (np.round(a / grid) * grid for a in (O, H, L, C))  # noqa: E741
    C = C.copy()
    C[-1] = c_end
    H = np.maximum(H, np.maximum(O, C))
    L = np.minimum(L, np.minimum(O, C))  # noqa: E741
    return O, H, L, C


def transform(s: Series, start: int, G: int, k: float, R_target: float, c0: float):
    """출처 구간을 변동성 k배 + 드리프트 보정으로 끝점에 맞춘다. (O,H,L,C, d) 반환."""
    sl = slice(start, start + G)
    r = s.r[sl] * k
    d = (R_target - r.sum()) / G
    r = r + d
    ro, rh, rl = s.ro[sl] * k, s.rh[sl] * k, s.rl[sl] * k
    C = c0 * np.exp(np.cumsum(r))
    prev = np.concatenate([[c0], C[:-1]])
    O = prev * np.exp(ro)
    H = prev * np.exp(np.maximum(rh, np.maximum(ro, r)))
    L = prev * np.exp(np.minimum(rl, np.minimum(ro, r)))  # noqa: E741
    return O, H, L, C, d


def mirror(O, H, L, C, c0: float):  # noqa: E741
    """브리지(직선)를 축으로 상하 반전. 끝점은 그대로다."""
    G = len(C)
    b = F.bridge(np.log(c0), np.log(C[-1]), G)
    flip = lambda p: np.exp(2 * b - np.log(p))  # noqa: E731
    return flip(O), flip(L), flip(H), flip(C)


def validate_option(O, H, L, C, c0: float, c_end: float, limit: np.ndarray | None, grid: float) -> str | None:  # noqa: E741
    """오답 불변식 검사. 문제가 없으면 None, 있으면 이유."""
    if not (np.all(np.isfinite([O, H, L, C])) and min(O.min(), L.min(), C.min()) > 0):
        return "nonpositive"
    if abs(C[-1] / c_end - 1) > 1e-9:
        return "endpoint"
    if np.any(L > np.minimum(O, C) + 1e-9) or np.any(H < np.maximum(O, C) - 1e-9):
        return "ohlc_order"
    prev = np.concatenate([[c0], C[:-1]])
    if limit is not None and np.all(np.isfinite(limit)):
        eps = 1e-9
        if np.any(np.abs(C / prev - 1) > limit + eps) or np.any(H / prev - 1 > limit + eps) or np.any(1 - L / prev > limit + eps):
            return "price_limit"
    if grid > 0:
        for a in (O, H, L, C):
            a = a[~np.isclose(a, c_end, rtol=1e-12)]  # 끝점(실제 종가)은 격자 밖일 수 있다
            if np.any(np.abs(a / grid - np.round(a / grid)) > 1e-6):
                return "grid"
    return None


def shape_dist(xa: np.ndarray, xb: np.ndarray, scale: float) -> float:
    """끝점이 같은 두 로그 경로의 형태 거리 (σ_g·√G 단위)."""
    return float(np.sqrt(np.mean((xa - xb) ** 2)) / scale)


def make_question(s: Series, st: int, L: int, G: int, R: int, difficulty: str, index: SegIndex,
                  sector: str | None, rng, sigma_c: float) -> dict | None:
    """실제 보기 + 오답 3개. 만들 수 없으면 None."""
    N = L + G + R
    gs, ge = st + L, st + L + G
    c0, c_end = float(s.c[gs - 1]), float(s.c[ge - 1])
    real = (s.o[gs:ge], s.h[gs:ge], s.l[gs:ge], s.c[gs:ge])
    real_v = s.v[gs:ge]
    xr = np.log(real[3])
    R_t = float(np.log(c_end / c0))
    sg = float(s.r[gs:ge].std())
    S_t = F.surprise(xr, np.log(c0), sigma_c)
    scale = sg * np.sqrt(G)
    ctx = [a[st:gs] for a in (s.o, s.h, s.l, s.c)] + [a[ge:st + N] for a in (s.o, s.h, s.l, s.c)]
    grid = price_grid(*ctx)
    limit = s.limit[gs:ge] if s.interval == "day" else None
    tier = int(s.tier[gs])

    options = [tuple(np.asarray(a, dtype="float64") for a in real)]
    volumes = [real_v.astype("float64")]
    sources: list[str] = []
    paths = [xr]
    used_codes = {s.code} if difficulty != "hard" else set()

    def accept(O, H, Lo, C, vol, label) -> bool:
        O, H, Lo, C = snap(O, H, Lo, C, grid, c_end)
        if validate_option(O, H, Lo, C, c0, c_end, limit, grid):
            return False
        x = np.log(C)
        if any(shape_dist(x, p, scale) < config.DIVERSITY_MIN for p in paths):
            return False
        options.append((O, H, Lo, C))
        volumes.append(vol)
        sources.append(label)
        paths.append(x)
        return True

    def from_pool(kind: str) -> bool:
        rows = index.sample(kind, rng, s.code, s.market, tier, sector)
        if len(rows) == 0:
            return False
        mult = float(rng.choice([0.5, 1.8])) if kind == "volmis" else 1.0
        k = sg * mult / index.sigma[rows]
        lo, hi = K_RANGE[kind]
        ok = (k >= lo * mult) & (k <= hi * mult)
        ok &= np.abs(k * index.R[rows] - R_t) / G <= config.MAX_DRIFT_SIGMA * sg * mult
        if kind == "same":
            ok &= (index.start[rows] + G <= st - G) | (index.start[rows] >= st + N + G)
        else:
            ok &= np.array([index.codes[i] not in used_codes for i in index.ci[rows]]) if used_codes else True
        rows, k = rows[ok], k[ok]
        if len(rows) == 0:
            return False
        order = rng.permutation(len(rows))[:80]
        cands = []
        for j in order:
            src = index.series[index.codes[index.ci[rows[j]]]]
            O, H, Lo, C, _ = transform(src, int(index.start[rows[j]]), G, float(k[j]), R_t, c0)
            x = np.log(C)
            if kind in S_TOL:
                a, rel = S_TOL[kind]
                if abs(F.surprise(x, np.log(c0), sigma_c) - S_t) > max(a, rel * S_t):
                    continue
            sv = src.v[index.start[rows[j]]: index.start[rows[j]] + G]
            vol = sv * (np.median(real_v) / max(np.median(sv), 1e-9))
            cands.append((shape_dist(x, xr, scale), O, H, Lo, C, vol, src.code))
            if kind not in ("same", "sector") and len(cands) >= 6:
                break
            if len(cands) >= 30:
                break
        if not cands:
            return False
        if kind in ("same", "sector"):  # 어려움: 너무 같지도, 너무 다르지도 않은 것부터
            cands.sort(key=lambda t: t[0])
            a, b = int(len(cands) * 0.3), max(int(len(cands) * 0.6), 1)
            cands = cands[a:b] + cands[:a] + cands[b:]
        for _, O, H, Lo, C, vol, code in cands:
            if accept(O, H, Lo, C, vol, SOURCE_LABEL[kind]):
                if kind != "same":
                    used_codes.add(code)
                return True
        return False

    for kind in STRATEGY[difficulty]:
        done = False
        if kind == "mirror":
            done = accept(*mirror(*real, c0), real_v.astype("float64"), SOURCE_LABEL["mirror"])
            kind = "any"
        while not done and kind:
            done = from_pool(kind) or from_pool(kind)
            if not done:
                kind = FALLBACK.get(kind)
                if difficulty == "hard" and kind == "any":
                    kind = None  # 어려움에서 아무 종목으로까지 내려가지는 않는다
        if not done:
            return None
    return {"options": options, "volumes": volumes, "sources": sources, "c0": c0, "grid": grid,
            "S": S_t, "sigma_g": sg}
