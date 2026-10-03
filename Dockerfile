# Multi-stage Dockerfile for D-DATO Full-Stack Application
# Stage 1: Build Frontend SPA
FROM node:20-bookworm-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend & Unified Production Runtime
FROM python:3.11-slim AS runtime
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install backend dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend application and demo data fixtures
COPY backend/ ./backend/
COPY demo_data/ ./demo_data/

# Copy compiled frontend assets into the expected directory
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Production environment configuration
ENV PYTHONUNBUFFERED=1 \
    DEMO_MODE=true \
    PORT=8000 \
    PYTHONPATH=/app/backend

WORKDIR /app/backend

EXPOSE 8000

# Start Uvicorn bound to Railway dynamic $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
