"""수집: 종목 마스터와 가격(Parquet). 중단 후 다시 실행하면 이어서 받는다."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

from .. import config
from ..sources import listing, naver


def ingest_listing() -> pd.DataFrame:
    config.ensure_dirs()
    path = config.RAW / "stocks.parquet"
    try:
        df = listing.build_stocks()
    except Exception as e:
        if path.exists():
            print(f"[listing] 갱신 실패, 기존 캐시 사용: {e}")
            return pd.read_parquet(path)
        raise
    df.to_parquet(path, index=False)
    print(f"[listing] 상장 {int((~df.is_delisted).sum())} / 폐지 {int(df.is_delisted.sum())}")
    return df


def _one(code: str, interval: str, incremental: bool, session: requests.Session) -> tuple[str, str, int]:
    path = config.PRICES / interval / f"{code}.parquet"
    if incremental and path.exists():
        new = naver.fetch(code, interval, count=30, session=session)
        old = pd.read_parquet(path)
        df = pd.concat([old, new]).drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    else:
        df = naver.fetch(code, interval, session=session)
    df.to_parquet(path, index=False)
    return code, interval, len(df)


def ingest_prices(incremental: bool = False, limit: int | None = None, codes: list[str] | None = None) -> dict:
    config.ensure_dirs()
    stocks = listing.load_stocks()
    if incremental:
        stocks = stocks[~stocks.is_delisted]
    all_codes = codes or list(stocks["code"])
    if limit:
        all_codes = all_codes[:limit]
    jobs = []
    for interval in config.INTERVALS:
        for code in all_codes:
            if incremental or not (config.PRICES / interval / f"{code}.parquet").exists():
                jobs.append((code, interval))
    print(f"[prices] 작업 {len(jobs)}건")
    failed, done, t0 = [], 0, time.time()
    session = requests.Session()
    with ThreadPoolExecutor(config.NAVER_WORKERS) as ex:
        futs = {ex.submit(_one, c, i, incremental, session): (c, i) for c, i in jobs}
        for f in as_completed(futs):
            try:
                f.result()
            except Exception as e:
                failed.append([*futs[f], str(e)[:120]])
            done += 1
            if done % 500 == 0:
                print(f"[prices] {done}/{len(jobs)}  실패 {len(failed)}  {time.time() - t0:.0f}s", flush=True)
    summary = {"jobs": len(jobs), "failed": len(failed), "seconds": round(time.time() - t0)}
    (config.LOGS / "ingest_failed.json").write_text(json.dumps(failed, ensure_ascii=False, indent=1))
    print(f"[prices] 완료 {summary}")
    return summary
