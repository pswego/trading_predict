"""서버에서 바로 서비스할 수 있는 한 파일짜리 게임 페이지를 만든다 (tools/standalone_template.html + 문제 데이터).

난이도는 '오답이 실제와 얼마나 다르게 생겼는가'로 다시 매긴다: 차이가 큰 문제부터 쉬움·보통·어려움.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import config

KEYS = ("name", "code", "gap_start", "gap_end", "gap_return_pct", "gap_max_pct", "gap_min_pct", "delisted",
        "decoy_sources", "cap_tier_then")


def separation(payload: dict) -> float:
    o = [np.log(np.array(x)[:, 3]) for x in payload["options"]]
    real = o[0]
    scale = np.std(np.diff(real)) * np.sqrt(len(real)) + 1e-9
    return float(min(np.sqrt(np.mean((d - real) ** 2)) / scale for d in o[1:]))


def build_questions(per_interval: dict[str, int] | None = None, seed: int = 3) -> list[dict]:
    per_interval = per_interval or {"day": 240, "week": 60}
    out = []
    for iv, n in per_interval.items():
        df = pd.read_parquet(config.WORK / f"questions_{iv}.parquet")
        s = df[df.difficulty.isin(["easy", "normal"])]
        s = s.sample(min(len(s), 9000 if iv == "day" else 5000), random_state=seed).copy()
        s["sep"] = [separation(json.loads(p)) for p in s.payload]
        s = s.sort_values("sep", ascending=False)
        k = n // 3
        for d, part in (("easy", s.iloc[:k]), ("normal", s.iloc[k * 3:k * 4]), ("hard", s.iloc[k * 8:k * 9])):
            for r in part.itertuples():
                p = json.loads(r.payload)
                p.pop("ma", None)
                rv = json.loads(r.reveal)
                out.append({"iv": iv, "d": d, "m": r.market, "t": r.cap_tier, "p": p, "r": {x: rv[x] for x in KEYS}})
    return out


def render(questions: list[dict], server_room: bool = True) -> str:
    tpl = (config.REPO / "tools" / "standalone_template.html").read_text()
    html = tpl.replace("__DATA__", json.dumps(questions, ensure_ascii=False, separators=(",", ":")))
    if server_room:  # 대전용 WebSocket 연결을 게임 스크립트보다 먼저 넣는다
        html = html.replace("<script>const Q=", '<script src="/static/room_shim.js"></script>\n<script>const Q=', 1)
    return html


def write(path=None) -> str:
    path = path or (config.REPO / "backend" / "chartgame" / "static" / "game.html")
    path.write_text(render(build_questions()))
    return str(path)
