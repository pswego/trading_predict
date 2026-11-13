"""CLI 진입점: `chartgame <명령>`"""
from __future__ import annotations

import typer

app = typer.Typer(add_completion=False, help="차트 빈칸 퍼즐 게임 파이프라인")


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


if __name__ == "__main__":
    app()
