"""합성 데이터로 개발용 DB를 만든다 (실제 데이터 없이 화면 확인용)."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from chartgame import config
from chartgame.db.session import make_session
from chartgame.pipeline import build, clean, decoys, generate, windows
from tests.conftest import synth_frame

series = {}
for i in range(60):
    code = f"{i:05d}0"
    s = clean.clean_frame(synth_frame(i, n=1400, vol=0.018 + 0.004 * (i % 5)), code, "KOSPI" if i % 2 else "KOSDAQ", "day")
    s.tier = np.full(len(s), i % 4, dtype=np.int8)
    series[code] = s
stocks = pd.DataFrame([{"code": c, "name": f"테스트전자{int(c[:5])}", "market": s.market, "sector": f"업종{int(c[:5]) % 3}",
    "listed_date": pd.NaT, "delisted_date": pd.Timestamp("2022-03-02") if int(c[:5]) % 9 == 0 else pd.NaT,
    "delist_reason": "감사의견 거절" if int(c[:5]) % 9 == 0 else None, "shares": 1e7, "is_delisted": int(c[:5]) % 9 == 0} for c, s in series.items()])
win, _ = windows.extract(series, stocks, "day", workers=1)
generate._CTX.update(series=series, stocks={r.code: r for r in stocks.itertuples()},
    index={G: decoys.SegIndex(series, G, 1, dict(zip(stocks.code, stocks.sector))) for _, G, _ in config.LAYOUTS["day"].values()})
recs, fail = generate._work(list(win.itertuples()))
db = make_session(sys.argv[1])
print("added", build.load_questions(pd.DataFrame(recs), db), "fail", fail)
