"""시각 QA: 문제를 4지선다 화면처럼 그린 컨택트 시트 PNG."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .. import config  # noqa: E402

UP, DOWN = "#e5484d", "#3b82f6"


def draw_candles(ax, candles, x0=0, alpha=1.0, width=0.7):
    for i, (o, h, l, c) in enumerate(candles):  # noqa: E741
        col = UP if c >= o else DOWN
        x = x0 + i
        ax.plot([x, x], [l, h], color=col, lw=0.6, alpha=alpha)
        ax.add_patch(plt.Rectangle((x - width / 2, min(o, c)), width, max(abs(c - o), 1e-4), color=col, alpha=alpha))


def draw_question(axes, payload: dict, order=None, mark_answer=True):
    L, G = payload["layout"]["L"], payload["layout"]["G"]
    cs = payload["candles"]
    opts = payload["options"]
    order = order or [0, 1, 2, 3]
    lo = min(min(c[2] for c in cs), min(c[2] for o in opts for c in o))
    hi = max(max(c[1] for c in cs), max(c[1] for o in opts for c in o))
    pad = (hi - lo) * 0.05
    for ax, k in zip(axes, order, strict=True):
        draw_candles(ax, cs[:L], 0, alpha=0.55)
        draw_candles(ax, cs[L:], L + G, alpha=0.55)
        draw_candles(ax, opts[k], L)
        ax.axvspan(L - 0.5, L + G - 0.5, color="#888", alpha=0.08)
        ax.set_ylim(lo - pad, hi + pad)
        ax.set_xticks([])
        ax.set_yticks([])
        if mark_answer and k == 0:
            for sp in ax.spines.values():
                sp.set_color("#16a34a")
                sp.set_linewidth(2.5)


def contact_sheet(df: pd.DataFrame, path, n: int = 12, mark_answer: bool = True, seed: int = 0):
    df = df.sample(min(n, len(df)), random_state=seed)
    rng = np.random.default_rng(seed)
    fig, axes = plt.subplots(len(df), 4, figsize=(16, 2.2 * len(df)), squeeze=False)
    for row, q in zip(axes, df.itertuples(), strict=True):
        payload = json.loads(q.payload)
        order = list(rng.permutation(4))
        draw_question(row, payload, order, mark_answer)
        rv = json.loads(q.reveal)
        row[0].set_ylabel(f"{q.difficulty}\nP={q.p_score:.2f}", fontsize=8)
        row[0].set_title(f"{rv['code']} {q.interval} {rv['gap_start']}  {'/'.join(rv['decoy_sources'])}", fontsize=7, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=70)
    plt.close(fig)


def run(interval: str, difficulty: str, n: int = 12, mark_answer: bool = True, seed: int = 0):
    df = pd.read_parquet(config.WORK / f"questions_{interval}.parquet")
    df = df[df.difficulty == difficulty]
    out = config.WORK / f"preview_{interval}_{difficulty}{'' if mark_answer else '_blind'}.png"
    contact_sheet(df, out, n, mark_answer, seed)
    return out
