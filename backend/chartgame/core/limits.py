"""시장·날짜별 일간 가격제한폭."""
from __future__ import annotations

import numpy as np
import pandas as pd

_D2005 = np.datetime64("2005-03-28")
_D2015 = np.datetime64("2015-06-15")


def price_limit(market: str, dates) -> np.ndarray:
    """각 날짜에 적용되던 가격제한폭(비율)을 돌려준다. 예: 0.30"""
    d = pd.to_datetime(pd.Series(dates)).to_numpy().astype("datetime64[D]")
    out = np.full(d.shape, 0.30)
    out[d < _D2015] = 0.15
    if market == "KOSDAQ":
        out[d < _D2005] = 0.12
    return out
