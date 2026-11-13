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


STATIC = config.REPO / "backend" / "chartgame" / "static"
MQTT_JS = "https://cdnjs.cloudflare.com/ajax/libs/mqtt/5.10.1/mqtt.min.js"


def render(questions: list[dict], room: str = "server") -> str:
    """room: 'server' (우리 서버의 WebSocket) | 'relay' (공개 MQTT 중계, 정적 호스팅용) | 'none'"""
    tpl = (config.REPO / "tools" / "standalone_template.html").read_text()
    html = tpl.replace("__DATA__", json.dumps(questions, ensure_ascii=False, separators=(",", ":")))
    if room == "server":  # 대전 연결 스크립트를 게임 스크립트보다 먼저 넣는다
        inject = '<script src="/static/room_shim.js"></script>\n'
    elif room == "relay":  # 정적 호스팅: 무료 공개 MQTT 중계 서버로 대전 (네트워크가 달라도 연결됨)
        inject = f'<script src="{MQTT_JS}"></script>\n<script>{(STATIC / "room_mqtt.js").read_text()}</script>\n'
    else:
        inject = ""
    return html.replace("<script>const Q=", inject + "<script>const Q=", 1)


def write(path=None) -> str:
    path = path or (STATIC / "game.html")
    path.write_text(render(build_questions()))
    return str(path)


def write_site(out=None) -> str:
    """GitHub Pages 등 정적 호스팅용: site/index.html 하나."""
    out = out or (config.REPO / "site")
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render(build_questions(), room="relay"))
    (out / ".nojekyll").write_text("")
    return str(out / "index.html")
