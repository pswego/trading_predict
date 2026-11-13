"""판별기 품질 게이트: 기계가 실제 보기와 오답을 구별할 수 있는지 측정한다.

4지선다에서 우연히 맞힐 확률은 25%. 판별기 정답률이 이보다 훨씬 높으면 오답 생성기에 티가 남아 있다는 뜻.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import config

THRESHOLD = {"normal": 0.45, "hard": 0.35}


def _stats(o, h, l, c, prev, v=None) -> dict[str, float]:  # noqa: E741
    r = np.log(c / prev)
    rng = np.maximum(h - l, 1e-12)
    body = np.abs(c - o) / rng
    up = (h - np.maximum(o, c)) / rng
    dn = (np.minimum(o, c) - l) / rng
    sd = r.std() + 1e-12
    rc = r - r.mean()
    ar = np.abs(r)
    sign = np.sign(r)
    run = best = 1
    for i in range(1, len(sign)):
        run = run + 1 if sign[i] == sign[i - 1] and sign[i] != 0 else 1
        best = max(best, run)
    out = {
        "sd": sd, "body": body.mean(), "up": up.mean(), "dn": dn.mean(),
        "range": (rng / prev).mean(), "gapopen": np.abs(np.log(o / prev)).mean(),
        "ac1": float((rc[1:] * rc[:-1]).mean() / (rc.var() + 1e-12)),
        "ac1abs": float(np.corrcoef(ar[1:], ar[:-1])[0, 1]) if ar.std() > 0 else 0.0,
        "kurt": float((rc**4).mean() / (rc.var() ** 2 + 1e-18)),
        "skew": float((rc**3).mean() / (sd**3)),
        "maxr": ar.max() / sd, "flat": float((r == 0).mean()), "doji": float((o == c).mean()),
        "nogap": float((np.abs(o / prev - 1) < 1e-9).mean()), "run": best / len(r),
        "eff": abs(r.sum()) / (ar.sum() + 1e-12),
    }
    if v is not None:
        out["vcorr"] = float(np.corrcoef(v, ar)[0, 1]) if v.std() > 0 and ar.std() > 0 else 0.0
        out["vcv"] = float(v.std() / (v.mean() + 1e-12))
        out["vmean"] = float(v.mean())
    return out


def question_features(payload: dict) -> list[dict[str, float]]:
    """보기 4개 각각의 특징 (맥락 대비 상대값 + 보기들 사이의 상대값)."""
    L = payload["layout"]["L"]
    G = payload["layout"]["G"]
    cs = np.array(payload["candles"])
    vol = np.array(payload["volume"]) if payload.get("volume") else None

    def ctx_part(a, b):
        seg = cs[a:b]
        return _stats(seg[1:, 0], seg[1:, 1], seg[1:, 2], seg[1:, 3], seg[:-1, 3], vol[a + 1:b] if vol is not None else None)

    cl, cr = ctx_part(0, L), ctx_part(L, len(cs))
    nl, nr = L - 1, len(cs) - L - 1
    ctx = {k: (cl[k] * nl + cr[k] * nr) / (nl + nr) for k in cl}
    c0 = cs[L - 1, 3]
    rows = []
    for i, opt in enumerate(payload["options"]):
        a = np.array(opt)
        prev = np.concatenate([[c0], a[:-1, 3]])
        ov = np.array(payload["option_volume"][i]) if payload.get("option_volume") else None
        st = _stats(a[:, 0], a[:, 1], a[:, 2], a[:, 3], prev, ov)
        x = np.log(a[:, 3])
        b = np.log(c0) + (x[-1] - np.log(c0)) * np.arange(1, G + 1) / G
        f = {f"{k}_rel": st[k] - ctx[k] for k in st}
        f.update({f"{k}_ratio": st[k] / (ctx[k] + 1e-9) for k in ("sd", "range", "gapopen", "body")})
        f["S"] = np.abs(x - b).max() / (ctx["sd"] * np.sqrt(G))
        f["first_gap"] = abs(np.log(a[0, 0] / c0)) / ctx["sd"]
        f["first_r"] = np.log(a[0, 3] / c0) / ctx["sd"]
        f["last_r"] = np.log(a[-1, 3] / a[-2, 3]) / ctx["sd"]
        f["G"] = G
        rows.append(f)
    keys = list(rows[0])
    mean = {k: np.mean([r[k] for r in rows]) for k in keys}
    for r in rows:
        r.update({f"{k}_q": r[k] - mean[k] for k in keys if k != "G"})
    return rows


def evaluate(df: pd.DataFrame, folds: int = 5, seed: int = 0) -> tuple[pd.DataFrame, dict]:
    """문제 표에 ai_p_real(판별기가 본 실제 보기의 확률, 4개 합 1) 열을 붙이고 난이도별 정답률을 낸다."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold

    feats, qid, label = [], [], []
    for i, p in enumerate(df["payload"]):
        rows = question_features(json.loads(p))
        feats.extend(rows)
        qid.extend([i] * 4)
        label.extend([1, 0, 0, 0])
    X = pd.DataFrame(feats).fillna(0.0)
    y, qid = np.array(label), np.array(qid)
    groups = df["code"].to_numpy()[qid]
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(folds).split(X, y, groups):
        m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, random_state=seed)
        m.fit(X.iloc[tr], y[tr])
        oof[te] = m.predict_proba(X.iloc[te])[:, 1]
    p4 = oof.reshape(-1, 4)
    p_real = p4[:, 0] / p4.sum(axis=1)
    hit = p4.argmax(axis=1) == 0
    out = df.assign(ai_p_real=np.round(p_real, 4), ai_hit=hit)
    acc = {d: round(float(out.loc[out.difficulty == d, "ai_hit"].mean()), 4) for d in config.DIFFICULTIES
           if (out.difficulty == d).any()}
    # 어떤 특징이 티를 내는지: 실제/오답 평균 차이가 큰 순
    Xn = (X - X.mean()) / (X.std() + 1e-12)
    gapv = (Xn[y == 1].mean() - Xn[y == 0].mean()).abs().sort_values(ascending=False)
    report = {"accuracy": acc, "n": int(len(df)), "top_tells": {k: round(float(v), 3) for k, v in gapv.head(8).items()}}
    return out, report
