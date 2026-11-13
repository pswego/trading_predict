from pathlib import Path

import numpy as np
import pandas as pd

from chartgame.core.limits import price_limit
from chartgame.pipeline import clean
from chartgame.sources import naver

from .conftest import synth_frame

XML = (Path(__file__).parent / "fixtures" / "naver_sample.xml").read_text()


def test_parse_xml_rows_and_dedup():
    df = naver.parse_xml(XML)
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(df) == 4  # 같은 날짜는 마지막 것만
    assert df.iloc[-1]["close"] == 13850
    assert df["date"].is_monotonic_increasing


def test_parse_xml_empty():
    assert naver.parse_xml("<protocol><chartdata></chartdata></protocol>").empty
    assert naver.parse_xml("").empty


def test_price_limit_by_era():
    d = ["2004-01-05", "2005-03-28", "2015-06-12", "2015-06-15"]
    assert price_limit("KOSPI", d).tolist() == [0.15, 0.15, 0.15, 0.30]
    assert price_limit("KOSDAQ", d).tolist() == [0.12, 0.15, 0.15, 0.30]


def test_clean_marks_notrade_and_fixes_prices():
    df = synth_frame(1, 200)
    df.loc[50, ["open", "high", "low", "volume"]] = 0
    s = clean.clean_frame(df, "000010", "KOSPI", "day")
    assert s.notrade[50] and s.o[50] == s.h[50] == s.l[50] == s.c[50]
    assert not s.notrade[49]


def test_clean_flags_limit_violation_and_calendar_gap():
    df = synth_frame(2, 300)
    df.loc[100:, ["open", "high", "low", "close"]] *= 2.0  # 하루 +100%: 수정 안 된 분할 같은 데이터 오류
    df.loc[200:, "date"] += pd.Timedelta(days=40)  # 거래정지
    s = clean.clean_frame(df, "000010", "KOSPI", "day")
    assert s.bad[100] and s.bad[200]
    assert not s.slice_ok(60, 150) and not s.slice_ok(150, 240)
    assert s.slice_ok(101, 190)


def test_clean_skips_listing_and_delisting_edges():
    s = clean.clean_frame(synth_frame(3, 300), "000010", "KOSDAQ", "day", is_delisted=True)
    assert s.bad[:5].all() and s.bad[-10:].all() and not s.bad[5:-10].any()


def test_slice_needs_previous_close():
    s = clean.clean_frame(synth_frame(4, 300), "000010", "KOSPI", "day")
    assert not s.slice_ok(0, 80)
    assert np.isclose(s.r[10], np.log(s.c[10] / s.c[9]))
