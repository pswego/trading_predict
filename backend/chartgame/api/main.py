"""FastAPI 앱. /api 아래가 게임 API, 그 밖의 경로는 빌드된 웹(SPA)을 돌려준다."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from .. import config
from ..db.session import get_engine
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_engine()
    sched = None
    if os.environ.get("ENABLE_SCHEDULER") == "1":
        from apscheduler.schedulers.background import BackgroundScheduler

        from ..pipeline import daily

        sched = BackgroundScheduler(timezone="Asia/Seoul")
        sched.add_job(daily.run, "cron", day_of_week="mon-fri", hour=18, minute=30, id="daily", max_instances=1)
        sched.add_job(daily.refresh_listing, "cron", day_of_week="sun", hour=6, id="listing", max_instances=1)
        sched.start()
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="빈칸 차트", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(router)


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    dist = config.WEB_DIST
    f = (dist / path).resolve()
    if path and f.is_file() and dist.resolve() in f.parents:
        return FileResponse(f)
    index = dist / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return JSONResponse({"detail": "웹이 아직 빌드되지 않았어요. web/ 에서 npm run build 를 실행하세요."}, status_code=503)
