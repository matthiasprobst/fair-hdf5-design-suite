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
    PYTHONDONTWRITEBYTECODE=1 \
    FAIR_HDF5_HOST=0.0.0.0

WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --create-home --uid 10001 appuser

COPY app.py LICENSE CITATION.cff ./
COPY backend/ ./backend/
RUN python -m pip install --no-cache-dir --no-deps -e ./backend
COPY --from=frontend-build /build/frontend/dist/ ./frontend/dist/

RUN mkdir -p /app/data && chown appuser:appuser /app/data

USER appuser
EXPOSE 8000
CMD ["python", "-m", "fair_hdf5"]
