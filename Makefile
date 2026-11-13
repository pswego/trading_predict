.PHONY: install data questions dev-api dev-web build-web serve test lint preview e2e

install:            ## 의존성 설치
	cd backend && uv venv --python 3.13 .venv && uv pip install -e ".[dev]"
	cd web && npm install

data:               ## 종목 목록과 가격 수집 (처음 한 번, 약 30분)
	cd backend && .venv/bin/chartgame ingest-listing && .venv/bin/chartgame ingest-prices

questions:          ## 문제 생성 + 판별기 평가 + DB 적재
	cd backend && .venv/bin/chartgame all

dev-api:            ## API 서버 (자동 재시작)
	cd backend && .venv/bin/chartgame serve --reload

dev-web:            ## 웹 개발 서버 (http://localhost:5173, /api는 8000번으로 전달)
	cd web && npm run dev

build-web:
	cd web && npm run build

serve: build-web    ## 빌드된 웹 + API를 한 서버로 (http://localhost:8000)
	cd backend && .venv/bin/chartgame serve

test:
	cd backend && .venv/bin/pytest
	cd web && npm test

lint:
	cd backend && .venv/bin/ruff check .
	cd web && npm run lint

preview:            ## 난이도별 샘플 문제 이미지 (data/work/preview_*.png)
	cd backend && for d in easy normal hard; do .venv/bin/chartgame preview --difficulty $$d; done

e2e: build-web      ## 브라우저 자동 테스트 (합성 데이터로 서버를 띄워서 실행)
	cd e2e && npx playwright test --trace off
