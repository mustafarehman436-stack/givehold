FROM node:22-alpine AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend/ .
COPY --from=frontend /web/dist /app/static
ENV STATIC_DIR=/app/static
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && uvicorn app.hosted:create_app --factory --host 0.0.0.0 --port ${PORT:-10000}"]
