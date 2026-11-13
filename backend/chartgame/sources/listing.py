"""종목 마스터: 현재 상장 종목 + 상장폐지 종목 (FinanceDataReader, KRX)."""
from __future__ import annotations

import time

import pandas as pd

from .. import config


def _retry(fn, tries: int = 4):
    err = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # KRX 엔드포인트는 간헐적으로 실패한다
            err = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"listing fetch failed: {err}")


def _listed() -> pd.DataFrame:
    import FinanceDataReader as fdr

    df = _retry(lambda: fdr.StockListing("KRX"))
    df = df[df["Market"].isin(["KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"])]
    df = df[df["Code"].str.endswith("0")]
    df = df[~df["Name"].str.contains(config.EXCLUDE_NAME_PATTERN)]
    out = pd.DataFrame({
        "code": df["Code"], "name": df["Name"],
        "market": df["Market"].replace({"KOSDAQ GLOBAL": "KOSDAQ"}),
        "shares": pd.to_numeric(df["Stocks"], errors="coerce"),
        "is_delisted": False,
    })
    out["listed_date"] = pd.NaT
    out["delisted_date"] = pd.NaT
    out["delist_reason"] = None
    out["sector"] = None
    try:
        desc = _retry(lambda: fdr.StockListing("KRX-DESC"), tries=2)
        sec = desc.set_index("Code")
        col = "Industry" if "Industry" in sec.columns else None
        if col:
            out["sector"] = out["code"].map(sec[col])
        if "ListingDate" in sec.columns:
            out["listed_date"] = pd.to_datetime(out["code"].map(sec["ListingDate"]), errors="coerce")
    except Exception:
        pass
    return out


def _delisted() -> pd.DataFrame:
    import FinanceDataReader as fdr

    df = _retry(lambda: fdr.StockListing("KRX-DELISTING"))
    df = df[(df["SecuGroup"] == "주권") & (df["Kind"] == "보통주") & df["Market"].isin(["KOSPI", "KOSDAQ"])]
    df = df.assign(DelistingDate=pd.to_datetime(df["DelistingDate"], errors="coerce"))
    df = df[df["DelistingDate"] >= config.DELIST_SINCE]
    df = df[~df["Name"].str.contains(config.EXCLUDE_NAME_PATTERN)]
    df = df[~df["Reason"].fillna("").str.contains("스팩")]
    return pd.DataFrame({
        "code": df["Symbol"], "name": df["Name"], "market": df["Market"],
        "shares": pd.to_numeric(df["ListingShares"], errors="coerce"),
        "is_delisted": True,
        "listed_date": pd.to_datetime(df["ListingDate"], errors="coerce"),
        "delisted_date": df["DelistingDate"],
        "delist_reason": df["Reason"],
        "sector": df["Industry"].replace({"-": None}),
    })


def build_stocks() -> pd.DataFrame:
    listed = _listed()
    delisted = _delisted()
    delisted = delisted[~delisted["code"].isin(listed["code"])]
    delisted = delisted.sort_values("delisted_date").drop_duplicates("code", keep="last")
    cols = ["code", "name", "market", "sector", "listed_date", "delisted_date", "delist_reason", "shares", "is_delisted"]
    return pd.concat([listed[cols], delisted[cols]], ignore_index=True)


def load_stocks() -> pd.DataFrame:
    return pd.read_parquet(config.RAW / "stocks.parquet")
