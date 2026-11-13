# 1) 웹 빌드
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# 2) 실행 이미지: API + 정적 웹
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 CHARTGAME_DATA=/data CHARTGAME_WEB_DIST=/app/web/dist
WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/chartgame ./chartgame
RUN pip install --no-cache-dir .
COPY --from=web /web/dist /app/web/dist
VOLUME /data
EXPOSE 8000
CMD ["chartgame", "serve", "--host", "0.0.0.0", "--port", "8000"]
