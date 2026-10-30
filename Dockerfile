# Tamheed — production image (used by Railway).
# 1) build the website
FROM node:20-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npx vite build

# 2) API + worker + video renderer
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg espeak-ng fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /app/frontend/dist frontend/dist
# Database + generated files live on a Railway volume mounted at /data (survives redeploys).
ENV DATABASE_URL=sqlite:////data/tamheed.db \
    TAMHEED_STORAGE=/data/storage \
    COOKIE_SECURE=1 \
    VIDEO_W=960 VIDEO_H=540 \
    PYTHONUNBUFFERED=1
WORKDIR /app/backend
CMD ["sh", "-c", "mkdir -p /data/storage && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
