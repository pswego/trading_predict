# 빈칸 차트 (Chart Gap)

실제 주식 차트의 **중간 구간**을 가리고, 그 자리에 실제로 들어간 모양을 맞히는 웹 게임입니다.
4지선다(진짜 1개 + 가짜 3개)와 O/X 두 방식이 있고, 시장·시가총액 규모·시기·차트 단위·난이도를 고를 수 있습니다.

- 설계 문서: [`docs/PLAN.md`](docs/PLAN.md)
- 실측 데이터 리포트: [`docs/data_report.md`](docs/data_report.md)

## 빠르게 실행하기

필요한 것: Python 3.12 이상, [uv](https://docs.astral.sh/uv/), Node.js 22

```bash
make install     # 의존성 설치
make data        # 종목 목록 + 일봉·주봉 수집 (처음 한 번, 약 30분)
make questions   # 문제 생성 → 품질 검사 → DB 적재 (약 10분)
make serve       # http://localhost:8000
```

Docker로 실행할 때는 `data/` 폴더가 만들어진 뒤에 `docker compose up --build` 를 실행하세요.
컨테이너는 평일 18:30(KST)에 새 가격을 받아 문제를 다시 만듭니다.

개발할 때는 터미널 두 개에서 `make dev-api` 와 `make dev-web` 을 실행하고 http://localhost:5173 을 엽니다.

## 구조

```
backend/chartgame/
  sources/     네이버 차트 수집기, KRX 종목 목록
  pipeline/    정제 → 시총 구간 → 구간 추출 → 난이도 → 오답 생성 → 판별기 검사 → DB 적재
  api/         FastAPI: 출제, 채점, Elo, 데일리, 순위표
  db/          SQLAlchemy 모델 (기본 SQLite)
web/           React + Vite + Tailwind. 차트는 자체 SVG 컴포넌트
e2e/           Playwright 브라우저 테스트
data/          수집한 가격과 문제 DB (git에 올리지 않음)
```

## 문제가 만들어지는 과정

1. **수집**: 네이버 차트 데이터에서 종목별 일봉(최근 3,000봉)과 주봉(전체)을 받습니다. 상장폐지 종목도 포함합니다.
2. **정제**: 거래정지, 가격제한폭을 넘는 오류, 상장 직후·폐지 직전 구간을 걸러냅니다.
3. **구간 추출**: 종목마다 겹치지 않는 영역을 자르고, 영역 하나에서 문제 하나만 만듭니다. 빈칸은 차트의 30~70% 지점에 옵니다.
4. **난이도**: "맥락만 보고 빈칸을 얼마나 추측할 수 있는가"를 6가지 지표로 점수화합니다.
5. **오답 생성**: 다른 실제 구간을 가져와 변동성을 맞추고, 시작점과 끝점이 실제와 정확히 같도록 보정합니다.
6. **품질 검사**: 실제와 가짜를 구별하도록 학습한 판별 모델로 문제를 풀려 봅니다. 모델이 너무 잘 맞히면 가짜에 티가 난다는 뜻입니다.

## 주요 명령

| 명령 | 하는 일 |
|---|---|
| `chartgame ingest-listing` / `ingest-prices` | 종목 목록 / 가격 수집 (중단 후 재실행하면 이어서 받음) |
| `chartgame all [--limit N]` | 문제 생성 + 판별기 평가 + DB 적재. `--limit` 으로 종목 수를 줄여 빠르게 시험 |
| `chartgame preview --difficulty hard` | 샘플 문제를 이미지로 뽑아 사람 눈으로 검수 |
| `chartgame daily` | 증분 수집 후 재생성 (자동화용) |
| `chartgame recalibrate` | 충분히 플레이된 문제의 난이도를 실제 정답률 기준으로 재분류 |
| `chartgame report` | 실측 데이터 리포트 갱신 |
| `chartgame serve` | API + 웹 서버 |

## 테스트

```bash
make test   # 백엔드(pytest) + 웹(vitest)
make e2e    # 브라우저 테스트 (합성 데이터로 서버를 띄워 실행)
```

## 환경 변수

| 이름 | 기본값 | 설명 |
|---|---|---|
| `CHARTGAME_DATA` | `./data` | 가격 원본과 DB 위치 |
| `CHARTGAME_DB` | `sqlite:///data/chartgame.db` | DB 주소 (PostgreSQL도 가능) |
| `CHARTGAME_SECRET` | 개발용 값 | 문제 토큰 서명 키. **운영에서는 반드시 바꾸세요** |
| `ENABLE_SCHEDULER` | 꺼짐 | `1`이면 서버 안에서 일일 수집을 실행 |
| `CHARTGAME_RATE_LIMIT` | `240` | 사용자당 분당 요청 수 (`0`이면 끔) |

## 알아둘 점

- 과거 데이터 기반 오락용 게임이며 투자 권유가 아닙니다.
- 가격 데이터는 네이버 금융의 비공식 차트 엔드포인트에서 받습니다. 개인·비상업 용도를 전제로 하며, 서비스로 공개하거나 수익화하려면 정식 데이터 라이선스로 바꿔야 합니다.
- "당시 시가총액"은 `수정종가 × 현재 상장주식수`로 근사한 순위입니다. 유상증자 등 주식 수 변화는 반영되지 않습니다.
