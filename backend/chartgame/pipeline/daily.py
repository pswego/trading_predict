"""일일 자동화: 증분 수집 → 문제 생성 → 판별기 평가 → DB 적재."""
from __future__ import annotations

import datetime as dt
import json
import traceback

import pandas as pd

from .. import config
from . import build, discriminator, generate, ingest


def evaluate(interval: str) -> dict:
    """문제 Parquet에 판별기 점수를 붙이고, 판별기가 너무 쉽게 맞히는 '어려움' 문제는 '보통'으로 내린다."""
    path = config.WORK / f"questions_{interval}.parquet"
    df = pd.read_parquet(path).drop(columns=["ai_p_real", "ai_hit"], errors="ignore")
    df, report = discriminator.evaluate(df)
    obvious = (df.difficulty == "hard") & (df.ai_p_real > 0.6)
    df.loc[obvious, "difficulty"] = "normal"
    report["downgraded_hard"] = int(obvious.sum())
    report["accuracy_after"] = {d: round(float(df.loc[df.difficulty == d, "ai_hit"].mean()), 4)
                                for d in config.DIFFICULTIES if (df.difficulty == d).any()}
    report["passed"] = all(report["accuracy_after"].get(d, 0) <= t for d, t in discriminator.THRESHOLD.items())
    df.to_parquet(path, index=False)
    (config.WORK / f"discriminator_{interval}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return report


def full_build(limit: int | None = None, workers: int = 4) -> dict:
    out: dict = {}
    for iv in config.INTERVALS:
        df = generate.run(iv, limit=limit, workers=workers)
        out[iv] = {"questions": len(df), "discriminator": evaluate(iv) if len(df) >= 200 else None}
    out["db"] = build.run()
    return out


def run() -> dict:
    """거래일 장 마감 후 실행."""
    config.ensure_dirs()
    log = {"started": dt.datetime.now().isoformat(timespec="seconds")}
    try:
        log["ingest"] = ingest.ingest_prices(incremental=True)
        log["build"] = full_build()
        log["ok"] = True
    except Exception:
        log["ok"] = False
        log["error"] = traceback.format_exc()
    (config.LOGS / f"daily_{dt.date.today()}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str))
    return log


def refresh_listing() -> None:
    """주 1회: 신규 상장·폐지 반영. 새 종목의 가격만 추가로 받는다."""
    ingest.ingest_listing()
    ingest.ingest_prices()
