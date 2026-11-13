"""CLI 진입점: `chartgame <명령>`"""
from __future__ import annotations

import json

import typer

app = typer.Typer(add_completion=False, help="빈칸 차트 — 데이터 파이프라인과 서버")


@app.command("ingest-listing")
def ingest_listing():
    """종목 마스터(상장 + 폐지)를 받는다."""
    from .pipeline import ingest

    ingest.ingest_listing()


@app.command("ingest-prices")
def ingest_prices(incremental: bool = False, limit: int = 0):
    """네이버에서 일봉·주봉을 받는다. 이미 받은 종목은 건너뛴다."""
    from .pipeline import ingest

    ingest.ingest_prices(incremental=incremental, limit=limit or None)


@app.command()
def generate(interval: str = "day", limit: int = 0, workers: int = 4):
    """구간 추출 + 오답 생성 → data/work/questions_<interval>.parquet"""
    from .pipeline import generate as g

    g.run(interval, limit=limit or None, workers=workers)


@app.command()
def evaluate(interval: str = "day"):
    """판별기 품질 게이트를 돌리고 결과를 출력한다."""
    from .pipeline import daily

    typer.echo(json.dumps(daily.evaluate(interval), ensure_ascii=False, indent=1))


@app.command()
def build():
    """문제 Parquet을 DB에 적재한다 (이미 있는 문제는 유지)."""
    from .pipeline import build as b

    typer.echo(b.run())


@app.command("all")
def build_all(limit: int = 0, workers: int = 4):
    """generate → evaluate → build 를 일봉·주봉 모두에 대해 실행. --limit 으로 종목 수를 줄일 수 있다."""
    from .pipeline import daily

    typer.echo(json.dumps(daily.full_build(limit or None, workers), ensure_ascii=False, indent=1, default=str))


@app.command()
def daily():
    """증분 수집 후 전체 재생성 (거래일 장 마감 후 실행)."""
    from .pipeline import daily as d

    out = d.run()
    typer.echo("ok" if out.get("ok") else out.get("error"))


@app.command()
def preview(interval: str = "day", difficulty: str = "normal", n: int = 12, blind: bool = False, seed: int = 0):
    """문제 샘플을 4지선다 화면처럼 그린 PNG를 만든다 (사람 눈 검수용)."""
    from .pipeline import preview as p

    typer.echo(p.run(interval, difficulty, n, mark_answer=not blind, seed=seed))


@app.command()
def report():
    """실측 데이터 리포트를 docs/data_report.md 에 쓴다."""
    from .pipeline import report as r

    typer.echo(r.write())


@app.command()
def recalibrate(min_plays: int = 30):
    """충분히 플레이된 문제의 난이도를 실제 정답률(Elo) 기준으로 다시 분류한다."""
    from sqlalchemy import select

    from .db.models import Question
    from .db.session import make_session
    from .pipeline import build as b

    db = make_session()
    changed = 0
    for q in db.scalars(select(Question).where(Question.plays >= min_plays)):
        new = "easy" if q.elo < 900 else ("normal" if q.elo < 1150 else "hard")
        if new != q.difficulty:
            q.difficulty = new
            changed += 1
    db.commit()
    b.refresh_stats(db)
    typer.echo(f"재분류 {changed}건")


@app.command()
def standalone(site: bool = False):
    """한 파일짜리 게임을 만든다. 기본: 서버용 static/game.html. --site: 정적 호스팅용 site/index.html (P2P 대전)."""
    from .pipeline import standalone as s

    typer.echo(s.write_site() if site else s.write())


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """API + 웹 서버를 띄운다."""
    import uvicorn

    uvicorn.run("chartgame.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
