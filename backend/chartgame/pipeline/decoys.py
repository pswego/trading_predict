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
# 출처 구간의 변동성(수준 보정 후)이 실제 빈칸 대비 이 범위 안이어야 후보가 된다
K_RANGE = {"any": (0.4, 2.5), "volmis": (0.4, 2.5), "tier": (0.7, 1.4), "same": (0.7, 1.4), "sector": (0.7, 1.4), "anym": (0.7, 1.4)}
MATCHED = ("tier", "same", "sector", "anym")  # 실제 보기와 통계적 성질까지 맞추는 유형
# 실제 보기와 맞추는 성질: 이름 → (보기끼리 무작위로 흩뜨리는 폭, 거리 계산 단위). traits() 참고
MATCH_SPEC = {
    "vol": (0.12, 0.06), "S": (0.20, 0.12), "B": (0.05, 0.04), "flat": (0.03, 0.04), "nogap": (0.05, 0.06),
    "rng": (0.10, 0.08), "dn": (0.04, 0.04), "doji": (0.03, 0.04),
}
MAX_MATCH_DIST = 1.5 * len(MATCH_SPEC)
# 이 성질들은 오답이 실제보다 큰지 작은지까지 미리 정한 대로 맞춘다. 그래야 "변동성이 제일 작은 보기가 정답"
# 같은 요령이 통하지 않는다 (실제 보기가 4개 중 몇 등인지가 완전히 무작위가 된다).
SIGN_KEYS = ("vol", "B", "flat")
N_CAND = 100
# 후보를 못 찾으면 더 넓은 풀로 내려간다. "anym"은 종목 제한 없이 찾되 성질은 똑같이 맞추는 유형
FALLBACK = {"same": "sector", "sector": "tier", "tier": "anym", "volmis": "any", "mirror": "any"}
CTX_W = 30  # 출처 구간의 주변 변동성을 재는 폭 (앞뒤 각각)
MAX_DELTA = 0.3  # 오른 봉/내린 봉 배율 차이의 한도
FLAT_SLACK = 0.04  # 출처와 문제의 '변동 없는 날' 비율 차이 한도 (호가 단위 굵기가 비슷해야 한다)
K_LEVEL = (0.4, 2.5)  # 종목 간 변동성 수준 차이를 맞추는 배율의 허용 범위
SOURCE_LABEL = {"mirror": "mirror", "volmis": "other_stock_volatility_mismatch", "any": "other_stock", "anym": "other_stock",
                "tier": "same_market_cap_tier", "same": "same_stock_other_period", "sector": "same_sector"}


class SegIndex:
    """길이 G인 출처 구간 색인. 빠르게 '비슷한 변동성·수익률' 구간을 찾기 위한 것."""

    def __init__(self, series: dict[str, Series], G: int, stride: int = 1, sectors: dict[str, str] | None = None):
        self.G = G
        self.codes = list(series)
        self.series = series
        ci, st, sg, sx, fl, R, tier, mkt = [], [], [], [], [], [], [], []
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
            # 주변(앞뒤 W봉) 변동성: 출처 구간이 제 주변에 비해 얼마나 요동쳤는지 알기 위한 값
            a, b = np.maximum(starts - CTX_W, 1), np.minimum(starts + G + CTX_W, len(s))
            n = (starts - a) + (b - starts - G)
            sm = (c1[starts] - c1[a]) + (c1[b] - c1[starts + G])
            sm2 = (c2[starts] - c2[a]) + (c2[b] - c2[starts + G])
            sctx = np.sqrt(np.maximum(sm2 / np.maximum(n, 1) - (sm / np.maximum(n, 1)) ** 2, 0))
            ok &= (n >= CTX_W) & (sctx > 1e-4) & (s.cs_bad[b] - s.cs_bad[a] == 0)
            flat = (s.cs_flat[b] - s.cs_flat[a]) / np.maximum(b - a, 1)
            starts, Rv, sig, sctx, flat = starts[ok], Rv[ok], sig[ok], sctx[ok], flat[ok]
            n = len(starts)
            if n == 0:
                continue
            ci.append(np.full(n, i, dtype=np.int32))
            st.append(starts.astype(np.int32))
            sg.append(sig.astype(np.float32))
            sx.append(sctx.astype(np.float32))
            fl.append(flat.astype(np.float32))
            R.append(Rv.astype(np.float32))
            tier.append(s.tier[starts] if s.tier is not None else np.full(n, -1, dtype=np.int8))
            mkt.append(np.full(n, 0 if s.market == "KOSPI" else 1, dtype=np.int8))
            self.code_slice[code] = (pos, pos + n)
            pos += n
        cat = lambda xs, dt: np.concatenate(xs) if xs else np.array([], dtype=dt)  # noqa: E731
        self.ci, self.start, self.sigma, self.R = cat(ci, np.int32), cat(st, np.int32), cat(sg, np.float32), cat(R, np.float32)
        self.sigma_ctx = cat(sx, np.float32)
        self.flat = cat(fl, np.float32)  # 주변에서 종가가 안 변한 날의 비율 (호가 단위가 얼마나 굵은지)
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
        if kind in ("any", "volmis", "anym"):
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
    """출처 구간을 변동성 k배로 맞추고, 오른 봉과 내린 봉의 배율을 살짝 다르게 해서 끝점을 정확히 맞춘다.

    봉마다 (시가·고가·저가·종가)를 같은 배율로 늘리므로 '종가 변동 없음', 도지(시가=종가), 갭 없는 시가 같은
    실제 차트의 특징이 그대로 남는다. (O, H, L, C, delta) 반환. delta는 오른 봉/내린 봉 배율의 차이 정도.
    만들 수 없으면 None.
    """
    sl = slice(start, start + G)
    r = s.r[sl]
    up, dn = r[r > 0].sum(), -r[r < 0].sum()
    if up + dn <= 0:
        return None
    delta = (R_target / k - (up - dn)) / (up + dn)
    if abs(delta) >= 1:
        return None
    f = np.where(r > 0, k * (1 + delta), np.where(r < 0, k * (1 - delta), k))
    rr, ro, rh, rl = r * f, s.ro[sl] * f, s.rh[sl] * f, s.rl[sl] * f
    C = c0 * np.exp(np.cumsum(rr))
    prev = np.concatenate([[c0], C[:-1]])
    return prev * np.exp(ro), prev * np.exp(rh), prev * np.exp(rl), C, float(delta)


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


def traits(O, H, L, C, c0: float, sigma_c: float) -> dict[str, float]:
    """보기 하나의 통계적 성질. 판별기가 실제와 가짜를 가르는 데 쓰던 것들이라, 오답을 고를 때 실제와 맞춘다."""
    prev = np.concatenate([[c0], C[:-1]])
    r = np.log(C / prev)
    rng = H - L
    safe = np.where(rng > 0, rng, 1)
    return {
        "vol": float(np.log(r.std() + 1e-9)),
        "S": float(np.log(max(F.surprise(np.log(C), np.log(c0), sigma_c), 1e-6))),
        "B": float(np.where(rng > 0, np.abs(C - O) / safe, 0).mean()),
        "flat": float((C == prev).mean()),  # 종가가 안 변한 날
        "nogap": float((O == prev).mean()),  # 시가가 전날 종가와 같은 날
        "rng": float(np.log((rng / prev).mean() + 1e-9)),
        "dn": float(np.where(rng > 0, (np.minimum(O, C) - L) / safe, 0).mean()),  # 아래꼬리 비율
        "doji": float((O == C).mean()),
    }


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
    ctx_flat = float((s.cs_flat[gs] - s.cs_flat[st] + s.cs_flat[st + N] - s.cs_flat[ge]) / (L + R))
    # 실제 보기가 늘 '가운데 값'이 되면 그것이 단서가 된다. 보기 4개의 자리를 무작위로 뽑고 그중 하나를
    # 실제 보기 자리로 정해, 실제 보기가 어느 성질에서든 1~4등이 될 확률을 같게 만든다.
    u = {key: rng.uniform(-w, w, 4) for key, (w, _) in MATCH_SPEC.items()}
    real_slot = int(rng.integers(0, 4))
    u["rng"] = u["vol"] * (MATCH_SPEC["rng"][0] / MATCH_SPEC["vol"][0])  # 봉 길이는 변동성과 같이 움직인다
    offsets = [{key: float(u[key][i] - u[key][real_slot]) for key in u} for i in range(4) if i != real_slot]

    options = [tuple(np.asarray(a, dtype="float64") for a in real)]
    T_t = traits(*options[0], c0, sigma_c)
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

    def from_pool(kind: str, off: dict[str, float]) -> bool:
        rows = index.sample(kind, rng, s.code, s.market, tier, sector)
        if len(rows) == 0:
            return False
        # 배율 k는 '종목의 평소 변동성 수준'만 맞춘다(맥락 대 맥락). 그러고 나서 출처 구간의 변동성이
        # 실제 빈칸과 비슷한 것만 고른다. 빈칸 변동성에 직접 맞춰 늘리면 시가 갭·꼬리까지 부자연스럽게 커진다.
        mult = float(rng.choice([0.5, 1.8])) if kind == "volmis" else 1.0
        k = sigma_c * mult / index.sigma_ctx[rows]
        eff = k * index.sigma[rows] / (sg * mult)
        lo, hi = K_RANGE[kind]
        ok = (eff >= lo) & (eff <= hi) & (k >= K_LEVEL[0] * mult) & (k <= K_LEVEL[1] * mult)
        ok &= np.abs(k * index.R[rows] - R_t) / G <= config.MAX_DRIFT_SIGMA * sg * mult
        matched = kind in MATCHED
        if matched:  # 호가 단위 굵기가 다르면 계단 모양이 달라 티가 난다
            ok &= np.abs(index.flat[rows] - ctx_flat) <= FLAT_SLACK
        if kind == "same":
            ok &= (index.start[rows] + G <= st - G) | (index.start[rows] >= st + N + G)
        elif used_codes:
            ok &= np.array([index.codes[i] not in used_codes for i in index.ci[rows]])
        rows, k, eff = rows[ok], k[ok], eff[ok]
        if len(rows) == 0:
            return False
        order = rng.permutation(len(rows))[:N_CAND]
        cands = []
        for j in order:
            src = index.series[index.codes[index.ci[rows[j]]]]
            tf = transform(src, int(index.start[rows[j]]), G, float(k[j]), R_t, c0)
            if tf is None or abs(tf[4]) > MAX_DELTA:
                continue
            O, H, Lo, C = snap(*tf[:4], grid, c_end)
            dist = 0.0
            if matched:
                tr = traits(O, H, Lo, C, c0, sigma_c)
                if any((tr[key] - T_t[key]) * off[key] < 0 for key in SIGN_KEYS):
                    continue  # 정해 둔 방향(실제보다 큼/작음)과 반대
                dist = sum(abs(tr[key] - T_t[key] - off[key]) / unit for key, (_, unit) in MATCH_SPEC.items())
                if dist > MAX_MATCH_DIST:
                    continue
            sv = src.v[index.start[rows[j]]: index.start[rows[j]] + G]
            vol = sv * (np.median(real_v) / max(np.median(sv), 1e-9))
            cands.append((dist, O, H, Lo, C, vol, src.code))
            if not matched and len(cands) >= 6:
                break
        cands.sort(key=lambda c: c[0])
        for _, O, H, Lo, C, vol, code in cands[:8]:
            if accept(O, H, Lo, C, vol, SOURCE_LABEL[kind]):
                if kind != "same":
                    used_codes.add(code)
                return True
        return False

    for kind, off in zip(STRATEGY[difficulty], offsets, strict=True):
        done = False
        if kind == "mirror":
            done = accept(*mirror(*real, c0), real_v.astype("float64"), SOURCE_LABEL["mirror"])
            kind = "any"
        while not done and kind:
            done = from_pool(kind, off) or from_pool(kind, off)
            if not done:
                kind = FALLBACK.get(kind)
                if difficulty == "hard" and kind == "any":
                    kind = None  # 어려움에서 아무 종목으로까지 내려가지는 않는다
        if not done:
            return None
    return {"options": options, "volumes": volumes, "sources": sources, "c0": c0, "grid": grid,
            "S": S_t, "sigma_g": sg}
