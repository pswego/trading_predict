"""실측 데이터 리포트 (docs/data_report.md)."""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd

from .. import config
from ..sources.listing import load_stocks
from . import clean

LAB = {"KOSPI": "코스피", "KOSDAQ": "코스닥", "large": "대형", "mid": "중형", "small": "소형", "micro": "초소형",
       "easy": "쉬움", "normal": "보통", "hard": "어려움", "day": "일봉", "week": "주봉"}


def _table(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "\n".join("| " + " | ".join(f"{v:,}" if isinstance(v, int | np.integer) else str(v) for v in row) + " |"
                             for row in df.itertuples(index=False)) + "\n"


def _limit_check(series: dict[str, clean.Series]) -> pd.DataFrame:
    """시기별로 실제 일간 수익률이 가격제한폭 표와 맞는지."""
    rows = []
    eras = [("~2005-03-27", None, "2005-03-28"), ("2005-03-28~2015-06-14", "2005-03-28", "2015-06-15"), ("2015-06-15~", "2015-06-15", None)]
    for market in ("KOSPI", "KOSDAQ"):
        for name, a, b in eras:
            rets, lim = [], None
            for s in series.values():
                if s.market != market:
                    continue
                m = np.ones(len(s), dtype=bool)
                if a:
                    m &= s.date >= np.datetime64(a)
                if b:
                    m &= s.date < np.datetime64(b)
                m[0] = False
                m &= ~s.notrade
                if m.any():
                    rets.append(np.abs(np.exp(s.r[m]) - 1))
                    lim = float(s.limit[m][0])
            if not rets:
                continue
            r = np.concatenate(rets)
            rows.append({"시장": LAB[market], "기간": name, "표의 제한폭": f"±{lim:.0%}", "봉 수": len(r),
                         "99.9% 분위 수익률": f"{np.quantile(r, 0.999):.1%}",
                         "제한폭 +1%p 초과 비율": f"{(r > lim + 0.01).mean():.3%}"})
    return pd.DataFrame(rows)


def write() -> str:
    stocks = load_stocks()
    out = [f"# 실측 데이터 리포트\n\n생성일: {dt.date.today()} · `chartgame report` 로 다시 만들 수 있습니다.\n"]

    out.append("## 1. 종목과 가격 데이터\n")
    rows = []
    for iv in config.INTERVALS:
        files = list((config.PRICES / iv).glob("*.parquet"))
        n_rows, n_data, first, last = 0, 0, None, None
        for f in files:
            d = pd.read_parquet(f, columns=["date"])
            if len(d):
                n_data += 1
                n_rows += len(d)
                first = d.date.min() if first is None else min(first, d.date.min())
                last = d.date.max() if last is None else max(last, d.date.max())
        rows.append({"단위": LAB[iv], "받은 종목": len(files), "데이터 있는 종목": n_data, "봉 수": n_rows,
                     "기간": f"{first:%Y-%m-%d} ~ {last:%Y-%m-%d}" if first is not None else "-"})
    out.append(f"- 종목 마스터: 상장 {int((~stocks.is_delisted).sum()):,}개, 상장폐지(2002년 이후 보통주) {int(stocks.is_delisted.sum()):,}개\n")
    out.append(_table(pd.DataFrame(rows)))
    out.append("\n네이버 일봉은 종목당 최근 3,000봉까지만 제공됩니다. 상장폐지 종목은 폐지 직전 3,000봉이 오며, "
               "오래전에 폐지된 종목 일부는 데이터가 없습니다.\n")

    out.append("\n## 2. 가격제한폭 표 검증 (일봉)\n")
    day = clean.load_all("day", stocks)
    out.append(_table(_limit_check(day)))
    out.append("\n'제한폭 +1%p 초과'는 데이터 오류나 반영 안 된 권리락으로 보고 해당 봉이 들어간 구간을 문제에서 뺍니다.\n")

    out.append("\n## 3. 문제 풀\n")
    frames = {}
    for iv in config.INTERVALS:
        path = config.WORK / f"questions_{iv}.parquet"
        if path.exists():
            frames[iv] = pd.read_parquet(path, columns=["code", "interval", "market", "cap_tier", "era", "difficulty", "p_score"]
                                         + (["ai_p_real", "ai_hit"] if "ai_hit" in pd.read_parquet(path).columns else []))
    if frames:
        allq = pd.concat(frames.values())
        gen = {iv: json.loads((config.WORK / f"generate_{iv}.json").read_text()) for iv in frames
               if (config.WORK / f"generate_{iv}.json").exists()}
        rows = []
        for iv, df in frames.items():
            g = gen.get(iv, {})
            rows.append({"단위": LAB[iv], "정제 후 종목": g.get("stocks", "-"), "추출한 구간": g.get("windows", "-"),
                         "오답 생성 실패": g.get("decoy_failures", "-"), "최종 문제": len(df),
                         **{LAB[d]: int((df.difficulty == d).sum()) for d in config.DIFFICULTIES}})
        out.append(_table(pd.DataFrame(rows)))
        out.append(f"\n**전체 문제 수: {len(allq):,}개** (종목 {allq.code.nunique():,}개). 영역 하나에서 문제 하나만 만들기 때문에 "
                   "사용자가 같은 차트 구간을 두 번 볼 일이 없는 '고유 문제' 수입니다.\n")
        for title, col, order in (("시장별", "market", ["KOSPI", "KOSDAQ"]), ("당시 시총 규모별", "cap_tier", ["large", "mid", "small", "micro"]),
                                  ("시기별", "era", ["2000s", "2010s", "2020s"])):
            piv = allq.pivot_table(index=col, columns="interval", values="code", aggfunc="count", fill_value=0).reindex(order).fillna(0).astype(int)
            piv = piv.rename(columns=LAB).rename(index=LAB).reset_index().rename(columns={col: title})
            out.append(f"\n### {title}\n\n" + _table(piv))
        combo = allq.groupby(["interval", "market", "cap_tier", "era", "difficulty"]).size().rename("n").reset_index()
        small = combo.sort_values("n").head(12).copy()
        for c in ("interval", "market", "cap_tier", "difficulty"):
            small[c] = small[c].map(LAB)
        small.columns = ["단위", "시장", "규모", "시기", "난이도", "문제 수"]
        out.append("\n### 가장 문제가 적은 조건 조합 (풀 고갈 위험)\n\n" + _table(small))
        out.append(f"\n조건 조합 {len(combo):,}개 중 문제가 50개 미만인 조합은 {int((combo.n < 50).sum()):,}개입니다. "
                   "이런 조합을 고르면 설정 화면에서 경고하고, 다 풀면 인접 조건으로 넓힙니다.\n")

        out.append("\n## 4. 판별기 품질 게이트\n\n실제 보기와 가짜 보기를 구별하도록 학습한 모델(종목 단위 교차검증)이 4지선다를 풀었을 때의 정답률입니다. "
                   "우연히 맞힐 확률은 25%이고, 낮을수록 가짜에 티가 없다는 뜻입니다.\n\n")
        rows = []
        for iv in frames:
            p = config.WORK / f"discriminator_{iv}.json"
            if not p.exists():
                continue
            r = json.loads(p.read_text())
            for d in config.DIFFICULTIES:
                if d in r["accuracy"]:
                    th = {"easy": "없음", "normal": "≤ 45%", "hard": "≤ 35%"}[d]
                    after = r["accuracy_after"].get(d)
                    ok = "-" if d == "easy" else ("통과" if after <= {"normal": 0.45, "hard": 0.35}[d] else "**미달**")
                    rows.append({"단위": LAB[iv], "난이도": LAB[d], "판별기 정답률": f"{r['accuracy'][d]:.1%}",
                                 "조정 후": f"{after:.1%}", "기준": th, "결과": ok})
            out.append(f"- {LAB[iv]}: 판별기가 60% 넘는 확신으로 맞힌 '어려움' 문제 {r['downgraded_hard']:,}개를 '보통'으로 내렸습니다. "
                       f"아직 남은 단서(어려움 기준): {', '.join(list(r['top_tells'].get('hard', {}))[:4])}\n")
        out.append("\n" + _table(pd.DataFrame(rows)))
    else:
        out.append("아직 문제를 생성하지 않았습니다. `chartgame all` 을 먼저 실행하세요.\n")

    path = config.REPO / "docs" / "data_report.md"
    path.write_text("\n".join(out))
    return str(path)
