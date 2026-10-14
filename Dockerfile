FROM node:22-bookworm-slim AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src/ ./src/
COPY frontend/public/ ./public/
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt requirements-shacl.txt ./
RUN python -m pip install --no-cache-dir -r requirements-shacl.txt \
    && useradd --create-home --uid 10001 appuser

COPY app.py backend.py LICENSE CITATION.cff ./
COPY --from=frontend-build /build/frontend/dist/ ./frontend/dist/

USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
