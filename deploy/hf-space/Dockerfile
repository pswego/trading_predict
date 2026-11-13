# Hugging Face Spaces 용 (Docker Space). 웹 빌드 없이 게임 서버만 띄운다.
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 GAME_AT_ROOT=1 CHARTGAME_DATA=/tmp/chartgame
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/chartgame ./chartgame
RUN pip install --no-cache-dir .
EXPOSE 7860
CMD ["sh", "-c", "mkdir -p $CHARTGAME_DATA && exec uvicorn chartgame.api.main:app --host 0.0.0.0 --port 7860 --proxy-headers --forwarded-allow-ips=*"]
