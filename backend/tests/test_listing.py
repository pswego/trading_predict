import pandas as pd

from chartgame.sources import listing


def _fake_listing(kind: str) -> pd.DataFrame:
    if kind == "KRX":
        return pd.DataFrame({
            "Code": ["000010", "000020", "000035", "900010", "000040"],
            "Name": ["가나전자", "다라제약", "가나전자우", "마바스팩1호", "사아코넥스"],
            "Market": ["KOSPI", "KOSDAQ GLOBAL", "KOSPI", "KOSDAQ", "KONEX"],
            "Stocks": [1000, 2000, 300, 400, 500],
        })
    if kind == "KRX-DESC":
        return pd.DataFrame({
            "Code": ["000010", "000020"],
            "Sector": [None, "우량기업부"],  # 코스닥은 여기에 '소속부'가 들어 있다. 업종이 아니다
            "Industry": ["전자부품 제조업", "의약품 제조업"],
            "ListingDate": pd.to_datetime(["1990-01-03", "2001-05-02"]),
        })
    return pd.DataFrame({
        "Symbol": ["000050", "000060", "000010", "000070"],
        "Name": ["옛날상사", "옛날스팩", "가나전자", "아주옛날"],
        "Market": ["KOSPI", "KOSDAQ", "KOSPI", "KOSPI"],
        "SecuGroup": ["주권"] * 4, "Kind": ["보통주"] * 4,
        "ListingDate": ["1995-01-04"] * 4,
        "DelistingDate": ["2010-04-01", "2015-01-02", "2003-01-02", "1999-01-02"],
        "Reason": ["감사의견 거절", "피흡수합병(스팩소멸합병)", "이전상장", "부도"],
        "Industry": ["유통", "-", "전기전자", "건설"],
        "ListingShares": [5000, 100, 100, 100],
    })


def test_build_stocks_filters_and_uses_industry(monkeypatch):
    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "StockListing", _fake_listing)
    df = listing.build_stocks().set_index("code")
    # 우선주(끝자리 5), 스팩, 코넥스, 2002년 이전 폐지, 이미 상장 목록에 있는 코드의 폐지 기록은 빠진다
    assert sorted(df.index) == ["000010", "000020", "000050"]
    assert df.at["000020", "market"] == "KOSDAQ"
    assert df.at["000010", "sector"] == "전자부품 제조업"
    assert df.at["000020", "sector"] == "의약품 제조업"  # 소속부("우량기업부")가 아니라 업종
    assert bool(df.at["000050", "is_delisted"]) and df.at["000050", "delist_reason"] == "감사의견 거절"
    assert not df.loc[["000010", "000020"], "is_delisted"].any()
