"""모든 경로·상수·임계값. 다른 모듈은 여기서만 숫자를 가져온다."""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("CHARTGAME_DATA", REPO / "data"))
RAW = DATA_DIR / "raw"
PRICES = RAW / "prices"
WORK = DATA_DIR / "work"
LOGS = DATA_DIR / "logs"
DB_URL = os.environ.get("CHARTGAME_DB", f"sqlite:///{DATA_DIR / 'chartgame.db'}")
WEB_DIST = Path(os.environ.get("CHARTGAME_WEB_DIST", REPO / "web" / "dist"))
SECRET = os.environ.get("CHARTGAME_SECRET", "dev-secret-change-me")

INTERVALS = ("day", "week")
DIFFICULTIES = ("easy", "normal", "hard")

# (L, G, R): 왼쪽 맥락, 빈칸, 오른쪽 맥락 봉 수
LAYOUTS: dict[str, dict[str, tuple[int, int, int]]] = {
    "day": {"easy": (40, 10, 40), "normal": (30, 18, 30), "hard": (20, 28, 20)},
    "week": {"easy": (30, 8, 30), "normal": (24, 12, 24), "hard": (16, 18, 16)},
}
REGION_LEN = {"day": 90, "week": 68}
DIFFICULTY_QUOTA = {"easy": 0.40, "normal": 0.35, "hard": 0.25}

# --- 수집 ---
NAVER_URL = "https://fchart.stock.naver.com/sise.nhn"
NAVER_COUNT = 3000
NAVER_MIN_INTERVAL = 0.25  # 요청 간 최소 간격(초), 전역
NAVER_WORKERS = 2
DELIST_SINCE = "2002-01-01"
EXCLUDE_NAME_PATTERN = "스팩|리츠|ETN|ETF|선박|인프라|기업인수목적"

# --- 정제 / 윈도우 품질 필터 ---
MAX_NOTRADE_FRAC = 0.02
MAX_FLAT_FRAC = 0.12
MAX_CAL_GAP_DAYS = {"day": 12, "week": 21}  # 추석 등 긴 연휴(최대 11일)는 허용
LIMIT_TOLERANCE = 0.01  # 가격제한폭 + 1%p 넘으면 데이터 오류로 본다
SKIP_AFTER_LISTING = {"day": 5, "week": 1}
SKIP_BEFORE_DELISTING = {"day": 10, "week": 2}
MIN_CLOSE = 50.0
MIN_MEDIAN_TURNOVER = {"day": 5e7, "week": 2.5e8}
DATA_START = "2000-01-01"

# --- 시총 구간 (당시 순위) ---
CAP_TIERS = (("large", 100), ("mid", 500), ("small", 1500), ("micro", 10**9))

# --- 오답 생성 ---
MAX_DRIFT_SIGMA = 0.25  # |d| <= 0.25 σ_g
DIVERSITY_MIN = 0.15  # 보기끼리의 최소 형태 거리 (σ_g·√G 단위)
DECOY_SAMPLE = 4000  # 후보 풀에서 한 번에 뽑아 보는 출처 구간 수

# --- 게임 ---
TIME_LIMIT_MS = {
    "choice4": {"easy": 25000, "normal": 20000, "hard": 20000},
    "ox": {"easy": 12000, "normal": 10000, "hard": 10000},
}
SCORE_MULT = {"easy": 1.0, "normal": 1.5, "hard": 2.5}
QUICK_TOTAL = 10
SURVIVAL_LIVES = 3
DAILY_MIX = ("easy", "easy", "normal", "normal", "hard")
OVERLAP_FRAC = 0.20
STOCK_COOLDOWN = 20
TOKEN_MAX_AGE = 600
LOW_POOL_WARN = 50


def ensure_dirs() -> None:
    for p in (RAW, PRICES / "day", PRICES / "week", WORK, LOGS):
        p.mkdir(parents=True, exist_ok=True)
