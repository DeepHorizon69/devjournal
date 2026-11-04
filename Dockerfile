# Stage 1: Build Frontend Assets
FROM node:22-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Runtime
FROM python:3.12-slim AS runtime
WORKDIR /app

# Install system dependencies (curl for healthcheck, tzdata for IANA ZoneInfo)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code and built frontend assets
COPY backend/app/ ./app/
COPY --from=frontend-builder /build/dist/ ./frontend-dist/

# Set production environment variables
ENV DEVJOURNAL_DATA_DIR=/data \
    DEVJOURNAL_FRONTEND_DIST_DIR=/app/frontend-dist \
    DEVJOURNAL_LOG_LEVEL=INFO \
    DEVJOURNAL_TIMEZONE=UTC \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://127.0.0.1:8000/api/v1/system/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
